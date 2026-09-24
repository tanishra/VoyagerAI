"""Geocoding service — Nominatim (OpenStreetMap) with Redis caching.

Geocodes location strings (e.g. "Eiffel Tower, Paris") to lat/lng coordinates.
Uses the free Nominatim API with a process-wide throttle (≥1.1s between calls)
per their usage policy. Results are cached in Redis (180-day TTL) via
geocode_cache so we only hit Nominatim once per unique location.

On any failure (timeout, non-200, no results) returns None — never raises.
"""

from __future__ import annotations

import asyncio
import logging
import time

import httpx

from geocode_cache import geocode_cache

logger = logging.getLogger("travel_agent.geocode")

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_USER_AGENT = "VoyagerAI/1.0 (travel itinerary planner)"
_TIMEOUT = 5.0
_MIN_INTERVAL = 1.1  # seconds between outbound Nominatim calls

# Process-wide throttle state
_throttle_lock = asyncio.Lock()
_last_nominatim_call: float = 0.0

# Negative-result cache: normalized query -> monotonic timestamp of failure.
# Repeated un-geocodable locations across itineraries shouldn't burn
# throttled Nominatim calls. Short TTL so a transient outage recovers.
_MISS_TTL = 3600.0          # "no results" / non-200 — the location likely doesn't resolve
_MISS_ERR_TTL = 300.0       # transient errors (timeout, DNS) — retry sooner
_MISS_MAX = 512
_miss_cache: dict[str, tuple[float, float]] = {}


def _miss_key(query: str) -> str:
    return query.lower().strip()


def _missed(query: str) -> bool:
    entry = _miss_cache.get(_miss_key(query))
    if entry is None:
        return False
    ts, ttl = entry
    if time.monotonic() - ts > ttl:
        del _miss_cache[_miss_key(query)]
        return False
    return True


def _record_miss(query: str, ttl: float = _MISS_TTL) -> None:
    if len(_miss_cache) >= _MISS_MAX:
        oldest = min(_miss_cache, key=lambda k: _miss_cache[k][0])
        del _miss_cache[oldest]
    _miss_cache[_miss_key(query)] = (time.monotonic(), ttl)


async def _throttle() -> None:
    """Ensure at least _MIN_INTERVAL seconds between outbound Nominatim calls."""
    global _last_nominatim_call
    async with _throttle_lock:
        now = time.monotonic()
        elapsed = now - _last_nominatim_call
        if elapsed < _MIN_INTERVAL:
            wait = _MIN_INTERVAL - elapsed
            logger.debug("Nominatim throttle: waiting %.2fs", wait)
            await asyncio.sleep(wait)
        _last_nominatim_call = time.monotonic()


async def geocode(query: str) -> dict | None:
    """Geocode a location string to {"lat": float, "lng": float} or None.

    Checks Redis cache first. On cache miss, calls Nominatim (throttled).
    Never raises — returns None on any failure.
    """
    if not query or not query.strip():
        return None

    # Known recent failure — skip the network call entirely
    if _missed(query):
        logger.debug("Geocode miss-cache hit: %s", query[:60])
        return None

    # Check cache first
    cached = await geocode_cache.get(query)
    if cached is not None:
        logger.debug("Geocode cache hit: %s → %s", query[:50], cached)
        return cached

    # Cache miss — call Nominatim
    await _throttle()

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                _NOMINATIM_URL,
                params={
                    "q": query,
                    "format": "json",
                    "limit": 1,
                    "addressdetails": 0,
                },
                headers={"User-Agent": _USER_AGENT},
            )
            if resp.status_code != 200:
                logger.warning("Nominatim returned %d for query: %s", resp.status_code, query[:80])
                _record_miss(query)
                return None

            results = resp.json()
            if not results:
                logger.debug("Nominatim: no results for query: %s", query[:80])
                _record_miss(query)
                return None

            lat = float(results[0]["lat"])
            lng = float(results[0]["lon"])
            coords = {"lat": lat, "lng": lng}
            await geocode_cache.set(query, lat, lng)
            logger.info("Geocoded: %s → (%.4f, %.4f)", query[:60], lat, lng)
            return coords

    except Exception as exc:  # noqa: BLE001
        logger.warning("Geocode failed for query '%s': %s", query[:80], exc)
        _record_miss(query, ttl=_MISS_ERR_TTL)
        return None
