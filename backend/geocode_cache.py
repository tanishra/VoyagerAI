"""Geocode cache — Redis-backed with in-memory fallback.

Caches geocoding results (lat/lng for location strings) so we only hit
Nominatim once per unique location. Uses a 180-day TTL to allow eventual
data refresh without re-geocoding on every itinerary render.

Same graceful degradation pattern as threads.py, share_store.py, cache.py.
"""

from __future__ import annotations

import hashlib
import logging
import time

from redis.asyncio import Redis
from redis.exceptions import RedisError

from config import REDIS_URL
from sqlite_fallback import get_sqlite_connection

logger = logging.getLogger("travel_agent.geocode")

_TTL_SECONDS: int = 180 * 86_400  # 180 days


def _cache_key(query: str) -> str:
    """Hash the normalized query to a stable cache key."""
    normalized = query.lower().strip()
    return f"geocode:{hashlib.sha256(normalized.encode()).hexdigest()[:16]}"


class GeocodeCache:
    """Redis-backed geocode cache with SQLite + in-memory fallback."""

    def __init__(self) -> None:
        self._redis: Redis | None = None
        self._mem: dict[str, dict[str, float]] = {}

    async def _get_redis(self) -> Redis | None:
        if self._redis is None:
            try:
                self._redis = Redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)
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
            except (RedisError, RuntimeError) as exc:
                logger.warning("GeocodeCache get Redis error: %s", exc)

        # SQLite fallback
        db = await get_sqlite_connection()
        if db is not None:
            try:
                cur = await db.execute(
                    "SELECT lat, lng FROM geocode_cache WHERE query_hash = ?", (key,)
                )
                row = await cur.fetchone()
                if row:
                    return {"lat": float(row["lat"]), "lng": float(row["lng"])}
            except Exception as exc:  # noqa: BLE001
                logger.warning("GeocodeCache get SQLite error — falling back: %s", exc)

        # In-memory fallback
        entry = self._mem.get(key)
        if entry is None:
            return None
        if entry.get("_exp", 0) <= time.time():
            del self._mem[key]
            return None
        return {"lat": entry["lat"], "lng": entry["lng"]}

    async def set(self, query: str, lat: float, lng: float) -> None:
        """Cache coordinates for a query."""
        key = _cache_key(query)
        persisted = False

        r = await self._get_redis()
        if r is not None:
            try:
                await r.hset(key, mapping={"lat": str(lat), "lng": str(lng)})
                await r.expire(key, _TTL_SECONDS)
                persisted = True
            except (RedisError, RuntimeError) as exc:
                logger.warning("GeocodeCache set Redis error: %s", exc)

        # SQLite write-through (durable copy alongside Redis)
        db = await get_sqlite_connection()
        if db is not None:
            try:
                import time as _time
                await db.execute(
                    "INSERT OR REPLACE INTO geocode_cache (query_hash, lat, lng, created_at) VALUES (?, ?, ?, ?)",
                    (key, lat, lng, _time.time()),
                )
                await db.commit()
                persisted = True
            except Exception as exc:  # noqa: BLE001
                logger.warning("GeocodeCache set SQLite error: %s", exc)

        if not persisted:
            # In-memory last resort
            now = time.time()
            for k in [k for k, e in self._mem.items() if e.get("_exp", 0) <= now]:
                del self._mem[k]
            self._mem[key] = {"lat": lat, "lng": lng, "_exp": now + _TTL_SECONDS}


geocode_cache = GeocodeCache()
