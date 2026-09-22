"""Regression: a failed RedisStore.setup() must not poison the global cache.

Previously _store was assigned BEFORE setup() ran, so after the first failure
every subsequent call silently returned the broken RedisStore — activity data
writes failed on every request (Upstash rejects FT.SEARCH). Now the broken
instance is never cached, and get_activity_store() falls back to a SHARED
InMemoryStore without retrying Redis.
"""

import asyncio

import pytest

import agents.deep_agent as deep_agent_module
from agents.activity_store import load_all_activity, save_activity
from langgraph.store.memory import InMemoryStore


class _FailingRedisStore:
    """Stand-in for RedisStore whose setup() always fails (like Upstash)."""

    created = 0

    def __init__(self, conn=None, index=None):
        _FailingRedisStore.created += 1

    def setup(self):
        raise RuntimeError("Upstash Redis does not support FT.* commands")


@pytest.fixture
def _redis_store_env(monkeypatch):
    """Force STORE_BACKEND=redis and a RedisStore that always fails setup()."""
    monkeypatch.setattr(deep_agent_module.settings, "STORE_BACKEND", "redis")
    monkeypatch.setattr(deep_agent_module, "RedisStore", _FailingRedisStore)
    monkeypatch.setattr(
        deep_agent_module.RedisConnectionFactory,
        "get_redis_connection",
        staticmethod(lambda url: object()),
    )
    _FailingRedisStore.created = 0


class TestCreateRedisStoreCaching:
    def test_failed_setup_does_not_cache(self, _redis_store_env, monkeypatch):
        with pytest.raises(RuntimeError):
            deep_agent_module.create_redis_store()
        assert deep_agent_module._store is None

    def test_successful_setup_caches(self, _redis_store_env, monkeypatch):
        class _GoodStore(_FailingRedisStore):
            def setup(self):
                pass

        monkeypatch.setattr(deep_agent_module, "RedisStore", _GoodStore)
        s1 = deep_agent_module.create_redis_store()
        s2 = deep_agent_module.create_redis_store()
        assert s1 is s2
        assert deep_agent_module._store is s1


class TestGetActivityStore:
    def test_falls_back_to_memory_after_failure(self, _redis_store_env):
        store = deep_agent_module.get_activity_store()
        assert isinstance(store, InMemoryStore)

    def test_marks_broken_and_does_not_retry(self, _redis_store_env):
        deep_agent_module.get_activity_store()
        assert deep_agent_module._store_broken is True
        created_after_first = _FailingRedisStore.created
        deep_agent_module.get_activity_store()
        deep_agent_module.get_activity_store()
        assert _FailingRedisStore.created == created_after_first

    def test_fallback_is_shared_singleton(self, _redis_store_env):
        """A fresh InMemoryStore per call would lose data across requests —
        the fallback must be the SAME instance every time."""
        s1 = deep_agent_module.get_activity_store()
        s2 = deep_agent_module.get_activity_store()
        assert s1 is s2

    def test_activity_round_trip_through_fallback(self, _redis_store_env):
        """End-to-end: the exact symptom from logs — 'Failed to save activity'
        — is gone; data saved is data read back."""
        store = deep_agent_module.get_activity_store()
        activity = {
            "thinking": [{"text": "hmm"}],
            "tool_calls": [{"name": "internet_search"}],
            "usage": [{"model": "gpt-4o"}],
            "total_input_tokens": 100,
            "total_output_tokens": 50,
            "images": [],
            "charts": [],
        }
        asyncio.run(save_activity(store, "thread-1", activity, message_index=2))
        loaded = asyncio.run(load_all_activity(store, "thread-1"))
        assert loaded is not None
        assert loaded["2"]["total_input_tokens"] == 100

    def test_memory_backend_returns_memory_store(self, monkeypatch):
        monkeypatch.setattr(deep_agent_module.settings, "STORE_BACKEND", "memory")
        assert isinstance(deep_agent_module.get_activity_store(), InMemoryStore)
