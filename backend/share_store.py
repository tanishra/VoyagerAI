"""Share token store — Redis-backed shareable itinerary links with TTL.

Stores itinerary snapshots against unguessable tokens so users can share
read-only itinerary links with anyone. Tokens expire after a configurable
TTL (default 7 days). Includes listing and revocation for full management.

Falls back to an in-memory dict when Redis is unavailable (same graceful
degradation pattern as threads.py and cache.py).
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import time
from dataclasses import dataclass

from redis.asyncio import Redis
from redis.exceptions import RedisError

from config import REDIS_URL, settings

logger = logging.getLogger("travel_agent.share")

_TTL_SECONDS: int = settings.SHARE_TTL_DAYS * 86_400


@dataclass
class ShareMeta:
    token: str
    thread_id: str
    destination: str
    created_at: float
    expires_at: float


def _user_tag(user_id: str) -> str:
    """Hash the user_id to a 12-char tag (same scheme as threads.py)."""
    return hashlib.sha256(user_id.encode()).hexdigest()[:12]


class ShareStore:
    """Redis-backed share token store with in-memory fallback."""

    def __init__(self) -> None:
        self._redis: Redis | None = None
        self._mem: dict[str, dict[str, dict]] = {}  # user_id → {token → data}

    async def _get_redis(self) -> Redis | None:
        if self._redis is None:
            try:
                self._redis = Redis.from_url(REDIS_URL, decode_responses=True)
                await self._redis.ping()
                logger.info("ShareStore connected to Redis at %s", REDIS_URL)
            except (RedisError, RuntimeError) as exc:
                logger.warning("ShareStore Redis unavailable — using in-memory fallback: %s", exc)
                self._redis = None
        return self._redis

    async def create_share(
        self,
        user_id: str,
        thread_id: str,
        itinerary_json: str,
        destination: str,
    ) -> tuple[str, float]:
        """Create a share token. Returns (token, expires_at)."""
        tag = _user_tag(user_id)
        token = secrets.token_urlsafe(16)
        now = time.time()
        expires_at = now + _TTL_SECONDS

        r = await self._get_redis()
        if r is not None:
            try:
                key = f"shares:{tag}:{token}"
                pipe = r.pipeline()
                pipe.hset(key, mapping={
                    "token": token,
                    "thread_id": thread_id,
                    "destination": destination[:100],
                    "itinerary_json": itinerary_json,
                    "created_at": str(now),
                    "expires_at": str(expires_at),
                })
                pipe.zadd(f"shares:{tag}", {token: now})
                pipe.expire(key, _TTL_SECONDS)
                await pipe.execute()
                return token, expires_at
            except (RedisError, RuntimeError) as exc:
                logger.warning("ShareStore create_share Redis error — falling back: %s", exc)

        # In-memory fallback
        user_shares = self._mem.setdefault(user_id, {})
        user_shares[token] = {
            "token": token,
            "thread_id": thread_id,
            "destination": destination[:100],
            "itinerary_json": itinerary_json,
            "created_at": now,
            "expires_at": expires_at,
        }
        return token, expires_at

    async def get_share(self, token: str) -> dict | None:
        """Get a share by token. Returns {itinerary_json, destination, created_at, expires_at} or None."""
        r = await self._get_redis()
        if r is not None:
            try:
                # Scan across all user tags — public access, no user_id needed
                cursor = 0
                while True:
                    cursor, keys = await r.scan(cursor, match=f"shares:*:{token}", count=100)
                    for key in keys:
                        data = await r.hgetall(key)
                        if data:
                            expires_at = float(data.get("expires_at", 0))
                            if expires_at < time.time():
                                await r.delete(key)
                                return None
                            return {
                                "itinerary_json": data.get("itinerary_json", ""),
                                "destination": data.get("destination", ""),
                                "created_at": float(data.get("created_at", 0)),
                                "expires_at": expires_at,
                            }
                    if cursor == 0:
                        break
                return None
            except (RedisError, RuntimeError) as exc:
                logger.warning("ShareStore get_share Redis error — falling back: %s", exc)

        # In-memory fallback
        for user_shares in self._mem.values():
            if token in user_shares:
                data = user_shares[token]
                if data["expires_at"] < time.time():
                    del user_shares[token]
                    return None
                return {
                    "itinerary_json": data["itinerary_json"],
                    "destination": data["destination"],
                    "created_at": data["created_at"],
                    "expires_at": data["expires_at"],
                }
        return None

    async def list_shares(self, user_id: str) -> list[ShareMeta]:
        """List all active shares for a user."""
        tag = _user_tag(user_id)
        r = await self._get_redis()
        if r is not None:
            try:
                tokens = await r.zrevrange(f"shares:{tag}", 0, -1)
                if not tokens:
                    return []
                pipe = r.pipeline()
                for tok in tokens:
                    pipe.hgetall(f"shares:{tag}:{tok}")
                results = await pipe.execute()
                shares = []
                now = time.time()
                for tok, data in zip(tokens, results, strict=False):
                    if not data:
                        continue
                    expires_at = float(data.get("expires_at", 0))
                    if expires_at < now:
                        continue
                    shares.append(ShareMeta(
                        token=data.get("token", tok),
                        thread_id=data.get("thread_id", ""),
                        destination=data.get("destination", ""),
                        created_at=float(data.get("created_at", 0)),
                        expires_at=expires_at,
                    ))
                return shares
            except (RedisError, RuntimeError) as exc:
                logger.warning("ShareStore list_shares Redis error — falling back: %s", exc)

        # In-memory fallback
        user_shares = self._mem.get(user_id, {})
        now = time.time()
        shares = []
        for data in user_shares.values():
            if data["expires_at"] < now:
                continue
            shares.append(ShareMeta(
                token=data["token"],
                thread_id=data["thread_id"],
                destination=data["destination"],
                created_at=data["created_at"],
                expires_at=data["expires_at"],
            ))
        shares.sort(key=lambda s: s.created_at, reverse=True)
        return shares

    async def revoke_share(self, user_id: str, token: str) -> bool:
        """Revoke a share token. Returns True if it existed."""
        tag = _user_tag(user_id)
        r = await self._get_redis()
        if r is not None:
            try:
                key = f"shares:{tag}:{token}"
                deleted = await r.delete(key)
                await r.zrem(f"shares:{tag}", token)
                return deleted > 0
            except (RedisError, RuntimeError) as exc:
                logger.warning("ShareStore revoke_share Redis error — falling back: %s", exc)

        # In-memory fallback
        user_shares = self._mem.get(user_id, {})
        if token in user_shares:
            del user_shares[token]
            return True
        return False


share_store = ShareStore()
