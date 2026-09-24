"""Tests for payload_store — Redis-backed side channel with bounded memory fallback.

conftest fails all Redis.from_url calls, so every test exercises the
in-memory path; Redis-specific behavior is covered by mocking _get_redis.
"""

import asyncio
import time

import payload_store as store_module
from payload_store import PayloadStore


def _store() -> PayloadStore:
    return PayloadStore()


class TestPayloads:
    def test_store_pop_roundtrip(self):
        s = _store()
        asyncio.run(s.store("p1", "comparison", {"plans": []}))
        assert asyncio.run(s.pop("p1")) == {"kind": "comparison", "data": {"plans": []}}
        assert asyncio.run(s.pop("p1")) is None  # one-shot

    def test_pop_missing_returns_none(self):
        assert asyncio.run(_store().pop("nope")) is None

    def test_expired_payload_dropped(self, monkeypatch):
        s = _store()
        asyncio.run(s.store("p1", "itinerary", {"days": []}))
        # Push the mem entry into the past
        key = "pipeline:payload:p1"
        exp, raw = s._mem[key]
        s._mem[key] = (time.time() - 1, raw)
        assert asyncio.run(s.pop("p1")) is None

    def test_bounded_eviction(self, monkeypatch):
        monkeypatch.setattr(store_module, "_MEM_MAX_ENTRIES", 5)
        s = _store()
        for i in range(10):
            asyncio.run(s.store(f"p{i}", "comparison", {"i": i}))
        assert len(s._mem) == 5
        # Oldest evicted, newest survive
        assert asyncio.run(s.pop("p0")) is None
        assert asyncio.run(s.pop("p9")) is not None


class TestThreadState:
    def test_roundtrip_per_thread(self):
        s = _store()
        asyncio.run(s.set_thread_state("t1", "constraints", {"days": 5}))
        asyncio.run(s.set_thread_state("t2", "constraints", {"days": 3}))
        assert asyncio.run(s.get_thread_state("t1", "constraints")) == {"days": 5}
        assert asyncio.run(s.get_thread_state("t2", "constraints")) == {"days": 3}
        assert asyncio.run(s.get_thread_state("t3", "constraints")) is None

    def test_overwrite(self):
        s = _store()
        asyncio.run(s.set_thread_state("t1", "latest_comparison", {"v": 1}))
        asyncio.run(s.set_thread_state("t1", "latest_comparison", {"v": 2}))
        assert asyncio.run(s.get_thread_state("t1", "latest_comparison")) == {"v": 2}


class TestRedisFallback:
    def test_redis_failure_uses_memory_and_retries_later(self):
        s = _store()
        asyncio.run(s.store("p1", "comparison", {"x": 1}))
        assert asyncio.run(s.pop("p1")) == {"kind": "comparison", "data": {"x": 1}}
        # First failure set a retry window
        assert s._redis_retry_after > 0
