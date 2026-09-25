"""Tests for weather_service — Open-Meteo enrichment. HTTP is mocked."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import weather_service

# conftest stubs weather_service.enrich_itinerary_weather for the whole suite;
# this module tests the real implementation, so bind it before the patch.
_enrich = weather_service.enrich_itinerary_weather


def _reset_memo():
    weather_service._memo.clear()


def _itinerary(day_dates):
    days = []
    for i, d in enumerate(day_dates, start=1):
        day = {"day": i, "weather": "AI guess"}
        if d is not None:
            day["date"] = d
        day["morning"] = {"activity": "a", "lat": 48.85, "lng": 2.35}
        days.append(day)
    return {"destination": "Paris", "days": days}


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _payload(dates):
    return {
        "daily": {
            "time": dates,
            "temperature_2m_max": [24.3] * len(dates),
            "precipitation_probability_max": [70] * len(dates),
            "weather_code": [61] * len(dates),
        }
    }


def _mock_client(monkeypatch, payload=None, raises=False):
    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def get(self, *a, **k):
            if raises:
                raise RuntimeError("network down")
            return _Resp(payload)

    monkeypatch.setattr(weather_service.httpx, "AsyncClient", lambda **k: _Client())


class TestFetchDailyForecast:
    def test_maps_response(self, monkeypatch):
        _reset_memo()
        _mock_client(monkeypatch, _payload(["2026-09-25", "2026-09-26"]))
        out = asyncio.run(weather_service.fetch_daily_forecast(48.85, 2.35))
        assert out["2026-09-25"]["tmax"] == 24.3
        assert out["2026-09-25"]["code"] == 61

    def test_failure_returns_empty(self, monkeypatch):
        _reset_memo()
        _mock_client(monkeypatch, raises=True)
        assert asyncio.run(weather_service.fetch_daily_forecast(48.85, 2.35)) == {}

    def test_memo_caches(self, monkeypatch):
        _reset_memo()
        calls = []

        class _Client:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return None

            async def get(self, *a, **k):
                calls.append(1)
                return _Resp(_payload(["2026-09-25"]))

        monkeypatch.setattr(weather_service.httpx, "AsyncClient", lambda **k: _Client())
        asyncio.run(weather_service.fetch_daily_forecast(48.85, 2.35))
        asyncio.run(weather_service.fetch_daily_forecast(48.85, 2.35))
        assert len(calls) == 1


class TestEnrichItineraryWeather:
    def test_real_weather_applied(self, monkeypatch):
        _reset_memo()
        today = datetime.now(timezone.utc).date().isoformat()
        _mock_client(monkeypatch, _payload([today]))
        it = _itinerary([today])
        asyncio.run(_enrich(it))
        assert it["days"][0]["weather"] == "24°C rain · rain 70%"

    def test_no_date_keeps_model_text(self, monkeypatch):
        _reset_memo()
        _mock_client(monkeypatch, _payload([datetime.now(timezone.utc).date().isoformat()]))
        it = _itinerary([None])
        asyncio.run(_enrich(it))
        assert it["days"][0]["weather"] == "AI guess"

    def test_out_of_window_keeps_model_text(self, monkeypatch):
        _reset_memo()
        far = (datetime.now(timezone.utc).date() + timedelta(days=60)).isoformat()
        _mock_client(monkeypatch, _payload([datetime.now(timezone.utc).date().isoformat()]))
        it = _itinerary([far])
        asyncio.run(_enrich(it))
        assert it["days"][0]["weather"] == "AI guess"

    def test_api_failure_keeps_model_text(self, monkeypatch):
        _reset_memo()
        _mock_client(monkeypatch, raises=True)
        it = _itinerary([datetime.now(timezone.utc).date().isoformat()])
        asyncio.run(_enrich(it))
        assert it["days"][0]["weather"] == "AI guess"

    def test_no_coords_skips_fetch(self, monkeypatch):
        _reset_memo()
        _mock_client(monkeypatch, _payload([datetime.now(timezone.utc).date().isoformat()]))
        it = {"destination": "Nowhere", "days": [{"day": 1, "date": datetime.now(timezone.utc).date().isoformat(), "weather": "AI guess"}]}
        asyncio.run(_enrich(it))
        assert it["days"][0]["weather"] == "AI guess"
