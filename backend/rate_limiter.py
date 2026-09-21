"""Per-user rate limiting with Redis (sliding window) + SQLite + in-memory fallback.

Sits as a second layer on top of the existing slowapi IP-based limiter.
When the user is authenticated, requests are counted per ``user_id``;
unauthenticated requests fall through to slowapi (IP-based).

Usage (middleware is registered in main.py):

    from rate_limiter import RateLimitMiddleware
    app.add_middleware(RateLimitMiddleware)
"""

from __future__ import annotations

import json
import logging
import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from config import REDIS_URL, settings
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlite_fallback import get_sqlite_connection

logger = logging.getLogger("travel_agent.rate_limiter")

# Map URL path prefixes to (endpoint_type, limit_setting_name)
_ROUTE_RULES: list[tuple[str, str, str]] = [
    ("/chat/", "chat", "RATE_LIMIT_CHAT_PER_MIN"),
    ("/upload", "upload", "RATE_LIMIT_UPLOADS_PER_MIN"),
    ("/threads", "threads", "RATE_LIMIT_THREADS_PER_MIN"),
]


def _match_route(path: str) -> tuple[str, int] | None:
    """Return (endpoint_type, limit) for the given path, or None if not rate-limited."""
    for prefix, endpoint_type, setting_name in _ROUTE_RULES:
        if path.startswith(prefix):
            return endpoint_type, getattr(settings, setting_name)
    return None


class RateLimiter:
    """Sliding-window rate limiter backed by Redis → SQLite → in-memory."""

    def __init__(self) -> None:
        self._redis: Redis | None = None
        self._mem: dict[str, list[float]] = {}  # key -> [timestamps]
        self._last_ts: dict[str, float] = {}  # key -> last recorded timestamp

    async def _get_redis(self) -> Redis | None:
        if self._redis is None:
            try:
                self._redis = Redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)
                await self._redis.ping()
                logger.info("RateLimiter connected to Redis at %s", REDIS_URL)
            except (RedisError, RuntimeError) as exc:
                logger.warning("RateLimiter Redis unavailable — using fallback: %s", exc)
                self._redis = None
        return self._redis

    async def check_rate_limit(
        self,
        user_id: str,
        endpoint_type: str,
        limit: int,
        window_seconds: int = 60,
    ) -> tuple[bool, int]:
        """Check if a request is within the rate limit.

        Returns ``(allowed, retry_after_seconds)``.
        """
        key = f"ratelimit:{user_id}:{endpoint_type}"
        now = time.time()
        # Guarantee a unique timestamp per hit — identical `now` values would
        # collapse in the cross-store union and undercount rapid requests.
        last = self._last_ts.get(key, 0.0)
        if now <= last:
            now = last + 1e-6
        self._last_ts[key] = now
        window_start = now - window_seconds

        # Record the request in every available store, then count the
        # union of timestamps — hits recorded during a Redis blip still
        # count after Redis recovers.
        seen: set[float] = {now}
        persisted = False

        # --- Redis (sliding window via sorted set) ---
        r = await self._get_redis()
        if r is not None:
            try:
                pipe = r.pipeline()
                pipe.zremrangebyscore(key, 0, window_start)
                pipe.zadd(key, {str(now): now})
                pipe.zrangebyscore(key, window_start, "+inf", withscores=True)
                pipe.expire(key, window_seconds)
                results = await pipe.execute()
                for _member, score in results[2]:
                    seen.add(float(score))
                persisted = True
            except (RedisError, RuntimeError) as exc:
                logger.warning("RateLimiter Redis error: %s", exc)

        # --- SQLite write-through ---
        db = await get_sqlite_connection()
        if db is not None:
            try:
                await db.execute(
                    "DELETE FROM rate_limits WHERE key = ? AND timestamp < ?",
                    (key, window_start),
                )
                await db.execute(
                    "INSERT OR REPLACE INTO rate_limits (key, timestamp) VALUES (?, ?)",
                    (key, now),
                )
                cur = await db.execute(
                    "SELECT timestamp FROM rate_limits WHERE key = ? AND timestamp >= ?",
                    (key, window_start),
                )
                for row in await cur.fetchall():
                    seen.add(float(row[0]))
                await db.commit()
                persisted = True
            except Exception as exc:  # noqa: BLE001
                logger.warning("RateLimiter SQLite error: %s", exc)

        if not persisted:
            # --- In-memory last resort ---
            for k in [k for k, ts in self._mem.items() if not ts or max(ts) <= window_start]:
                del self._mem[k]
            timestamps = [t for t in self._mem.get(key, []) if t > window_start]
            timestamps.append(now)
            self._mem[key] = timestamps
            seen.update(timestamps)

        count = len(seen)
        if count <= limit:
            return True, 0
        # Retry-after: time until the oldest in-window hit expires
        oldest = min(seen)
        retry_after = int(oldest + window_seconds - now) + 1
        return False, max(retry_after, 1)



# Singleton
rate_limiter = RateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that enforces per-user rate limits.

    Only applies to authenticated users on rate-limited routes.
    Unauthenticated requests fall through to slowapi (IP-based).
    """

    async def dispatch(self, request: Request, call_next: Callable):
        path = request.url.path
        rule = _match_route(path)
        if rule is None:
            return await call_next(request)

        endpoint_type, limit = rule

        # Extract user_id from session cookie
        user_id = await self._get_user_id(request)
        if user_id is None:
            # Unauthenticated — let slowapi handle it
            return await call_next(request)

        allowed, retry_after = await rate_limiter.check_rate_limit(
            user_id, endpoint_type, limit
        )
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Rate limit exceeded. Try again in {retry_after} seconds.",
                },
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)

    async def _get_user_id(self, request: Request) -> str | None:
        """Extract user_id from the session cookie via oauth.get_session."""
        session_id = request.cookies.get("voyager_session")
        if not session_id:
            return None
        try:
            from oauth import get_session
            session = await get_session(session_id)
            if session:
                return session.get("user_id")
        except Exception:  # noqa: BLE001, S110
            pass
        return None
