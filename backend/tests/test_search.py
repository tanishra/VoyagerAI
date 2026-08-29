"""Tests for thread search functionality."""

from __future__ import annotations

import pytest

from threads import ThreadStore


@pytest.fixture
def fresh_store():
    """A ThreadStore with no Redis connection — uses in-memory fallback."""
    store = ThreadStore()
    store._redis = None
    return store


class TestSearchThreads:
    @pytest.mark.asyncio
    async def test_search_by_destination(self, fresh_store):
        """Search by destination finds matching thread."""
        store = fresh_store
        await store.upsert_thread(
            "user1", "thread:t1", "Tokyo trip",
            search_text="Plan a 3-day Tokyo trip with sushi and temples",
        )
        await store.upsert_thread(
            "user1", "thread:t2", "Paris weekend",
            search_text="Weekend in Paris with museum visits",
        )
        results, total = await store.search_threads("user1", "tokyo")
        assert total == 1
        assert results[0]["thread_id"] == "thread:t1"
        assert "tokyo" in results[0]["snippet"].lower()

    @pytest.mark.asyncio
    async def test_search_by_activity(self, fresh_store):
        """Search by activity keyword finds matching thread."""
        store = fresh_store
        await store.upsert_thread(
            "user1", "thread:t1", "Switzerland trip",
            search_text="Hiking in the Swiss Alps near Interlaken",
        )
        await store.upsert_thread(
            "user1", "thread:t2", "Beach vacation",
            search_text="Relaxing beach vacation in Bali",
        )
        results, total = await store.search_threads("user1", "hiking")
        assert total == 1
        assert results[0]["thread_id"] == "thread:t1"
        assert "hiking" in results[0]["snippet"].lower()

    @pytest.mark.asyncio
    async def test_search_no_results(self, fresh_store):
        """Search with no matches returns empty results."""
        store = fresh_store
        await store.upsert_thread(
            "user1", "thread:t1", "Tokyo trip",
            search_text="Plan a trip to Tokyo",
        )
        results, total = await store.search_threads("user1", "xyz123nonexistent")
        assert total == 0
        assert results == []

    @pytest.mark.asyncio
    async def test_search_pagination(self, fresh_store):
        """Search results are paginated correctly."""
        store = fresh_store
        for i in range(25):
            await store.upsert_thread(
                "user1", f"thread:t{i}", f"Trip {i}",
                search_text=f"Plan a hiking trip number {i}",
            )
        # First page
        results, total = await store.search_threads("user1", "hiking", limit=10, offset=0)
        assert total == 25
        assert len(results) == 10
        # Last page
        results, total = await store.search_threads("user1", "hiking", limit=10, offset=20)
        assert total == 25
        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_search_case_insensitive(self, fresh_store):
        """Search is case-insensitive."""
        store = fresh_store
        await store.upsert_thread(
            "user1", "thread:t1", "Tokyo trip",
            search_text="Plan a trip to Tokyo with temple visits",
        )
        results, total = await store.search_threads("user1", "TOKYO")
        assert total == 1
        assert results[0]["thread_id"] == "thread:t1"

    @pytest.mark.asyncio
    async def test_search_user_isolation(self, fresh_store):
        """Search only returns threads belonging to the searching user."""
        store = fresh_store
        await store.upsert_thread(
            "user1", "thread:t1", "Tokyo trip",
            search_text="Plan a trip to Tokyo",
        )
        await store.upsert_thread(
            "user2", "thread:t2", "Tokyo trip",
            search_text="Plan a trip to Tokyo",
        )
        results, total = await store.search_threads("user1", "tokyo")
        assert total == 1
        assert results[0]["thread_id"] == "thread:t1"

    @pytest.mark.asyncio
    async def test_search_empty_query(self, fresh_store):
        """Empty query returns all threads (endpoint guards against this)."""
        store = fresh_store
        await store.upsert_thread(
            "user1", "thread:t1", "Tokyo trip",
            search_text="Plan a trip to Tokyo",
        )
        results, total = await store.search_threads("user1", "")
        # Store returns all for empty string; endpoint-level guard prevents this
        assert total == 1

    @pytest.mark.asyncio
    async def test_search_preserves_existing_search_text(self, fresh_store):
        """upsert_thread without search_text preserves existing value."""
        store = fresh_store
        await store.upsert_thread(
            "user1", "thread:t1", "Tokyo trip",
            search_text="Plan a trip to Tokyo",
        )
        # Update without search_text — should preserve
        await store.upsert_thread(
            "user1", "thread:t1", "Tokyo trip updated",
        )
        results, total = await store.search_threads("user1", "tokyo")
        assert total == 1
        assert results[0]["thread_id"] == "thread:t1"
