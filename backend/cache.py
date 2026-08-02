"""Redis health-check layer with graceful degradation.

Caching of plan requests/responses has been removed along with the form-based
flow. This module retains a minimal Redis connection wrapper used by the
/health endpoint to report Redis connectivity status.
"""

from __future__ import annotations

import logging

from config import REDIS_URL
from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = logging.getLogger("travel_agent.cache")


class CacheClient:
    """Thin async wrapper around ``redis.asyncio.Redis``.

    All public methods catch exceptions — Redis being down never breaks
    the application.
    """

    def __init__(self) -> None:
        self._redis: Redis | None = None

    async def _get_redis(self) -> Redis | None:
        if self._redis is None:
            try:
                self._redis = Redis.from_url(REDIS_URL, decode_responses=True)
                await self._redis.ping()
                logger.info("Connected to Redis at %s", REDIS_URL)
            except (RedisError, RuntimeError) as exc:
                logger.warning("Redis unavailable — caching disabled: %s", exc)
                self._redis = None
        return self._redis

    async def ping(self) -> bool:
        r = await self._get_redis()
        if r is None:
            return False
        try:
            return await r.ping()
        except (RedisError, RuntimeError):
            return False

    async def aclose(self) -> None:
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except (RedisError, RuntimeError):
                pass
            self._redis = None


cache_client = CacheClient()
