"""Research result cache — Redis-backed with in-memory fallback.

Caches formatted Tavily search results to avoid redundant API calls.
Follows the same graceful degradation pattern as cost_store.py and feedback_store.py.

Redis key layout:
  research:cache:{sha256_hash}   — string: formatted search result text
  research:cache:index           — set: all cache keys (for bulk invalidation)
  research:cache:hits            — counter: cache hits (for observability)
  research:cache:misses          — counter: cache misses (for observability)
"""

from __future__ import annotations

import logging
import time

from redis.asyncio import Redis
from redis.exceptions import RedisError

from config import REDIS_URL

logger = logging.getLogger("travel_agent.research_cache")

_DEFAULT_TTL = 86400  # 24 hours


class ResearchCache:
    """Redis-backed research cache with in-memory fallback."""

    def __init__(self) -> None:
        self._redis: Redis | None = None
        self._mem_cache: dict[str, tuple[str, float]] = {}

    async def _get_redis(self) -> Redis | None:
        if self._redis is None:
            try:
                self._redis = Redis.from_url(REDIS_URL, decode_responses=True)
                await self._redis.ping()
                logger.info("ResearchCache connected to Redis at %s", REDIS_URL)
            except (RedisError, RuntimeError) as exc:
                logger.warning("ResearchCache Redis unavailable — using in-memory fallback: %s", exc)
                self._redis = None
        return self._redis

    async def get(self, key: str) -> str | None:
        """Get a cached search result by key. Returns None on miss or Redis error."""
        r = await self._get_redis()
        if r is not None:
            try:
                value = await r.get(f"research:cache:{key}")
                if value is not None:
                    await r.incr("research:cache:hits")
                    return value
                await r.incr("research:cache:misses")
                return None
            except (RedisError, RuntimeError) as exc:
                logger.warning("ResearchCache get Redis error: %s", exc)

        now = time.time()
        entry = self._mem_cache.get(key)
        if entry is not None:
            value, expiry = entry
            if now < expiry:
                return value
            del self._mem_cache[key]
        return None

    async def set(self, key: str, value: str, ttl: int = _DEFAULT_TTL) -> None:
        """Store a formatted search result with TTL."""
        r = await self._get_redis()
        if r is not None:
            try:
                pipe = r.pipeline()
                pipe.set(f"research:cache:{key}", value, ex=ttl)
                pipe.sadd("research:cache:index", key)
                pipe.expire("research:cache:index", ttl)
                await pipe.execute()
                return
            except (RedisError, RuntimeError) as exc:
                logger.warning("ResearchCache set Redis error: %s", exc)

        self._mem_cache[key] = (value, time.time() + ttl)

    async def invalidate_all(self) -> int:
        """Delete all cached research results. Returns count of cleared entries."""
        r = await self._get_redis()
        if r is not None:
            try:
                keys = await r.smembers("research:cache:index")
                if not keys:
                    return 0
                pipe = r.pipeline()
                for k in keys:
                    pipe.delete(f"research:cache:{k}")
                pipe.delete("research:cache:index")
                results = await pipe.execute()
                count = sum(1 for r_val in results[:-1] if r_val)
                logger.info("ResearchCache invalidated %d entries", count)
                return count
            except (RedisError, RuntimeError) as exc:
                logger.warning("ResearchCache invalidate_all Redis error: %s", exc)

        count = len(self._mem_cache)
        self._mem_cache.clear()
        return count

    async def get_stats(self) -> dict:
        """Return cache statistics for admin observability."""
        r = await self._get_redis()
        if r is not None:
            try:
                pipe = r.pipeline()
                pipe.scard("research:cache:index")
                pipe.get("research:cache:hits")
                pipe.get("research:cache:misses")
                results = await pipe.execute()
                return {
                    "total_entries": int(results[0] or 0),
                    "cache_hits": int(results[1] or 0),
                    "cache_misses": int(results[2] or 0),
                }
            except (RedisError, RuntimeError) as exc:
                logger.warning("ResearchCache get_stats Redis error: %s", exc)

        now = time.time()
        active = sum(1 for _, exp in self._mem_cache.values() if now < exp)
        return {
            "total_entries": active,
            "cache_hits": 0,
            "cache_misses": 0,
        }


research_cache = ResearchCache()
