"""Tests for Phase 7.2: Per-user rate limiting, daily cost cap, and circuit breaker.

Uses in-memory / SQLite fallback (no Redis required) with mocked session
extraction for the middleware tests.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
from unittest.mock import patch

import pytest
import pytest_asyncio

# Patch the SQLite fallback DB path BEFORE importing store modules
_tmpdir = tempfile.mkdtemp(prefix="voyager_test_")
_test_db_path = os.path.join(_tmpdir, "test_rate_limits.sqlite")
os.environ["SQLITE_FALLBACK_DB_PATH"] = _test_db_path

from config import settings  # noqa: E402
settings.SQLITE_FALLBACK_DB_PATH = _test_db_path

import sqlite_fallback  # noqa: E402
from rate_limiter import RateLimiter, rate_limiter  # noqa: E402
from cost_store import CostStore  # noqa: E402


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
    settings.SQLITE_FALLBACK_DB_PATH = _test_db_path
    await sqlite_fallback.close_connection()
    _cleanup_db_files()
    yield
    await sqlite_fallback.close_connection()
    _cleanup_db_files()


def _no_redis(self):
    """Patch target that returns None (Redis unavailable)."""
    async def _get_redis_none():
        return None
    return _get_redis_none()


# ---------------------------------------------------------------------------
# RateLimiter — unit tests
# ---------------------------------------------------------------------------


class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_allows_under_limit(self):
        rl = RateLimiter()
        rl._redis = None
        with patch.object(RateLimiter, "_get_redis", _no_redis):
            for i in range(5):
                allowed, retry = await rl.check_rate_limit("alice", "chat", 10)
                assert allowed is True
                assert retry == 0

    @pytest.mark.asyncio
    async def test_blocks_over_limit(self):
        rl = RateLimiter()
        rl._redis = None
        with patch.object(RateLimiter, "_get_redis", _no_redis):
            for i in range(10):
                allowed, _ = await rl.check_rate_limit("alice", "chat", 10)
                assert allowed is True
            # 11th request should be blocked
            allowed, retry = await rl.check_rate_limit("alice", "chat", 10)
            assert allowed is False
            assert retry > 0

    @pytest.mark.asyncio
    async def test_different_users_independent(self):
        rl = RateLimiter()
        rl._redis = None
        with patch.object(RateLimiter, "_get_redis", _no_redis):
            for i in range(10):
                allowed, _ = await rl.check_rate_limit("alice", "chat", 10)
                assert allowed is True
            # Bob should still be allowed
            allowed, retry = await rl.check_rate_limit("bob", "chat", 10)
            assert allowed is True
            assert retry == 0

    @pytest.mark.asyncio
    async def test_different_endpoint_types_independent(self):
        rl = RateLimiter()
        rl._redis = None
        with patch.object(RateLimiter, "_get_redis", _no_redis):
            for i in range(10):
                allowed, _ = await rl.check_rate_limit("alice", "chat", 10)
                assert allowed is True
            # Upload should still be allowed (different endpoint type)
            allowed, _ = await rl.check_rate_limit("alice", "upload", 5)
            assert allowed is True

    @pytest.mark.asyncio
    async def test_persistence_across_instances(self):
        """Rate limit data should survive creating a new RateLimiter (SQLite)."""
        rl1 = RateLimiter()
        rl1._redis = None
        with patch.object(RateLimiter, "_get_redis", _no_redis):
            for i in range(10):
                allowed, _ = await rl1.check_rate_limit("alice", "chat", 10)
                assert allowed is True
        # New instance — should read from same SQLite DB
        rl2 = RateLimiter()
        rl2._redis = None
        with patch.object(RateLimiter, "_get_redis", _no_redis):
            allowed, retry = await rl2.check_rate_limit("alice", "chat", 10)
            assert allowed is False
            assert retry > 0

    @pytest.mark.asyncio
    async def test_retry_after_is_positive(self):
        rl = RateLimiter()
        rl._redis = None
        with patch.object(RateLimiter, "_get_redis", _no_redis):
            for i in range(3):
                await rl.check_rate_limit("alice", "chat", 3)
            allowed, retry = await rl.check_rate_limit("alice", "chat", 3)
            assert allowed is False
            assert 1 <= retry <= 60


# ---------------------------------------------------------------------------
# CostStore — daily spend + circuit breaker
# ---------------------------------------------------------------------------


class TestDailyCostCap:
    @pytest.mark.asyncio
    async def test_daily_spend_zero_for_new_user(self):
        store = CostStore()
        store._redis = None
        with patch.object(CostStore, "_get_redis", _no_redis):
            spent = await store.get_user_daily_spend("alice")
            assert spent == 0.0

    @pytest.mark.asyncio
    async def test_daily_spend_after_recording_cost(self):
        store = CostStore()
        store._redis = None
        with patch.object(CostStore, "_get_redis", _no_redis):
            await store.update_session_total("t1", "alice", 100, 200, 1.5, 0.50, False)
            spent = await store.get_user_daily_spend("alice")
            assert spent == 1.5

    @pytest.mark.asyncio
    async def test_daily_spend_multiple_threads(self):
        store = CostStore()
        store._redis = None
        with patch.object(CostStore, "_get_redis", _no_redis):
            await store.update_session_total("t1", "alice", 100, 200, 1.0, 5.0, False)
            await store.update_session_total("t2", "alice", 200, 400, 2.5, 5.0, False)
            spent = await store.get_user_daily_spend("alice")
            assert spent == 3.5

    @pytest.mark.asyncio
    async def test_daily_spend_user_isolation(self):
        store = CostStore()
        store._redis = None
        with patch.object(CostStore, "_get_redis", _no_redis):
            await store.update_session_total("t1", "alice", 100, 200, 3.0, 5.0, False)
            await store.update_session_total("t2", "bob", 100, 200, 1.0, 5.0, False)
            alice_spent = await store.get_user_daily_spend("alice")
            bob_spent = await store.get_user_daily_spend("bob")
            assert alice_spent == 3.0
            assert bob_spent == 1.0

    @pytest.mark.asyncio
    async def test_check_daily_budget_within_limit(self):
        store = CostStore()
        store._redis = None
        with patch.object(CostStore, "_get_redis", _no_redis):
            await store.update_session_total("t1", "alice", 100, 200, 2.0, 5.0, False)
            within, spent, cap = await store.check_daily_budget("alice")
            assert within is True
            assert spent == 2.0
            assert cap == 5.0

    @pytest.mark.asyncio
    async def test_check_daily_budget_exceeded(self):
        store = CostStore()
        store._redis = None
        with patch.object(CostStore, "_get_redis", _no_redis):
            await store.update_session_total("t1", "alice", 100, 200, 6.0, 5.0, True)
            within, spent, cap = await store.check_daily_budget("alice")
            assert within is False
            assert spent == 6.0
            assert cap == 5.0


class TestCircuitBreaker:
    @pytest.mark.asyncio
    async def test_hourly_spend_zero_initially(self):
        store = CostStore()
        store._redis = None
        with patch.object(CostStore, "_get_redis", _no_redis):
            spent = await store.get_hourly_platform_spend()
            assert spent == 0.0

    @pytest.mark.asyncio
    async def test_hourly_spend_after_recording(self):
        store = CostStore()
        store._redis = None
        with patch.object(CostStore, "_get_redis", _no_redis):
            await store.update_session_total("t1", "alice", 100, 200, 10.0, 50.0, False)
            await store.update_session_total("t2", "bob", 100, 200, 20.0, 50.0, False)
            spent = await store.get_hourly_platform_spend()
            assert spent == 30.0

    @pytest.mark.asyncio
    async def test_circuit_breaker_not_tripped(self):
        store = CostStore()
        store._redis = None
        with patch.object(CostStore, "_get_redis", _no_redis):
            await store.update_session_total("t1", "alice", 100, 200, 10.0, 50.0, False)
            tripped, spent, cap = await store.check_circuit_breaker()
            assert tripped is False
            assert spent == 10.0
            assert cap == 50.0

    @pytest.mark.asyncio
    async def test_circuit_breaker_tripped(self):
        store = CostStore()
        store._redis = None
        with patch.object(CostStore, "_get_redis", _no_redis):
            await store.update_session_total("t1", "alice", 100, 200, 60.0, 50.0, True)
            tripped, spent, cap = await store.check_circuit_breaker()
            assert tripped is True
            assert spent == 60.0
            assert cap == 50.0

    @pytest.mark.asyncio
    async def test_circuit_breaker_disabled(self):
        store = CostStore()
        store._redis = None
        original = settings.CIRCUIT_BREAKER_ENABLED
        settings.CIRCUIT_BREAKER_ENABLED = False
        try:
            with patch.object(CostStore, "_get_redis", _no_redis):
                await store.update_session_total("t1", "alice", 100, 200, 100.0, 50.0, True)
                tripped, _spent, _cap = await store.check_circuit_breaker()
                assert tripped is False
        finally:
            settings.CIRCUIT_BREAKER_ENABLED = original
