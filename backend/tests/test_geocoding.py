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


@pytest.fixture(autouse=True)
def _no_google_key(monkeypatch):
    """Nominatim tests must not see a real GOOGLE_MAPS_API_KEY from .env —
    the Google-first path would consume the mocked HTTP client. Tests for
    the Google path re-patch this attribute themselves."""
    monkeypatch.setattr("geocode_service.settings.GOOGLE_MAPS_API_KEY", "")


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
    async def test_miss_cache_skips_http(self, fresh_cache):
        """A failed query is remembered — the second call makes no HTTP request."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        import geocode_service
        geocode_service._miss_cache.clear()

        with (
            patch("geocode_service.geocode_cache", fresh_cache),
            patch("geocode_service.httpx.AsyncClient", return_value=mock_client) as mock_cls,
            patch("geocode_service._throttle", new_callable=AsyncMock),
        ):
            from geocode_service import geocode

            assert await geocode("Unresolvable Spot XQZ") is None
            assert await geocode("Unresolvable Spot XQZ") is None
            # HTTP client built once — the second call short-circuited
            assert mock_cls.call_count == 1

    @pytest.mark.asyncio
    async def test_miss_cache_error_uses_short_ttl(self, fresh_cache):
        """Transient errors get the short TTL, definitive misses the long one."""
        import geocode_service

        geocode_service._miss_cache.clear()
        geocode_service._record_miss("err query", ttl=geocode_service._MISS_ERR_TTL)
        geocode_service._record_miss("empty query")

        _, err_ttl = geocode_service._miss_cache["err query"]
        _, empty_ttl = geocode_service._miss_cache["empty query"]
        assert err_ttl == geocode_service._MISS_ERR_TTL
        assert empty_ttl == geocode_service._MISS_TTL

    @pytest.mark.asyncio
    async def test_google_geocode_success_skips_nominatim(self, fresh_cache):
        """GOOGLE_MAPS_API_KEY set → Google result returned and cached, Nominatim untouched."""
        google_response = MagicMock()
        google_response.status_code = 200
        google_response.json.return_value = {
            "status": "OK",
            "results": [{"geometry": {"location": {"lat": 48.8584, "lng": 2.2945}}}],
        }

        google_client = AsyncMock()
        google_client.get = AsyncMock(return_value=google_response)
        google_client.__aenter__ = AsyncMock(return_value=google_client)
        google_client.__aexit__ = AsyncMock(return_value=None)

        import geocode_service
        geocode_service._miss_cache.clear()

        with (
            patch("geocode_service.geocode_cache", fresh_cache),
            patch("geocode_service.httpx.AsyncClient", return_value=google_client),
            patch("geocode_service.settings.GOOGLE_MAPS_API_KEY", "test-key"),
            patch("geocode_service._throttle", new_callable=AsyncMock) as mock_throttle,
        ):
            from geocode_service import geocode

            result = await geocode("Eiffel Tower, Paris, France")
            assert result == {"lat": pytest.approx(48.8584), "lng": pytest.approx(2.2945)}
            mock_throttle.assert_not_called()  # Nominatim never reached
            cached = await fresh_cache.get("Eiffel Tower, Paris, France")
            assert cached is not None

    @pytest.mark.asyncio
    async def test_google_zero_results_falls_back_to_nominatim(self, fresh_cache):
        """Google returns ZERO_RESULTS → Nominatim fallback still applies."""
        calls: list[dict] = []

        def make_client():
            client = AsyncMock()
            async def get(url, **kwargs):
                calls.append(kwargs.get("params", {}))
                resp = MagicMock()
                resp.status_code = 200
                if "maps.googleapis.com" in url:
                    resp.json.return_value = {"status": "ZERO_RESULTS", "results": []}
                else:
                    resp.json.return_value = [{"lat": "48.85", "lon": "2.35"}]
                return resp
            client.get = get
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=None)
            return client

        import geocode_service
        geocode_service._miss_cache.clear()

        with (
            patch("geocode_service.geocode_cache", fresh_cache),
            patch("geocode_service.httpx.AsyncClient", side_effect=lambda **kw: make_client()),
            patch("geocode_service.settings.GOOGLE_MAPS_API_KEY", "test-key"),
            patch("geocode_service._throttle", new_callable=AsyncMock),
        ):
            from geocode_service import geocode

            result = await geocode("Some Obscure Place, Paris")
            assert result == {"lat": pytest.approx(48.85), "lng": pytest.approx(2.35)}
            assert len(calls) == 2  # google then nominatim

    @pytest.mark.asyncio
    async def test_google_failure_falls_back_to_nominatim(self, fresh_cache):
        """Google raises → Nominatim still tried; never propagates."""
        def make_client():
            client = AsyncMock()
            async def get(url, **kwargs):
                if "maps.googleapis.com" in url:
                    raise RuntimeError("google down")
                resp = MagicMock()
                resp.status_code = 200
                resp.json.return_value = [{"lat": "40.71", "lon": "-74.0"}]
                return resp
            client.get = get
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=None)
            return client

        import geocode_service
        geocode_service._miss_cache.clear()

        with (
            patch("geocode_service.geocode_cache", fresh_cache),
            patch("geocode_service.httpx.AsyncClient", side_effect=lambda **kw: make_client()),
            patch("geocode_service.settings.GOOGLE_MAPS_API_KEY", "test-key"),
            patch("geocode_service._throttle", new_callable=AsyncMock),
        ):
            from geocode_service import geocode

            result = await geocode("Somewhere, NYC")
            assert result == {"lat": pytest.approx(40.71), "lng": pytest.approx(-74.0)}

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
    async def test_enrich_partial_failure_gets_approx_pins(self):
        """Slots whose own queries miss get the destination centroid, flagged geo_approx."""
        from agents.deep_agent import _enrich_itinerary_with_coordinates

        itinerary = _make_itinerary()

        async def mock_geocode(query):
            # Only the destination itself resolves — every slot query misses.
            if query == "Paris, France":
                return {"lat": 48.85, "lng": 2.35}
            return None

        with patch("agents.deep_agent.geocode", new=mock_geocode):
            enriched = await _enrich_itinerary_with_coordinates(itinerary)

        # Original itinerary should not be mutated
        assert "lat" not in itinerary["days"][0]["morning"]

        for day in enriched["days"]:
            for slot_key in ("morning", "afternoon", "evening"):
                slot = day[slot_key]
                assert slot["lat"] == pytest.approx(48.85)
                assert slot["lng"] == pytest.approx(2.35)
                assert slot["geo_approx"] is True

    @pytest.mark.asyncio
    async def test_enrich_activity_fallback_resolves_exact(self):
        """Primary location query misses but activity fallback hits → exact coords, no flag."""
        from agents.deep_agent import _enrich_itinerary_with_coordinates

        itinerary = _make_itinerary(destination="Paris, France")

        async def mock_geocode(query):
            if query == "Paris, France":
                return {"lat": 48.85, "lng": 2.35}
            # Location queries miss, activity fallback queries hit
            if query.startswith("Check-in,"):
                return {"lat": 48.86, "lng": 2.36}
            return None

        with patch("agents.deep_agent.geocode", new=mock_geocode):
            enriched = await _enrich_itinerary_with_coordinates(itinerary)

        morning = enriched["days"][0]["morning"]
        assert morning["lat"] == pytest.approx(48.86)
        assert morning["lng"] == pytest.approx(2.36)
        assert "geo_approx" not in morning
        # Other slots fell back to the centroid
        assert enriched["days"][0]["afternoon"]["geo_approx"] is True

    @pytest.mark.asyncio
    async def test_enrich_dedupes_queries(self):
        """Identical location strings across slots hit geocode only once."""
        from agents.deep_agent import _enrich_itinerary_with_coordinates

        itinerary = _make_itinerary()
        itinerary["days"][1]["morning"]["location"] = "Hotel Marais"  # same as day 1

        calls: list[str] = []

        async def mock_geocode(query):
            calls.append(query)
            return {"lat": 48.85, "lng": 2.35}

        with patch("agents.deep_agent.geocode", new=mock_geocode):
            await _enrich_itinerary_with_coordinates(itinerary)

        loc_queries = [c for c in calls if c.startswith("Hotel Marais")]
        assert len(loc_queries) == 1

    @pytest.mark.asyncio
    async def test_enrich_fallback_budget_caps_calls(self):
        """After the fallback budget is spent, remaining slots go straight to centroid."""
        from agents.deep_agent import _enrich_itinerary_with_coordinates

        # 6 unique slots, all unresolvable — dest hit + 5 budgeted calls max
        itinerary = _make_itinerary()

        calls: list[str] = []

        async def mock_geocode(query):
            calls.append(query)
            if query == "Paris, France":
                return {"lat": 48.85, "lng": 2.35}
            return None

        with patch("agents.deep_agent.geocode", new=mock_geocode):
            enriched = await _enrich_itinerary_with_coordinates(itinerary)

        # 1 destination call + at most 5 slot queries (budget)
        assert len(calls) <= 6
        # Every slot still got the approx centroid pin
        for day in enriched["days"]:
            for slot_key in ("morning", "afternoon", "evening"):
                assert day[slot_key].get("geo_approx") is True

    @pytest.mark.asyncio
    async def test_enrich_all_fail(self):
        """All geocode calls return None (incl. destination) → no lat/lng anywhere."""
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
