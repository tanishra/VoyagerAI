"""Real-weather enrichment via Open-Meteo (free, no API key).

Fetches a 16-day daily forecast for the trip's anchor coordinates once per
itinerary and rewrites ``day["weather"]`` for days whose ``date`` falls inside
the forecast window. Days without a date, dates beyond the window, and any
fetch failure all leave the model-generated weather text untouched — the
enrichment is strictly best-effort.
"""

from __future__ import annotations

import logging
import time

import httpx

logger = logging.getLogger("travel_agent.weather")

_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
_FORECAST_DAYS = 16
_TIMEOUT_S = 5.0
_CACHE_TTL_S = 3600.0

# {(lat_r, lng_r): (fetched_at, {date_str: {...}})} — one call per destination
# per hour; forecasts are cheap and regenerate/edit paths reuse the result.
_memo: dict[tuple[float, float], tuple[float, dict[str, dict]]] = {}

# WMO weather codes → short chip labels.
_CODE_LABELS = {
    0: "clear",
    1: "mostly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "fog",
    51: "drizzle",
    53: "drizzle",
    55: "drizzle",
    56: "freezing drizzle",
    57: "freezing drizzle",
    61: "rain",
    63: "rain",
    65: "heavy rain",
    66: "freezing rain",
    67: "freezing rain",
    71: "snow",
    73: "snow",
    75: "heavy snow",
    77: "snow",
    80: "showers",
    81: "showers",
    82: "heavy showers",
    85: "snow showers",
    86: "snow showers",
    95: "thunderstorm",
    96: "thunderstorm",
    99: "thunderstorm",
}


async def fetch_daily_forecast(lat: float, lng: float) -> dict[str, dict]:
    """Return {date_str: {tmax, precip_prob, code}} for the next 16 days.

    Never raises — returns {} on any failure (network, shape, timeout).
    """
    key = (round(lat, 1), round(lng, 1))
    cached = _memo.get(key)
    if cached and time.time() - cached[0] < _CACHE_TTL_S:
        return cached[1]

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
            resp = await client.get(
                _FORECAST_URL,
                params={
                    "latitude": lat,
                    "longitude": lng,
                    "daily": "temperature_2m_max,precipitation_probability_max,weather_code",
                    "timezone": "auto",
                    "forecast_days": _FORECAST_DAYS,
                },
            )
            resp.raise_for_status()
            daily = resp.json().get("daily") or {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Open-Meteo fetch failed: %s", exc)
        return {}

    dates = daily.get("time") or []
    tmaxes = daily.get("temperature_2m_max") or []
    probs = daily.get("precipitation_probability_max") or []
    codes = daily.get("weather_code") or daily.get("weathercode") or []

    out: dict[str, dict] = {}
    for i, date_str in enumerate(dates):
        try:
            out[date_str] = {
                "tmax": tmaxes[i],
                "precip_prob": probs[i] if i < len(probs) else None,
                "code": codes[i] if i < len(codes) else None,
            }
        except (IndexError, TypeError):
            continue

    if out:
        _memo[key] = (time.time(), out)
    return out


def _format_chip(entry: dict) -> str | None:
    tmax = entry.get("tmax")
    if not isinstance(tmax, (int, float)):
        return None
    label = _CODE_LABELS.get(entry.get("code"), "mixed")
    chip = f"{tmax:.0f}°C {label}"
    prob = entry.get("precip_prob")
    if isinstance(prob, (int, float)) and prob >= 50:
        chip += f" · rain {prob:.0f}%"
    return chip


def _anchor_coords(itinerary: dict) -> tuple[float, float] | None:
    """Mean of slots with exact (non-approximate) coordinates."""
    lats: list[float] = []
    lngs: list[float] = []
    for day in itinerary.get("days") or []:
        if not isinstance(day, dict):
            continue
        for slot_key in ("morning", "afternoon", "evening"):
            slot = day.get(slot_key)
            if not isinstance(slot, dict) or slot.get("geo_approx"):
                continue
            lat, lng = slot.get("lat"), slot.get("lng")
            if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
                lats.append(lat)
                lngs.append(lng)
    if not lats:
        return None
    return sum(lats) / len(lats), sum(lngs) / len(lngs)


async def enrich_itinerary_weather(itinerary: dict) -> dict:
    """Rewrite day.weather with a real forecast chip when the date is known.

    Mutates and returns the same dict. Never raises.
    """
    try:
        from ical_generator import _parse_day_date

        anchor = _anchor_coords(itinerary)
        if anchor is None:
            return itinerary
        forecast = await fetch_daily_forecast(*anchor)
        if not forecast:
            return itinerary

        updated = 0
        for day in itinerary.get("days") or []:
            if not isinstance(day, dict):
                continue
            parsed = _parse_day_date(day.get("date"))
            if parsed is None:
                continue
            date_str = f"{parsed[0]:04d}-{parsed[1]:02d}-{parsed[2]:02d}"
            entry = forecast.get(date_str)
            if entry is None:
                continue
            chip = _format_chip(entry)
            if chip:
                day["weather"] = chip
                updated += 1
        if updated:
            logger.info("Real weather applied to %d days", updated)
        return itinerary
    except Exception:
        logger.warning("Weather enrichment failed", exc_info=True)
        return itinerary
