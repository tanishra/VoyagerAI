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
        _exp, raw = s._mem[key]
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


class TestDurableTier:
    """Thread-state keys write through to the durable DB (SQLite in tests —
    PG pool is broken by conftest) so a Redis flush doesn't orphan history,
    export, or share lookups."""

    def test_thread_state_survives_fresh_store(self):
        """Simulates Redis flush + process restart: a brand-new store with
        empty memory still resolves the record via the durable tier."""
        s = _store()
        asyncio.run(s.set_thread_state("t-dur", "latest_itinerary", {"days": [1, 2]}))
        s2 = _store()
        assert asyncio.run(s2.get_thread_state("t-dur", "latest_itinerary")) == {"days": [1, 2]}

    def test_durable_expiry_returns_none(self):
        """Rows past their TTL are treated as gone (and lazily deleted)."""
        s = _store()
        asyncio.run(s.set_thread_state("t-exp", "latest_comparison", {"v": 1}))
        # Expire the durable row directly
        from pg_store import get_durable_db

        async def _expire():
            db = await get_durable_db()
            await db.execute(
                "UPDATE payload_thread_state SET expires_at = ? WHERE thread_id = ? AND key = ?",
                (time.time() - 1, "t-exp", "latest_comparison"),
            )
            await db.commit()
        asyncio.run(_expire())
        s2 = _store()
        assert asyncio.run(s2.get_thread_state("t-exp", "latest_comparison")) is None

    def test_durable_failure_falls_back_to_memory(self, monkeypatch):
        """If the durable tier is down, Redis/mem behavior is unchanged."""
        async def _no_db():
            return None
        import pg_store
        monkeypatch.setattr(pg_store, "get_durable_db", _no_db)
        s = _store()
        asyncio.run(s.set_thread_state("t-mem", "constraints", {"days": 5}))
        assert asyncio.run(s.get_thread_state("t-mem", "constraints")) == {"days": 5}
