"""Tests for geocoding cache, service, and itinerary enrichment.

Uses in-memory GeocodeCache (no Redis required) and mocked httpx calls.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from geocode_cache import GeocodeCache

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fresh_cache():
    """A GeocodeCache with no Redis connection — uses in-memory fallback."""
    cache = GeocodeCache()
    cache._redis = None
    return cache


def _make_itinerary(destination="Paris, France"):
    return {
        "destination": destination,
        "total_days": 2,
        "estimated_total_cost_usd": 800,
        "budget_status": "within",
        "visa_note": "Schengen",
        "best_season_note": "Spring",
        "days": [
            {
                "day": 1,
                "theme": "Arrival",
                "morning": {"activity": "Check-in", "location": "Hotel Marais", "cost_usd": 0, "duration": "1h"},
                "afternoon": {"activity": "Eiffel Tower", "location": "Champ de Mars", "cost_usd": 30, "duration": "3h"},
                "evening": {"activity": "Dinner", "location": "Le Bistro", "cost_usd": 50, "duration": "2h"},
                "transport": "Metro",
                "accommodation": "Hotel",
                "daily_cost_usd": 400,
                "tips": [],
            },
            {
                "day": 2,
                "theme": "Art",
                "morning": {"activity": "Louvre", "location": "Rue de Rivoli", "cost_usd": 17, "duration": "3h"},
                "afternoon": {"activity": "Montmartre", "location": "Butte Montmartre", "cost_usd": 0, "duration": "2h"},
                "evening": {"activity": "Show", "location": "Moulin Rouge", "cost_usd": 120, "duration": "3h"},
                "transport": "Metro",
                "accommodation": "Hotel",
                "daily_cost_usd": 400,
                "tips": [],
            },
        ],
        "warnings": [],
        "packing_essentials": [],
    }


# ---------------------------------------------------------------------------
# GeocodeCache unit tests
# ---------------------------------------------------------------------------


class TestGeocodeCache:
    @pytest.mark.asyncio
    async def test_set_and_get(self, fresh_cache):
        await fresh_cache.set("Eiffel Tower, Paris", 48.8584, 2.2945)
        result = await fresh_cache.get("Eiffel Tower, Paris")
        assert result is not None
        assert result["lat"] == pytest.approx(48.8584)
        assert result["lng"] == pytest.approx(2.2945)

    @pytest.mark.asyncio
    async def test_get_miss_returns_none(self, fresh_cache):
        result = await fresh_cache.get("Nonexistent Place, Nowhere")
        assert result is None

    @pytest.mark.asyncio
    async def test_case_insensitive_key(self, fresh_cache):
        await fresh_cache.set("Eiffel Tower, Paris", 48.8584, 2.2945)
        result = await fresh_cache.get("eiffel tower, paris")
        assert result is not None
        assert result["lat"] == pytest.approx(48.8584)


# ---------------------------------------------------------------------------
# geocode_service tests
# ---------------------------------------------------------------------------


class TestGeocodeService:
    @pytest.mark.asyncio
    async def test_geocode_cache_hit_skips_http(self, fresh_cache):
        """When cache has the result, no HTTP call is made."""
        await fresh_cache.set("Eiffel Tower, Paris, France", 48.8584, 2.2945)

        with (
            patch("geocode_service.geocode_cache", fresh_cache),
            patch("geocode_service.httpx.AsyncClient") as mock_client_cls,
        ):
            from geocode_service import geocode

            result = await geocode("Eiffel Tower, Paris, France")
            assert result is not None
            assert result["lat"] == pytest.approx(48.8584)
            # httpx.AsyncClient should never have been instantiated
            mock_client_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_geocode_success(self, fresh_cache):
        """Cache miss → Nominatim returns a result → cached and returned."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"lat": "48.8584", "lon": "2.2945"}]

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("geocode_service.geocode_cache", fresh_cache),
            patch("geocode_service.httpx.AsyncClient", return_value=mock_client),
            patch("geocode_service._throttle", new_callable=AsyncMock),
        ):
            from geocode_service import geocode

            result = await geocode("Eiffel Tower, Paris, France")
            assert result is not None
            assert result["lat"] == pytest.approx(48.8584)
            assert result["lng"] == pytest.approx(2.2945)

            # Verify it was cached
            cached = await fresh_cache.get("Eiffel Tower, Paris, France")
            assert cached is not None
            assert cached["lat"] == pytest.approx(48.8584)

    @pytest.mark.asyncio
    async def test_geocode_empty_results(self, fresh_cache):
        """Nominatim returns empty list → None."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("geocode_service.geocode_cache", fresh_cache),
            patch("geocode_service.httpx.AsyncClient", return_value=mock_client),
            patch("geocode_service._throttle", new_callable=AsyncMock),
        ):
            from geocode_service import geocode

            result = await geocode("Nowhere, Antarctica")
            assert result is None

    @pytest.mark.asyncio
    async def test_geocode_non_200(self, fresh_cache):
        """Nominatim returns 503 → None."""
        mock_response = MagicMock()
        mock_response.status_code = 503

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("geocode_service.geocode_cache", fresh_cache),
            patch("geocode_service.httpx.AsyncClient", return_value=mock_client),
            patch("geocode_service._throttle", new_callable=AsyncMock),
        ):
            from geocode_service import geocode

            result = await geocode("Some Place, Some City")
            assert result is None

    @pytest.mark.asyncio
    async def test_geocode_exception_returns_none(self, fresh_cache):
        """httpx raises → None, never propagates."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("network error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("geocode_service.geocode_cache", fresh_cache),
            patch("geocode_service.httpx.AsyncClient", return_value=mock_client),
            patch("geocode_service._throttle", new_callable=AsyncMock),
        ):
            from geocode_service import geocode

            result = await geocode("Some Place, Some City")
            assert result is None

    @pytest.mark.asyncio
    async def test_geocode_empty_query_returns_none(self, fresh_cache):
        with patch("geocode_service.geocode_cache", fresh_cache):
            from geocode_service import geocode

            result = await geocode("")
            assert result is None

    @pytest.mark.asyncio
    async def test_throttle_enforces_interval(self):
        """Two rapid calls to _throttle should wait at least 1.1s total."""
        from geocode_service import _MIN_INTERVAL, _throttle

        sleep_calls: list[float] = []

        async def mock_sleep(seconds):
            sleep_calls.append(seconds)

        # Reset throttle state
        with (
            patch("geocode_service.asyncio.sleep", mock_sleep),
            patch("geocode_service._last_nominatim_call", 0.0),
        ):
            await _throttle()
            await _throttle()

        # Second call should have waited approximately _MIN_INTERVAL
        assert len(sleep_calls) >= 1
        assert sleep_calls[-1] <= _MIN_INTERVAL
        assert sleep_calls[-1] > 0


# ---------------------------------------------------------------------------
# _enrich_itinerary_with_coordinates tests
# ---------------------------------------------------------------------------


class TestEnrichItinerary:
    @pytest.mark.asyncio
    async def test_enrich_adds_coordinates(self):
        """All 6 slots geocoded → all have lat/lng."""
        from agents.deep_agent import _enrich_itinerary_with_coordinates

        itinerary = _make_itinerary()

        async def mock_geocode(query):
            return {"lat": 48.85, "lng": 2.35}

        with patch("agents.deep_agent.geocode", new=mock_geocode):
            enriched = await _enrich_itinerary_with_coordinates(itinerary)

        for day in enriched["days"]:
            for slot_key in ("morning", "afternoon", "evening"):
                slot = day[slot_key]
                assert "lat" in slot
                assert "lng" in slot
                assert slot["lat"] == pytest.approx(48.85)
                assert slot["lng"] == pytest.approx(2.35)

    @pytest.mark.asyncio
    async def test_enrich_partial_failure(self):
        """Some geocode calls return None → those slots lack lat/lng, others have them."""
        from agents.deep_agent import _enrich_itinerary_with_coordinates

        itinerary = _make_itinerary()

        call_count = 0

        async def mock_geocode(query):
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                return None
            return {"lat": 48.85, "lng": 2.35}

        with patch("agents.deep_agent.geocode", new=mock_geocode):
            enriched = await _enrich_itinerary_with_coordinates(itinerary)

        # Original itinerary should not be mutated
        assert "lat" not in itinerary["days"][0]["morning"]

        # Enriched should have some slots with coords and some without
        slots_with_coords = 0
        slots_without = 0
        for day in enriched["days"]:
            for slot_key in ("morning", "afternoon", "evening"):
                if "lat" in day[slot_key]:
                    slots_with_coords += 1
                else:
                    slots_without += 1

        assert slots_with_coords > 0
        assert slots_without > 0

    @pytest.mark.asyncio
    async def test_enrich_all_fail(self):
        """All geocode calls return None → itinerary unchanged (no lat/lng anywhere)."""
        from agents.deep_agent import _enrich_itinerary_with_coordinates

        itinerary = _make_itinerary()

        async def mock_geocode(query):
            return None

        with patch("agents.deep_agent.geocode", new=mock_geocode):
            enriched = await _enrich_itinerary_with_coordinates(itinerary)

        for day in enriched["days"]:
            for slot_key in ("morning", "afternoon", "evening"):
                assert "lat" not in day[slot_key]
                assert "lng" not in day[slot_key]

    @pytest.mark.asyncio
    async def test_enrich_does_not_mutate_original(self):
        """The original itinerary dict should be untouched."""
        from agents.deep_agent import _enrich_itinerary_with_coordinates

        itinerary = _make_itinerary()

        async def mock_geocode(query):
            return {"lat": 48.85, "lng": 2.35}

        with patch("agents.deep_agent.geocode", new=mock_geocode):
            await _enrich_itinerary_with_coordinates(itinerary)

        assert "lat" not in itinerary["days"][0]["morning"]

    @pytest.mark.asyncio
    async def test_enrich_exception_returns_original(self):
        """If geocode raises, enrichment returns the original itinerary unchanged."""
        from agents.deep_agent import _enrich_itinerary_with_coordinates

        itinerary = _make_itinerary()

        async def mock_geocode(query):
            raise RuntimeError("unexpected error")

        with patch("agents.deep_agent.geocode", new=mock_geocode):
            enriched = await _enrich_itinerary_with_coordinates(itinerary)

        # Should return the original itinerary (no coords)
        assert "lat" not in enriched["days"][0]["morning"]
