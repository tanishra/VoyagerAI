"""Tests for feedback store — in-memory fallback mode."""

from __future__ import annotations

import asyncio

import pytest

from feedback_store import FeedbackStore


class TestFeedbackStore:
    @pytest.fixture
    def store(self, monkeypatch) -> FeedbackStore:
        s = FeedbackStore()
        s._redis = None
        async def _no_redis():
            return None
        monkeypatch.setattr(s, "_get_redis", _no_redis)
        import feedback_store as fb_module
        async def _no_sqlite():
            return None
        monkeypatch.setattr(fb_module, "get_durable_db", _no_sqlite)
        return s

    def test_submit_feedback_stores_rating(self, store: FeedbackStore):
        result = asyncio.run(store.submit_feedback("user1", "msg1", "thread1", "up"))
        assert result == {"status": "ok", "rating": "up"}

        feedback = asyncio.run(store.get_feedback("user1", "msg1"))
        assert feedback is not None
        assert feedback["rating"] == "up"
        assert feedback["thread_id"] == "thread1"

    def test_submit_feedback_overwrites(self, store: FeedbackStore):
        asyncio.run(store.submit_feedback("user1", "msg1", "thread1", "up"))
        asyncio.run(store.submit_feedback("user1", "msg1", "thread1", "down", "Bad response"))

        feedback = asyncio.run(store.get_feedback("user1", "msg1"))
        assert feedback is not None
        assert feedback["rating"] == "down"
        assert feedback["comment"] == "Bad response"

    def test_submit_feedback_with_comment(self, store: FeedbackStore):
        asyncio.run(store.submit_feedback("user1", "msg1", "thread1", "down", "Itinerary was wrong"))

        feedback = asyncio.run(store.get_feedback("user1", "msg1"))
        assert feedback is not None
        assert feedback["comment"] == "Itinerary was wrong"

    def test_get_feedback_not_found(self, store: FeedbackStore):
        feedback = asyncio.run(store.get_feedback("unknown", "unknown"))
        assert feedback is None

    def test_get_aggregate_stats_counts(self, store: FeedbackStore):
        asyncio.run(store.submit_feedback("user1", "msg1", "thread1", "up"))
        asyncio.run(store.submit_feedback("user2", "msg2", "thread1", "up"))
        asyncio.run(store.submit_feedback("user3", "msg3", "thread1", "down"))

        stats = asyncio.run(store.get_aggregate_stats())
        assert stats["total_up"] == 2
        assert stats["total_down"] == 1
        assert stats["total_ratings"] == 3

    def test_get_aggregate_stats_satisfaction_ratio(self, store: FeedbackStore):
        asyncio.run(store.submit_feedback("user1", "msg1", "thread1", "up"))
        asyncio.run(store.submit_feedback("user2", "msg2", "thread1", "up"))
        asyncio.run(store.submit_feedback("user3", "msg3", "thread1", "down"))
        asyncio.run(store.submit_feedback("user4", "msg4", "thread1", "down"))

        stats = asyncio.run(store.get_aggregate_stats())
        assert stats["satisfaction_ratio"] == 0.5

    def test_get_aggregate_stats_recent_comments(self, store: FeedbackStore):
        asyncio.run(store.submit_feedback("user1", "msg1", "thread1", "down", "Wrong prices"))
        asyncio.run(store.submit_feedback("user2", "msg2", "thread1", "down", "Bad restaurant recs"))
        asyncio.run(store.submit_feedback("user3", "msg3", "thread1", "down", "Missing transport info"))

        stats = asyncio.run(store.get_aggregate_stats())
        assert len(stats["recent_comments"]) == 3
        for c in stats["recent_comments"]:
            assert c["comment"]
            assert c["thread_id"] == "thread1"

    def test_one_rating_per_message(self, store: FeedbackStore):
        asyncio.run(store.submit_feedback("user1", "msg1", "thread1", "up"))
        asyncio.run(store.submit_feedback("user1", "msg1", "thread1", "down", "Changed my mind"))

        stats = asyncio.run(store.get_aggregate_stats())
        assert stats["total_ratings"] == 1
        assert stats["total_down"] == 1
        assert stats["total_up"] == 0

    def test_empty_stats(self, store: FeedbackStore):
        stats = asyncio.run(store.get_aggregate_stats())
        assert stats["total_up"] == 0
        assert stats["total_down"] == 0
        assert stats["total_ratings"] == 0
        assert stats["satisfaction_ratio"] == 0.0
        assert stats["recent_comments"] == []

    def test_up_votes_excluded_from_comments(self, store: FeedbackStore):
        asyncio.run(store.submit_feedback("user1", "msg1", "thread1", "up", "Great!"))
        asyncio.run(store.submit_feedback("user2", "msg2", "thread1", "down", "Bad"))

        stats = asyncio.run(store.get_aggregate_stats())
        assert len(stats["recent_comments"]) == 1
        assert stats["recent_comments"][0]["comment"] == "Bad"
