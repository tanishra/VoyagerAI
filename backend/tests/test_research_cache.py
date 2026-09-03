"""Tests for research cache — in-memory fallback mode."""

from __future__ import annotations

import asyncio
import time

import pytest

from research_cache import ResearchCache


class TestResearchCache:
    @pytest.fixture
    def cache(self) -> ResearchCache:
        return ResearchCache()

    def test_cache_miss_returns_none(self, cache: ResearchCache):
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(cache.get("nonexistent_key"))
        assert result is None

    def test_cache_set_then_get(self, cache: ResearchCache):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(cache.set("key1", "cached result text"))
        result = loop.run_until_complete(cache.get("key1"))
        assert result == "cached result text"

    def test_cache_ttl_expiry(self, cache: ResearchCache):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(cache.set("key2", "expires soon", ttl=1))
        result = loop.run_until_complete(cache.get("key2"))
        assert result == "expires soon"

        time.sleep(1.1)
        result = loop.run_until_complete(cache.get("key2"))
        assert result is None

    def test_cache_invalidate_all(self, cache: ResearchCache):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(cache.set("key3", "result1"))
        loop.run_until_complete(cache.set("key4", "result2"))
        loop.run_until_complete(cache.set("key5", "result3"))

        loop.run_until_complete(cache.invalidate_all())

        assert loop.run_until_complete(cache.get("key3")) is None
        assert loop.run_until_complete(cache.get("key4")) is None
        assert loop.run_until_complete(cache.get("key5")) is None

    def test_cache_invalidate_all_returns_count(self, cache: ResearchCache):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(cache.set("key6", "result1"))
        loop.run_until_complete(cache.set("key7", "result2"))
        loop.run_until_complete(cache.set("key8", "result3"))

        count = loop.run_until_complete(cache.invalidate_all())
        assert count == 3

    def test_cache_stats_empty(self, cache: ResearchCache):
        loop = asyncio.get_event_loop()
        stats = loop.run_until_complete(cache.get_stats())
        assert stats["total_entries"] == 0
        assert stats["cache_hits"] == 0
        assert stats["cache_misses"] == 0
