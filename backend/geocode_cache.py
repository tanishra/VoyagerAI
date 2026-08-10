"""Geocode cache — Redis-backed with in-memory fallback.

Caches geocoding results (lat/lng for location strings) so we only hit
Nominatim once per unique location. Uses a 180-day TTL to allow eventual
data refresh without re-geocoding on every itinerary render.

Same graceful degradation pattern as threads.py, share_store.py, cache.py.
"""

from __future__ import annotations

import hashlib
import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

from config import REDIS_URL

logger = logging.getLogger("travel_agent.geocode")

_TTL_SECONDS: int = 180 * 86_400  # 180 days


def _cache_key(query: str) -> str:
    """Hash the normalized query to a stable cache key."""
    normalized = query.lower().strip()
    return f"geocode:{hashlib.sha256(normalized.encode()).hexdigest()[:16]}"


class GeocodeCache:
    """Redis-backed geocode cache with in-memory fallback."""

    def __init__(self) -> None:
        self._redis: Redis | None = None
        self._mem: dict[str, dict[str, float]] = {}

    async def _get_redis(self) -> Redis | None:
        if self._redis is None:
            try:
                self._redis = Redis.from_url(REDIS_URL, decode_responses=True)
                await self._redis.ping()
                logger.info("GeocodeCache connected to Redis at %s", REDIS_URL)
            except (RedisError, RuntimeError) as exc:
                logger.warning("GeocodeCache Redis unavailable — using in-memory fallback: %s", exc)
                self._redis = None
        return self._redis

    async def get(self, query: str) -> dict | None:
        """Get cached coordinates for a query. Returns {"lat": float, "lng": float} or None."""
        key = _cache_key(query)
        r = await self._get_redis()
        if r is not None:
            try:
                data = await r.hgetall(key)
                if data and "lat" in data and "lng" in data:
                    return {"lat": float(data["lat"]), "lng": float(data["lng"])}
                return None
            except (RedisError, RuntimeError) as exc:
                logger.warning("GeocodeCache get Redis error — falling back: %s", exc)

        # In-memory fallback
        return self._mem.get(key)

    async def set(self, query: str, lat: float, lng: float) -> None:
        """Cache coordinates for a query."""
        key = _cache_key(query)
        r = await self._get_redis()
        if r is not None:
            try:
                await r.hset(key, mapping={"lat": str(lat), "lng": str(lng)})
                await r.expire(key, _TTL_SECONDS)
                return
            except (RedisError, RuntimeError) as exc:
                logger.warning("GeocodeCache set Redis error — falling back: %s", exc)

        # In-memory fallback
        self._mem[key] = {"lat": lat, "lng": lng}


geocode_cache = GeocodeCache()
