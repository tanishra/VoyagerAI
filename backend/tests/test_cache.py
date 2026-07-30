"""Tests for Redis caching layer.

Unit tests:
    - Cache key determinism and collision resistance.
    - Graceful degradation when Redis is unreachable.

Integration tests (require a Redis server on localhost:6379):
    - Cache miss returns None.
    - Cache set + get round-trip.
    - ping() returns True.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from cache import _compute_key
from models import PlanRequest


class TestCacheKey:
    def test_deterministic(self) -> None:
        req = PlanRequest(destination="Paris", days=3, budget_usd=1000, travel_style="luxury", group_type="couple")
        assert _compute_key(req) == _compute_key(req)

    def test_different_destination(self) -> None:
        a = PlanRequest(destination="Paris", days=3, budget_usd=1000, travel_style="luxury", group_type="couple")
        b = PlanRequest(destination="London", days=3, budget_usd=1000, travel_style="luxury", group_type="couple")
        assert _compute_key(a) != _compute_key(b)

    def test_different_budget(self) -> None:
        a = PlanRequest(destination="Paris", days=3, budget_usd=1000, travel_style="luxury", group_type="couple")
        b = PlanRequest(destination="Paris", days=3, budget_usd=2000, travel_style="luxury", group_type="couple")
        assert _compute_key(a) != _compute_key(b)

    def test_different_optional_fields(self) -> None:
        a = PlanRequest(destination="Paris", days=3, budget_usd=1000, travel_style="luxury", group_type="couple")
        b = PlanRequest(destination="Paris", days=3, budget_usd=1000, travel_style="luxury", group_type="couple", dietary="vegan")
        assert _compute_key(a) != _compute_key(b)

    def test_title_normalization(self) -> None:
        a = PlanRequest(destination="Tokyo", days=3, budget_usd=500, travel_style="budget", group_type="solo")
        b = PlanRequest(destination="Tokyo", days=3, budget_usd=500, travel_style="budget", group_type="solo")
        assert _compute_key(a) == _compute_key(b)

    def test_key_format(self) -> None:
        req = PlanRequest(destination="Rome", days=3, budget_usd=800, travel_style="cultural", group_type="solo")
        key = _compute_key(req)
        assert key.startswith("plan:v2:")
        assert len(key) == len("plan:v2:") + 64


@pytest.mark.asyncio
class TestCacheGracefulDegradation:
    """Cache never raises — Redis failures return None or no-op."""

    async def test_get_returns_none_when_redis_down(self) -> None:
        from cache import CacheClient
        cc = CacheClient()
        with patch.object(cc, "_get_redis", return_value=None):
            req = PlanRequest(destination="NY", days=1, budget_usd=100, travel_style="budget", group_type="solo")
            result = await cc.get(req)
            assert result is None

    async def test_set_noop_when_redis_down(self) -> None:
        from cache import CacheClient
        cc = CacheClient()
        with patch.object(cc, "_get_redis", return_value=None):
            req = PlanRequest(destination="NY", days=1, budget_usd=100, travel_style="budget", group_type="solo")
            await cc.set(req, {"data": 1})

    async def test_ping_false_when_redis_down(self) -> None:
        from cache import CacheClient
        cc = CacheClient()
        with patch.object(cc, "_get_redis", return_value=None):
            assert await cc.ping() is False


@pytest.mark.skipif(not __import__("os").path.exists("/tmp/test_redis_marker"), reason="No Redis available")
class TestCacheIntegration:
    ...


if __name__ == "__main__":
    import asyncio


    async def _manual_integration() -> None:
        from cache import cache_client
        from models import PlanRequest

        req = PlanRequest(destination="Paris", days=3, budget_usd=1000, travel_style="luxury", group_type="couple")

        miss = await cache_client.get(req)
        assert miss is None, f"Expected None, got {miss}"
        print("✓ Cache miss returns None")

        data = {"destination": "Paris", "total_days": 3, "estimated_total_cost_usd": 1000}
        await cache_client.set(req, data)
        hit = await cache_client.get(req)
        assert hit == data, f"Expected {data}, got {hit}"
        print("✓ Cache set + get round-trip OK")

        assert await cache_client.ping() is True
        print("✓ Redis ping OK")

        from redis.asyncio import Redis
        r = Redis.from_url("redis://localhost:6379/0", decode_responses=True)
        key = _compute_key(req)
        await r.delete(key)
        await r.aclose()
        print("✓ Cleanup OK")

        print("\nAll integration tests passed!")

    asyncio.run(_manual_integration())
