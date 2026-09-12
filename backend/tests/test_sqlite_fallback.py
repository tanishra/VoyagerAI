"""Tests for the SQLite fallback mechanism.

Verifies that all Redis-backed stores correctly fall back to SQLite when
Redis is unavailable, and that data persists across store instances (simulating
server restarts). Uses a temporary SQLite database file for isolation.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
from unittest.mock import patch

import pytest
import pytest_asyncio

# Patch the SQLite fallback DB path BEFORE importing any store modules
_tmpdir = tempfile.mkdtemp(prefix="voyager_test_")
_test_db_path = os.path.join(_tmpdir, "test_stores.sqlite")
os.environ["SQLITE_FALLBACK_DB_PATH"] = _test_db_path

# Force the settings to pick up the env var
from config import settings  # noqa: E402
settings.SQLITE_FALLBACK_DB_PATH = _test_db_path

import sqlite_fallback  # noqa: E402
from threads import ThreadStore  # noqa: E402
from share_store import ShareStore  # noqa: E402
from oauth import create_session, get_session, delete_session  # noqa: E402
from cost_store import CostStore  # noqa: E402
from feedback_store import FeedbackStore  # noqa: E402
from security_store import SecurityStore  # noqa: E402
from research_cache import ResearchCache  # noqa: E402
from geocode_cache import GeocodeCache  # noqa: E402
from file_store import FileStore  # noqa: E402


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
    """Reset the shared SQLite connection before each test for isolation."""
    await sqlite_fallback.close_connection()
    _cleanup_db_files()
    yield
    await sqlite_fallback.close_connection()
    _cleanup_db_files()


def _no_redis():
    """Patch target that always returns None (Redis unavailable)."""
    async def _get_redis_none(self):
        return None
    return _get_redis_none


# ---------------------------------------------------------------------------
# ThreadStore SQLite fallback
# ---------------------------------------------------------------------------


class TestThreadStoreSQLite:
    @pytest.mark.asyncio
    async def test_upsert_and_list_via_sqlite(self):
        store = ThreadStore()
        store._redis = None
        with patch.object(ThreadStore, "_get_redis", _no_redis()):
            await store.upsert_thread("alice", "chat:abc:t1", "Tokyo trip")
            threads = await store.list_threads("alice")
            assert len(threads) == 1
            assert threads[0].thread_id == "chat:abc:t1"
            assert threads[0].summary == "Tokyo trip"

    @pytest.mark.asyncio
    async def test_persistence_across_store_instances(self):
        """Data should survive creating a new store instance (simulating restart)."""
        store1 = ThreadStore()
        store1._redis = None
        with patch.object(ThreadStore, "_get_redis", _no_redis()):
            await store1.upsert_thread("alice", "chat:abc:t1", "Persistent thread")
        # Create a new store — should read from the same SQLite DB
        store2 = ThreadStore()
        store2._redis = None
        with patch.object(ThreadStore, "_get_redis", _no_redis()):
            threads = await store2.list_threads("alice")
            assert len(threads) == 1
            assert threads[0].summary == "Persistent thread"

    @pytest.mark.asyncio
    async def test_delete_via_sqlite(self):
        store = ThreadStore()
        store._redis = None
        with patch.object(ThreadStore, "_get_redis", _no_redis()):
            await store.upsert_thread("alice", "chat:abc:t1", "Delete me")
            assert await store.delete_thread("alice", "chat:abc:t1") is True
            threads = await store.list_threads("alice")
            assert len(threads) == 0

    @pytest.mark.asyncio
    async def test_get_thread_via_sqlite(self):
        store = ThreadStore()
        store._redis = None
        with patch.object(ThreadStore, "_get_redis", _no_redis()):
            await store.upsert_thread("alice", "chat:abc:t1", "Get me")
            thread = await store.get_thread("alice", "chat:abc:t1")
            assert thread is not None
            assert thread.summary == "Get me"

    @pytest.mark.asyncio
    async def test_count_threads_via_sqlite(self):
        store = ThreadStore()
        store._redis = None
        with patch.object(ThreadStore, "_get_redis", _no_redis()):
            assert await store.count_threads("alice") == 0
            await store.upsert_thread("alice", "chat:abc:t1", "Trip 1")
            await store.upsert_thread("alice", "chat:abc:t2", "Trip 2")
            assert await store.count_threads("alice") == 2

    @pytest.mark.asyncio
    async def test_update_status_via_sqlite(self):
        store = ThreadStore()
        store._redis = None
        with patch.object(ThreadStore, "_get_redis", _no_redis()):
            await store.upsert_thread("alice", "chat:abc:t1", "Trip")
            await store.update_status("alice", "chat:abc:t1", "busy")
            thread = await store.get_thread("alice", "chat:abc:t1")
            assert thread.status == "busy"

    @pytest.mark.asyncio
    async def test_search_threads_via_sqlite(self):
        store = ThreadStore()
        store._redis = None
        with patch.object(ThreadStore, "_get_redis", _no_redis()):
            await store.upsert_thread("alice", "chat:abc:t1", "Tokyo trip", search_text="Tokyo Japan temples")
            await store.upsert_thread("alice", "chat:abc:t2", "Paris trip", search_text="Paris France food")
            results, total = await store.search_threads("alice", "Tokyo")
            assert total == 1
            assert results[0]["thread_id"] == "chat:abc:t1"


# ---------------------------------------------------------------------------
# ShareStore SQLite fallback
# ---------------------------------------------------------------------------


class TestShareStoreSQLite:
    @pytest.mark.asyncio
    async def test_create_and_get_share_via_sqlite(self):
        store = ShareStore()
        store._redis = None
        with patch.object(ShareStore, "_get_redis", _no_redis()):
            token, expires_at = await store.create_share(
                "alice", "chat:abc:t1", '{"dest": "Tokyo"}', "Tokyo"
            )
            assert expires_at > time.time()
            data = await store.get_share(token)
            assert data is not None
            assert data["destination"] == "Tokyo"

    @pytest.mark.asyncio
    async def test_list_shares_via_sqlite(self):
        store = ShareStore()
        store._redis = None
        with patch.object(ShareStore, "_get_redis", _no_redis()):
            await store.create_share("alice", "chat:abc:t1", "{}", "Tokyo")
            await store.create_share("alice", "chat:abc:t2", "{}", "Paris")
            shares = await store.list_shares("alice")
            assert len(shares) == 2

    @pytest.mark.asyncio
    async def test_revoke_share_via_sqlite(self):
        store = ShareStore()
        store._redis = None
        with patch.object(ShareStore, "_get_redis", _no_redis()):
            token, _ = await store.create_share("alice", "chat:abc:t1", "{}", "Tokyo")
            assert await store.revoke_share("alice", token) is True
            assert await store.get_share(token) is None


# ---------------------------------------------------------------------------
# OAuth sessions SQLite fallback
# ---------------------------------------------------------------------------


class TestOAuthSQLite:
    @pytest.mark.asyncio
    async def test_create_and_get_session_via_sqlite(self):
        with patch("oauth._get_redis", new=None):
            # _get_redis is a module-level function, not a method
            with patch("oauth._get_redis", side_effect=_redis_none_func):
                sid = await create_session({"user_id": "alice", "email": "a@b.com"})
                session = await get_session(sid)
                assert session is not None
                assert session["user_id"] == "alice"

    @pytest.mark.asyncio
    async def test_delete_session_via_sqlite(self):
        with patch("oauth._get_redis", side_effect=_redis_none_func):
            sid = await create_session({"user_id": "alice"})
            await delete_session(sid)
            session = await get_session(sid)
            assert session is None


async def _redis_none_func():
    return None


# ---------------------------------------------------------------------------
# CostStore SQLite fallback
# ---------------------------------------------------------------------------


class TestCostStoreSQLite:
    @pytest.mark.asyncio
    async def test_record_and_get_subagent_cost_via_sqlite(self):
        store = CostStore()
        store._redis = None
        with patch.object(CostStore, "_get_redis", _no_redis()):
            await store.record_subagent_cost("t1", "alice", "researcher", 100, 200, 0.05, "gpt-4o")
            breakdown = await store.get_subagent_breakdown("t1")
            assert len(breakdown) == 1
            assert breakdown[0]["subagent_name"] == "researcher"
            assert breakdown[0]["input_tokens"] == 100

    @pytest.mark.asyncio
    async def test_update_and_get_session_cost_via_sqlite(self):
        store = CostStore()
        store._redis = None
        with patch.object(CostStore, "_get_redis", _no_redis()):
            await store.update_session_total("t1", "alice", 500, 300, 0.15, 10.0, False)
            cost = await store.get_session_cost("t1")
            assert cost is not None
            assert cost["total_input_tokens"] == 500
            assert cost["total_cost_usd"] == 0.15
            assert cost["budget_reached"] is False


# ---------------------------------------------------------------------------
# FeedbackStore SQLite fallback
# ---------------------------------------------------------------------------


class TestFeedbackStoreSQLite:
    @pytest.mark.asyncio
    async def test_submit_and_get_feedback_via_sqlite(self):
        store = FeedbackStore()
        store._redis = None
        with patch.object(FeedbackStore, "_get_redis", _no_redis()):
            await store.submit_feedback("alice", "msg1", "t1", "up")
            fb = await store.get_feedback("alice", "msg1")
            assert fb is not None
            assert fb["rating"] == "up"

    @pytest.mark.asyncio
    async def test_update_feedback_via_sqlite(self):
        store = FeedbackStore()
        store._redis = None
        with patch.object(FeedbackStore, "_get_redis", _no_redis()):
            await store.submit_feedback("alice", "msg1", "t1", "up")
            await store.submit_feedback("alice", "msg1", "t1", "down", "Not helpful")
            fb = await store.get_feedback("alice", "msg1")
            assert fb["rating"] == "down"
            assert fb["comment"] == "Not helpful"


# ---------------------------------------------------------------------------
# SecurityStore SQLite fallback
# ---------------------------------------------------------------------------


class TestSecurityStoreSQLite:
    @pytest.mark.asyncio
    async def test_record_flag_via_sqlite(self):
        store = SecurityStore()
        store._redis = None
        with patch.object(SecurityStore, "_get_redis", _no_redis()):
            flag_id = await store.record_flag("alice", "injection", "high", "llm_guard", "test", "t1")
            assert len(flag_id) > 0

    @pytest.mark.asyncio
    async def test_record_and_get_strike_via_sqlite(self):
        store = SecurityStore()
        store._redis = None
        with patch.object(SecurityStore, "_get_redis", _no_redis()):
            count = await store.record_strike("alice")
            assert count == 1
            count2 = await store.get_strike_count("alice")
            assert count2 >= 1

    @pytest.mark.asyncio
    async def test_cooldown_via_sqlite(self):
        store = SecurityStore()
        store._redis = None
        with patch.object(SecurityStore, "_get_redis", _no_redis()):
            assert await store.is_in_cooldown("alice") is False
            await store.apply_cooldown("alice", minutes=5)
            assert await store.is_in_cooldown("alice") is True
            user_hash = store._mem_cooldowns  # Won't be in mem, it's in SQLite
            # Remove cooldown
            from security_store import _hash_user_id
            uh = _hash_user_id("alice")
            assert await store.remove_cooldown(uh) is True
            assert await store.is_in_cooldown("alice") is False


# ---------------------------------------------------------------------------
# ResearchCache SQLite fallback
# ---------------------------------------------------------------------------


class TestResearchCacheSQLite:
    @pytest.mark.asyncio
    async def test_set_and_get_via_sqlite(self):
        cache = ResearchCache()
        cache._redis = None
        with patch.object(ResearchCache, "_get_redis", _no_redis()):
            await cache.set("query1", "result text")
            value = await cache.get("query1")
            assert value == "result text"

    @pytest.mark.asyncio
    async def test_miss_returns_none_via_sqlite(self):
        cache = ResearchCache()
        cache._redis = None
        with patch.object(ResearchCache, "_get_redis", _no_redis()):
            value = await cache.get("nonexistent")
            assert value is None


# ---------------------------------------------------------------------------
# GeocodeCache SQLite fallback
# ---------------------------------------------------------------------------


class TestGeocodeCacheSQLite:
    @pytest.mark.asyncio
    async def test_set_and_get_via_sqlite(self):
        cache = GeocodeCache()
        cache._redis = None
        with patch.object(GeocodeCache, "_get_redis", _no_redis()):
            await cache.set("Tokyo, Japan", 35.6762, 139.6503)
            result = await cache.get("Tokyo, Japan")
            assert result is not None
            assert abs(result["lat"] - 35.6762) < 0.01
            assert abs(result["lng"] - 139.6503) < 0.01

    @pytest.mark.asyncio
    async def test_miss_returns_none_via_sqlite(self):
        cache = GeocodeCache()
        cache._redis = None
        with patch.object(GeocodeCache, "_get_redis", _no_redis()):
            result = await cache.get("Nonexistent Place")
            assert result is None


# ---------------------------------------------------------------------------
# FileStore SQLite fallback
# ---------------------------------------------------------------------------


class TestFileStoreSQLite:
    @pytest.mark.asyncio
    async def test_upload_and_get_via_sqlite(self):
        store = FileStore()
        store._redis = None
        with patch.object(FileStore, "_get_redis", _no_redis()):
            data = b"test file content"
            result = await store.upload("alice", "test.png", "image/png", data)
            assert result["filename"] == "test.png"
            assert result["size"] == len(data)
            file_id = result["file_id"]
            meta = await store.get("alice", file_id)
            assert meta is not None
            assert meta.filename == "test.png"
            assert meta.size == len(data)

    @pytest.mark.asyncio
    async def test_delete_via_sqlite(self):
        store = FileStore()
        store._redis = None
        with patch.object(FileStore, "_get_redis", _no_redis()):
            result = await store.upload("alice", "test.txt", "text/plain", b"hello")
            file_id = result["file_id"]
            assert await store.delete("alice", file_id) is True
            assert await store.get("alice", file_id) is None


# ---------------------------------------------------------------------------
# Cleanup task
# ---------------------------------------------------------------------------


class TestCleanupExpired:
    @pytest.mark.asyncio
    async def test_cleanup_deletes_expired_rows(self):
        db = await sqlite_fallback.get_sqlite_connection()
        assert db is not None
        # Insert an expired share
        now = time.time()
        await db.execute(
            "INSERT INTO shares (token, user_tag, thread_id, destination, itinerary_json, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("expired_token", "test", "t1", "Tokyo", "{}", now - 100, now - 50),
        )
        await db.commit()
        # Run cleanup
        deleted = await sqlite_fallback.cleanup_expired()
        assert deleted >= 1
        # Verify the row is gone
        cur = await db.execute("SELECT * FROM shares WHERE token = ?", ("expired_token",))
        row = await cur.fetchone()
        assert row is None
