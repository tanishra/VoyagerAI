"""Tests for research cache — in-memory fallback mode."""

from __future__ import annotations

import asyncio
import time

import pytest

from research_cache import ResearchCache


class TestResearchCache:
    @pytest.fixture
    def cache(self, monkeypatch) -> ResearchCache:
        c = ResearchCache()
        c._redis = None
        async def _no_redis():
            return None
        monkeypatch.setattr(c, "_get_redis", _no_redis)
        import research_cache as rc_module
        async def _no_sqlite():
            return None
        monkeypatch.setattr(rc_module, "get_sqlite_connection", _no_sqlite)
        asyncio.run(c.invalidate_all())
        return c

    def test_cache_miss_returns_none(self, cache: ResearchCache):
        result = asyncio.run(cache.get("nonexistent_key"))
        assert result is None

    def test_cache_set_then_get(self, cache: ResearchCache):
        asyncio.run(cache.set("key1", "cached result text"))
        result = asyncio.run(cache.get("key1"))
        assert result == "cached result text"

    def test_cache_ttl_expiry(self, cache: ResearchCache):
        asyncio.run(cache.set("key2", "expires soon", ttl=1))
        result = asyncio.run(cache.get("key2"))
        assert result == "expires soon"

        time.sleep(1.1)
        result = asyncio.run(cache.get("key2"))
        assert result is None

    def test_cache_invalidate_all(self, cache: ResearchCache):
        asyncio.run(cache.set("key3", "result1"))
        asyncio.run(cache.set("key4", "result2"))
        asyncio.run(cache.set("key5", "result3"))

        asyncio.run(cache.invalidate_all())

        assert asyncio.run(cache.get("key3")) is None
        assert asyncio.run(cache.get("key4")) is None
        assert asyncio.run(cache.get("key5")) is None

    def test_cache_invalidate_all_returns_count(self, cache: ResearchCache):
        asyncio.run(cache.set("key6", "result1"))
        asyncio.run(cache.set("key7", "result2"))
        asyncio.run(cache.set("key8", "result3"))

        count = asyncio.run(cache.invalidate_all())
        assert count == 3

    def test_cache_stats_empty(self, cache: ResearchCache):
        stats = asyncio.run(cache.get_stats())
        assert stats["total_entries"] == 0
        assert stats["cache_hits"] == 0
        assert stats["cache_misses"] == 0
