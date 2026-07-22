"""Redis caching layer with graceful degradation.

Architecture:
    - Module-level ``cache_client`` singleton (lazy init on first use).
    - All public methods catch exceptions internally — the app never
      500s on a Redis outage. Failures are logged, and the caller sees
      ``None`` (cache miss) or a silent no-op (cache set).
    - Key format: ``"plan:v2:<sha256>"`` — the version tag allows
      wholesale invalidation by bumping the prefix.
"""

from __future__ import annotations

import hashlib
import json
import logging

from redis import RedisError
from redis.asyncio import Redis

from config import REDIS_URL, CACHE_TTL_SECONDS
from models import PlanRequest

logger = logging.getLogger("travel_agent.cache")

KEY_PREFIX = "plan:v2"


def _compute_key(plan_req: PlanRequest) -> str:
    """Return a deterministic SHA-256 cache key for a ``PlanRequest``."""
    canonical = json.dumps(
        {
            "destination": plan_req.destination,
            "days": plan_req.days,
            "budget_usd": plan_req.budget_usd,
            "travel_style": plan_req.travel_style.value,
            "group_type": plan_req.group_type.value,
            "dietary": plan_req.dietary,
            "constraints": plan_req.constraints,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    return f"{KEY_PREFIX}:{digest}"


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

    async def get(self, plan_req: PlanRequest) -> dict | None:
        r = await self._get_redis()
        if r is None:
            return None
        key = _compute_key(plan_req)
        try:
            raw = await r.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except (RedisError, RuntimeError, json.JSONDecodeError) as exc:
            logger.warning("Cache GET failed for key=%s: %s", key, exc)
            return None

    async def set(self, plan_req: PlanRequest, data: dict, ttl: int | None = None) -> None:
        r = await self._get_redis()
        if r is None:
            return
        key = _compute_key(plan_req)
        try:
            await r.setex(key, ttl or CACHE_TTL_SECONDS, json.dumps(data))
        except (RedisError, RuntimeError) as exc:
            logger.warning("Cache SET failed for key=%s: %s", key, exc)

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
