"""Regression tests for Bug #1 — split-brain reads across stores.

The old pattern wrote to the first working store and returned early on a
successful (but empty) Redis read. Data written to SQLite during a Redis
blip became invisible once Redis recovered. These tests verify:

- reads consult ALL stores (Redis-up-but-empty still finds SQLite data)
- writes go through to Redis AND SQLite
- deletes propagate to every store
- merged reads deduplicate records present in multiple stores
"""

from __future__ import annotations

import fnmatch
import os
import tempfile
import time
from unittest.mock import patch

import pytest
import pytest_asyncio

# Patch the SQLite fallback DB path BEFORE importing any store modules
_tmpdir = tempfile.mkdtemp(prefix="voyager_splitbrain_")
_test_db_path = os.path.join(_tmpdir, "test_stores.sqlite")
os.environ["SQLITE_FALLBACK_DB_PATH"] = _test_db_path

from config import settings  # noqa: E402
settings.SQLITE_FALLBACK_DB_PATH = _test_db_path

import sqlite_fallback  # noqa: E402
from threads import ThreadStore  # noqa: E402
from share_store import ShareStore  # noqa: E402
from cost_store import CostStore  # noqa: E402
from security_store import SecurityStore  # noqa: E402
from feedback_store import FeedbackStore  # noqa: E402
from research_cache import ResearchCache  # noqa: E402
from geocode_cache import GeocodeCache  # noqa: E402
from file_store import FileStore  # noqa: E402
import rate_limiter as rl_module  # noqa: E402
from rate_limiter import RateLimiter  # noqa: E402
from sqlite_fallback import get_sqlite_connection as _real_get_sqlite  # noqa: E402


# ---------------------------------------------------------------------------
# Minimal in-memory Redis double
# ---------------------------------------------------------------------------


class FakePipeline:
    def __init__(self, r: "FakeRedis") -> None:
        self._r = r
        self._ops: list[tuple] = []

    def __getattr__(self, name: str):
        def enqueue(*args, **kwargs):
            self._ops.append((name, args, kwargs))
            return self
        return enqueue

    async def execute(self) -> list:
        results = []
        for name, args, kwargs in self._ops:
            results.append(await getattr(self._r, name)(*args, **kwargs))
        self._ops.clear()
        return results


class FakeRedis:
    """In-memory stand-in for redis.asyncio.Redis covering ops used by the stores."""

    def __init__(self) -> None:
        self.hashes: dict[str, dict] = {}
        self.zsets: dict[str, dict] = {}
        self.strings: dict[str, str] = {}
        self.sets: dict[str, set] = {}
        self.lists: dict[str, list] = {}

    def pipeline(self) -> FakePipeline:
        return FakePipeline(self)

    async def zadd(self, key, mapping):
        self.zsets.setdefault(key, {}).update(mapping)

    async def zrange(self, key, start, end, withscores=False):
        members = [m for m, _ in sorted(self.zsets.get(key, {}).items(), key=lambda kv: kv[1])]
        sliced = members[start:] if end == -1 else members[start:end + 1]
        if withscores:
            return [(m, self.zsets[key][m]) for m in sliced]
        return sliced

    async def zrevrange(self, key, start, end):
        members = [m for m, _ in sorted(self.zsets.get(key, {}).items(), key=lambda kv: -kv[1])]
        return members[start:] if end == -1 else members[start:end + 1]

    async def zrangebyscore(self, key, minv, maxv, withscores=False):
        hi = float("inf") if maxv == "+inf" else float(maxv)
        pairs = [(m, sc) for m, sc in sorted(self.zsets.get(key, {}).items(), key=lambda kv: kv[1])
                 if float(minv) <= sc <= hi]
        if withscores:
            return pairs
        return [m for m, _ in pairs]

    async def zrem(self, key, member):
        self.zsets.get(key, {}).pop(member, None)

    async def zremrangebyscore(self, key, minv, maxv):
        z = self.zsets.get(key, {})
        for m in [m for m, sc in z.items() if float(minv) <= sc <= float(maxv)]:
            del z[m]

    async def zcard(self, key):
        return len(self.zsets.get(key, {}))

    async def hset(self, key, field=None, value=None, mapping=None):
        h = self.hashes.setdefault(key, {})
        if mapping:
            h.update(mapping)
        elif field is not None:
            h[field] = value

    async def hgetall(self, key):
        return dict(self.hashes.get(key, {}))

    async def exists(self, key):
        return any(key in store for store in (self.hashes, self.zsets, self.strings, self.sets, self.lists))

    async def delete(self, *keys):
        n = 0
        for k in keys:
            for store in (self.hashes, self.zsets, self.strings, self.sets, self.lists):
                if k in store:
                    del store[k]
                    n += 1
        return n

    async def expire(self, key, ttl):
        return True

    async def get(self, key):
        return self.strings.get(key)

    async def set(self, key, value, ex=None):
        self.strings[key] = value

    async def scan(self, cursor=0, match=None, count=100):
        keys = [k for k in self.hashes if match is None or fnmatch.fnmatch(k, match)]
        return 0, keys

    async def keys(self, pattern):
        return [k for k in self.strings if fnmatch.fnmatch(k, pattern)]

    async def sadd(self, key, *members):
        self.sets.setdefault(key, set()).update(members)

    async def smembers(self, key):
        return set(self.sets.get(key, set()))

    async def scard(self, key):
        return len(self.sets.get(key, set()))

    async def incr(self, key):
        self.strings[key] = str(int(self.strings.get(key, 0)) + 1)
        return int(self.strings[key])

    async def rpush(self, key, *values):
        self.lists.setdefault(key, []).extend(values)

    async def lrange(self, key, start, end):
        lst = self.lists.get(key, [])
        return lst[start:] if end == -1 else lst[start:end + 1]


def _no_redis():
    """Patch target that always returns None (Redis fully down)."""
    async def _get_redis_none(self):
        return None
    return _get_redis_none


def _fake_redis(fake: FakeRedis):
    """Patch target returning an empty/populated in-memory Redis."""
    async def _get(self):
        return fake
    return _get


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _cleanup_db_files():
    for ext in ("", "-wal", "-shm"):
        path = _test_db_path + ext
        if os.path.exists(path):
            os.remove(path)


@pytest_asyncio.fixture(autouse=True)
async def _reset_sqlite_conn():
    settings.SQLITE_FALLBACK_DB_PATH = _test_db_path
    await sqlite_fallback.close_connection()
    _cleanup_db_files()
    yield
    await sqlite_fallback.close_connection()
    _cleanup_db_files()


# ---------------------------------------------------------------------------
# ThreadStore
# ---------------------------------------------------------------------------


class TestThreadStoreSplitBrain:
    @pytest.mark.asyncio
    async def test_sqlite_only_thread_visible_when_redis_empty(self):
        """Thread written during Redis outage is listed after Redis recovers."""
        # Write while Redis is down → lands in SQLite only
        store = ThreadStore()
        with patch.object(ThreadStore, "_get_redis", _no_redis()):
            await store.upsert_thread("alice", "chat:u:t1", "Kyoto trip")

        # Redis "recovers" but has no copy — read must still find the thread
        fake = FakeRedis()
        with patch.object(ThreadStore, "_get_redis", _fake_redis(fake)):
            threads = await store.list_threads("alice")
            assert [t.thread_id for t in threads] == ["chat:u:t1"]
            assert await store.get_thread("alice", "chat:u:t1") is not None
            assert await store.count_threads("alice") == 1

    @pytest.mark.asyncio
    async def test_merged_reads_deduplicate(self):
        """A thread present in both stores is returned once."""
        fake = FakeRedis()
        store = ThreadStore()
        with patch.object(ThreadStore, "_get_redis", _fake_redis(fake)):
            # Write-through → exists in both Redis and SQLite
            await store.upsert_thread("alice", "chat:u:t1", "Both stores")
            assert fake.hashes  # sanity: Redis copy exists
            threads = await store.list_threads("alice")
            assert len(threads) == 1
            assert await store.count_threads("alice") == 1

    @pytest.mark.asyncio
    async def test_union_of_disjoint_stores(self):
        """Threads split across Redis and SQLite are all listed."""
        fake = FakeRedis()
        store = ThreadStore()
        # t1 in SQLite only (written during Redis outage)
        with patch.object(ThreadStore, "_get_redis", _no_redis()):
            await store.upsert_thread("alice", "chat:u:t1", "SQLite only")
        # t2 in Redis only (write-through fails on SQLite? simulate by deleting sqlite row)
        with patch.object(ThreadStore, "_get_redis", _fake_redis(fake)):
            await store.upsert_thread("alice", "chat:u:t2", "Both stores")
            db = await _real_get_sqlite()
            await db.execute("DELETE FROM threads WHERE thread_id = 'chat:u:t2'")
            await db.commit()
            threads = await store.list_threads("alice")
            assert sorted(t.thread_id for t in threads) == ["chat:u:t1", "chat:u:t2"]

    @pytest.mark.asyncio
    async def test_delete_propagates_to_all_stores(self):
        """delete_thread removes the thread from Redis AND SQLite."""
        fake = FakeRedis()
        store = ThreadStore()
        with patch.object(ThreadStore, "_get_redis", _fake_redis(fake)):
            await store.upsert_thread("alice", "chat:u:t1", "Delete me")
            assert await store.delete_thread("alice", "chat:u:t1") is True
            assert not any(k.endswith("chat:u:t1") for k in fake.hashes)
            db = await _real_get_sqlite()
            cur = await db.execute("SELECT COUNT(*) FROM threads WHERE thread_id = 'chat:u:t1'")
            assert (await cur.fetchone())[0] == 0
            assert await store.list_threads("alice") == []

    @pytest.mark.asyncio
    async def test_update_status_reaches_sqlite(self):
        """Status update applies to the SQLite copy too."""
        store = ThreadStore()
        with patch.object(ThreadStore, "_get_redis", _no_redis()):
            await store.upsert_thread("alice", "chat:u:t1", "Trip")
        fake = FakeRedis()
        with patch.object(ThreadStore, "_get_redis", _fake_redis(fake)):
            await store.update_status("alice", "chat:u:t1", "busy")
            db = await _real_get_sqlite()
            cur = await db.execute("SELECT status FROM threads WHERE thread_id = 'chat:u:t1'")
            assert (await cur.fetchone())[0] == "busy"


# ---------------------------------------------------------------------------
# FileStore
# ---------------------------------------------------------------------------


class TestFileStoreSplitBrain:
    @pytest.mark.asyncio
    async def test_sqlite_only_file_visible_when_redis_empty(self):
        store = FileStore()
        with patch.object(FileStore, "_get_redis", _no_redis()):
            meta = await store.upload("alice", "doc.pdf", "application/pdf", b"hello")
        fake = FakeRedis()
        with patch.object(FileStore, "_get_redis", _fake_redis(fake)):
            got = await store.get("alice", meta["file_id"])
            assert got is not None
            assert got.filename == "doc.pdf"
            assert got.data == "aGVsbG8="  # base64("hello")

    @pytest.mark.asyncio
    async def test_delete_propagates(self):
        fake = FakeRedis()
        store = FileStore()
        with patch.object(FileStore, "_get_redis", _fake_redis(fake)):
            meta = await store.upload("alice", "a.txt", "text/plain", b"x")
            assert await store.delete("alice", meta["file_id"]) is True
            assert await store.get("alice", meta["file_id"]) is None


# ---------------------------------------------------------------------------
# ShareStore
# ---------------------------------------------------------------------------


class TestShareStoreSplitBrain:
    @pytest.mark.asyncio
    async def test_sqlite_only_share_resolves_when_redis_empty(self):
        store = ShareStore()
        with patch.object(ShareStore, "_get_redis", _no_redis()):
            token, _ = await store.create_share("alice", "t1", '{"itinerary": 1}', "Tokyo")
        fake = FakeRedis()
        with patch.object(ShareStore, "_get_redis", _fake_redis(fake)):
            share = await store.get_share(token)
            assert share is not None
            assert share["destination"] == "Tokyo"
            listed = await store.list_shares("alice")
            assert [s.token for s in listed] == [token]

    @pytest.mark.asyncio
    async def test_revoke_propagates(self):
        fake = FakeRedis()
        store = ShareStore()
        with patch.object(ShareStore, "_get_redis", _fake_redis(fake)):
            token, _ = await store.create_share("alice", "t1", "{}", "Rome")
            assert await store.revoke_share("alice", token) is True
            assert await store.get_share(token) is None


# ---------------------------------------------------------------------------
# SecurityStore
# ---------------------------------------------------------------------------


class TestSecurityStoreSplitBrain:
    @pytest.mark.asyncio
    async def test_strikes_recorded_during_outage_still_count(self):
        store = SecurityStore()
        with patch.object(SecurityStore, "_get_redis", _no_redis()):
            await store.record_strike("mallory")
        fake = FakeRedis()
        with patch.object(SecurityStore, "_get_redis", _fake_redis(fake)):
            assert await store.get_strike_count("mallory") == 1

    @pytest.mark.asyncio
    async def test_cooldown_survives_redis_recovery(self):
        """Cooldown written to SQLite during a blip still applies."""
        store = SecurityStore()
        with patch.object(SecurityStore, "_get_redis", _no_redis()):
            await store.apply_cooldown("mallory", minutes=30)
        fake = FakeRedis()
        with patch.object(SecurityStore, "_get_redis", _fake_redis(fake)):
            assert await store.is_in_cooldown("mallory") is True
            # remove_cooldown clears it everywhere
            import hashlib
            user_hash = hashlib.sha256(b"mallory").hexdigest()[:12]
            assert await store.remove_cooldown(user_hash) is True
            assert await store.is_in_cooldown("mallory") is False


# ---------------------------------------------------------------------------
# CostStore
# ---------------------------------------------------------------------------


class TestCostStoreSplitBrain:
    @pytest.mark.asyncio
    async def test_sqlite_only_spend_counts_toward_daily_cap(self):
        """Spend recorded during a Redis blip still counts after recovery."""
        store = CostStore()
        with patch.object(CostStore, "_get_redis", _no_redis()):
            await store.update_session_total("t1", "alice", 100, 50, 0.25, 10.0, False)
        fake = FakeRedis()
        with patch.object(CostStore, "_get_redis", _fake_redis(fake)):
            assert await store.get_user_daily_spend("alice") == 0.25
            session = await store.get_session_cost("t1")
            assert session is not None
            assert session["total_cost_usd"] == 0.25

    @pytest.mark.asyncio
    async def test_subagent_entries_dedupe_across_stores(self):
        """Write-through stores the same entry in Redis + SQLite — count once."""
        fake = FakeRedis()
        store = CostStore()
        with patch.object(CostStore, "_get_redis", _fake_redis(fake)):
            await store.record_subagent_cost("t1", "alice", "flights", 10, 5, 0.01, "gpt-4o")
            breakdown = await store.get_subagent_breakdown("t1")
            assert len(breakdown) == 1


# ---------------------------------------------------------------------------
# FeedbackStore / caches
# ---------------------------------------------------------------------------


class TestFeedbackSplitBrain:
    @pytest.mark.asyncio
    async def test_sqlite_only_feedback_visible(self):
        store = FeedbackStore()
        with patch.object(FeedbackStore, "_get_redis", _no_redis()):
            await store.submit_feedback("alice", "m1", "t1", "up")
        fake = FakeRedis()
        with patch.object(FeedbackStore, "_get_redis", _fake_redis(fake)):
            fb = await store.get_feedback("alice", "m1")
            assert fb is not None and fb["rating"] == "up"
            stats = await store.get_aggregate_stats()
            assert stats["total_up"] == 1


class TestCachesSplitBrain:
    @pytest.mark.asyncio
    async def test_research_cache_sqlite_hit(self):
        cache = ResearchCache()
        with patch.object(ResearchCache, "_get_redis", _no_redis()):
            await cache.set("k1", "result-text")
        fake = FakeRedis()
        with patch.object(ResearchCache, "_get_redis", _fake_redis(fake)):
            assert await cache.get("k1") == "result-text"

    @pytest.mark.asyncio
    async def test_geocode_cache_sqlite_hit(self):
        cache = GeocodeCache()
        with patch.object(GeocodeCache, "_get_redis", _no_redis()):
            await cache.set("Tokyo", 35.6762, 139.6503)
        fake = FakeRedis()
        with patch.object(GeocodeCache, "_get_redis", _fake_redis(fake)):
            got = await cache.get("Tokyo")
            assert got == {"lat": 35.6762, "lng": 139.6503}


# ---------------------------------------------------------------------------
# RateLimiter — union counting across stores
# ---------------------------------------------------------------------------


class TestRateLimiterSplitBrain:
    @pytest.mark.asyncio
    async def test_hits_in_sqlite_count_when_redis_recovers(self):
        """Requests recorded during a Redis blip still count toward the limit."""
        # conftest disables SQLite for rate_limiter — restore the real one
        mp = pytest.MonkeyPatch()
        mp.setattr(rl_module, "get_sqlite_connection", _real_get_sqlite)

        rl = RateLimiter()
        # 9 hits while Redis is down → SQLite only
        with patch.object(RateLimiter, "_get_redis", _no_redis()):
            for _ in range(9):
                allowed, _ = await rl.check_rate_limit("alice", "chat", 10)
                assert allowed is True
        # Redis "recovers" empty — hits 10 and 11 must see the 9 SQLite hits
        fake = FakeRedis()
        with patch.object(RateLimiter, "_get_redis", _fake_redis(fake)):
            allowed, _ = await rl.check_rate_limit("alice", "chat", 10)
            assert allowed is True
            allowed, retry = await rl.check_rate_limit("alice", "chat", 10)
            assert allowed is False
            assert retry > 0
