"""Tests for Phase 7.4: Cost monitoring & observability.

Tests live cost breakdown, platform alerting, Prometheus metrics,
and structured JSON logging — all using SQLite fallback (no Redis).
"""

from __future__ import annotations

import io
import json
import logging
import os
import tempfile
import time
from unittest.mock import patch

import pytest
import pytest_asyncio

# Patch the SQLite fallback DB path BEFORE importing store modules
_tmpdir = tempfile.mkdtemp(prefix="voyager_test_")
_test_db_path = os.path.join(_tmpdir, "test_cost_monitoring.sqlite")
os.environ["SQLITE_FALLBACK_DB_PATH"] = _test_db_path

from config import settings  # noqa: E402
settings.SQLITE_FALLBACK_DB_PATH = _test_db_path

import sqlite_fallback  # noqa: E402
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
# get_live_costs — per-hour cost breakdown
# ---------------------------------------------------------------------------


class TestGetLiveCosts:
    @pytest.mark.asyncio
    async def test_empty_returns_empty_list(self):
        store = CostStore()
        with patch.object(CostStore, "_get_redis", _no_redis):
            result = await store.get_live_costs(hours=24)
            assert result == []

    @pytest.mark.asyncio
    async def test_returns_per_hour_breakdown(self):
        store = CostStore()
        with patch.object(CostStore, "_get_redis", _no_redis):
            await store.update_session_total(
                thread_id="t1", user_id="alice",
                total_input_tokens=100, total_output_tokens=50,
                total_cost_usd=0.05, budget_limit_usd=0.50,
                budget_reached=False,
            )
            await store.update_session_total(
                thread_id="t2", user_id="bob",
                total_input_tokens=200, total_output_tokens=100,
                total_cost_usd=0.10, budget_limit_usd=0.50,
                budget_reached=False,
            )

            result = await store.get_live_costs(hours=24)
            assert len(result) == 1  # Both in the same hour
            assert result[0]["cost"] == pytest.approx(0.15, abs=1e-6)
            assert result[0]["requests"] == 2
            assert result[0]["tokens_in"] == 300
            assert result[0]["tokens_out"] == 150

    @pytest.mark.asyncio
    async def test_excludes_old_sessions(self):
        store = CostStore()
        with patch.object(CostStore, "_get_redis", _no_redis):
            await store.update_session_total(
                thread_id="t1", user_id="alice",
                total_input_tokens=100, total_output_tokens=50,
                total_cost_usd=0.05, budget_limit_usd=0.50,
                budget_reached=False,
            )
            # Backdate the session in SQLite
            db = await sqlite_fallback.get_sqlite_connection()
            old_ts = time.time() - 100000
            await db.execute(
                "UPDATE costs_session SET created_at = ? WHERE thread_id = ?",
                (old_ts, "t1"),
            )
            await db.commit()

            result = await store.get_live_costs(hours=24)
            assert result == []

    @pytest.mark.asyncio
    async def test_hourly_grouping(self):
        store = CostStore()
        with patch.object(CostStore, "_get_redis", _no_redis):
            await store.update_session_total(
                thread_id="t1", user_id="alice",
                total_input_tokens=100, total_output_tokens=50,
                total_cost_usd=0.05, budget_limit_usd=0.50,
                budget_reached=False,
            )
            await store.update_session_total(
                thread_id="t2", user_id="bob",
                total_input_tokens=200, total_output_tokens=100,
                total_cost_usd=0.10, budget_limit_usd=0.50,
                budget_reached=False,
            )
            # Backdate t2 by 2 hours in SQLite
            db = await sqlite_fallback.get_sqlite_connection()
            old_ts = time.time() - 7200
            await db.execute(
                "UPDATE costs_session SET created_at = ? WHERE thread_id = ?",
                (old_ts, "t2"),
            )
            await db.commit()

            result = await store.get_live_costs(hours=24)
            assert len(result) == 2  # Two different hour buckets
            # Sorted by hour ascending — older one first
            assert result[0]["cost"] == pytest.approx(0.10, abs=1e-6)
            assert result[1]["cost"] == pytest.approx(0.05, abs=1e-6)


# ---------------------------------------------------------------------------
# check_platform_alerts — alert thresholds
# ---------------------------------------------------------------------------


class TestCheckPlatformAlerts:
    @pytest.mark.asyncio
    async def test_ok_when_no_spend(self):
        store = CostStore()
        with patch.object(CostStore, "_get_redis", _no_redis):
            result = await store.check_platform_alerts()
            assert result["level"] == "ok"
            assert result["daily_spend"] == 0.0
            assert result["percentage"] == 0.0

    @pytest.mark.asyncio
    async def test_ok_when_under_threshold(self):
        store = CostStore()
        with patch.object(CostStore, "_get_redis", _no_redis):
            # Daily cap = HOURLY_PLATFORM_CAP_USD * 24 = 50 * 24 = 1200
            await store.update_session_total(
                thread_id="t1", user_id="alice",
                total_input_tokens=100, total_output_tokens=50,
                total_cost_usd=1.0, budget_limit_usd=0.50,
                budget_reached=False,
            )
            result = await store.check_platform_alerts()
            assert result["level"] == "ok"
            assert result["daily_spend"] == pytest.approx(1.0, abs=1e-6)

    @pytest.mark.asyncio
    async def test_warning_at_threshold(self):
        store = CostStore()
        with patch.object(CostStore, "_get_redis", _no_redis):
            original_cap = settings.HOURLY_PLATFORM_CAP_USD
            original_threshold = settings.ALERT_DAILY_THRESHOLD_PCT
            settings.HOURLY_PLATFORM_CAP_USD = 1.0  # daily cap = 24
            settings.ALERT_DAILY_THRESHOLD_PCT = 0.8  # 80% = 19.2
            await store.update_session_total(
                thread_id="t1", user_id="alice",
                total_input_tokens=100, total_output_tokens=50,
                total_cost_usd=20.0, budget_limit_usd=0.50,
                budget_reached=False,
            )
            result = await store.check_platform_alerts()
            assert result["level"] == "warning"
            assert result["percentage"] >= 80.0
            settings.HOURLY_PLATFORM_CAP_USD = original_cap
            settings.ALERT_DAILY_THRESHOLD_PCT = original_threshold

    @pytest.mark.asyncio
    async def test_critical_at_cap(self):
        store = CostStore()
        with patch.object(CostStore, "_get_redis", _no_redis):
            original_cap = settings.HOURLY_PLATFORM_CAP_USD
            settings.HOURLY_PLATFORM_CAP_USD = 1.0  # daily cap = 24
            await store.update_session_total(
                thread_id="t1", user_id="alice",
                total_input_tokens=100, total_output_tokens=50,
                total_cost_usd=25.0, budget_limit_usd=0.50,
                budget_reached=False,
            )
            result = await store.check_platform_alerts()
            assert result["level"] == "critical"
            assert result["percentage"] >= 100.0
            settings.HOURLY_PLATFORM_CAP_USD = original_cap

    @pytest.mark.asyncio
    async def test_alert_excludes_old_sessions(self):
        store = CostStore()
        with patch.object(CostStore, "_get_redis", _no_redis):
            await store.update_session_total(
                thread_id="t1", user_id="alice",
                total_input_tokens=100, total_output_tokens=50,
                total_cost_usd=100.0, budget_limit_usd=0.50,
                budget_reached=False,
            )
            # Backdate to yesterday in SQLite
            db = await sqlite_fallback.get_sqlite_connection()
            old_ts = time.time() - 100000
            await db.execute(
                "UPDATE costs_session SET created_at = ? WHERE thread_id = ?",
                (old_ts, "t1"),
            )
            await db.commit()

            result = await store.check_platform_alerts()
            assert result["level"] == "ok"
            assert result["daily_spend"] == 0.0


# ---------------------------------------------------------------------------
# Prometheus metrics — verify counters exist and increment
# ---------------------------------------------------------------------------


class TestPrometheusMetrics:
    def test_metrics_are_registered(self):
        from metrics import (
            LLM_CALLS_TOTAL,
            LLM_TOKENS_TOTAL,
            LLM_COST_TOTAL,
            CIRCUIT_BREAKER_STATUS,
            DAILY_PLATFORM_SPEND,
            HOURLY_PLATFORM_SPEND,
            ACTIVE_SESSIONS,
            RATE_LIMIT_HITS_TOTAL,
        )
        # Prometheus strips _total suffix from Counter._name internally
        assert LLM_CALLS_TOTAL._name == "voyager_llm_calls"
        assert LLM_TOKENS_TOTAL._name == "voyager_llm_tokens"
        assert LLM_COST_TOTAL._name == "voyager_llm_cost_usd"
        # Gauges keep their full name
        assert CIRCUIT_BREAKER_STATUS._name == "voyager_circuit_breaker_status"
        assert DAILY_PLATFORM_SPEND._name == "voyager_daily_platform_spend_usd"
        assert HOURLY_PLATFORM_SPEND._name == "voyager_hourly_platform_spend_usd"
        assert ACTIVE_SESSIONS._name == "voyager_active_sessions"
        assert RATE_LIMIT_HITS_TOTAL._name == "voyager_rate_limit_hits"

    def test_llm_calls_counter_increments(self):
        from metrics import LLM_CALLS_TOTAL
        counter = LLM_CALLS_TOTAL.labels(model="test_model", subagent="test_subagent")
        before = counter._value.get()
        counter.inc()
        assert counter._value.get() == before + 1

    def test_llm_cost_counter_increments(self):
        from metrics import LLM_COST_TOTAL
        counter = LLM_COST_TOTAL.labels(model="test_model")
        before = counter._value.get()
        counter.inc(0.05)
        assert counter._value.get() == pytest.approx(before + 0.05, abs=1e-6)

    def test_gauges_set_values(self):
        from metrics import DAILY_PLATFORM_SPEND, HOURLY_PLATFORM_SPEND
        DAILY_PLATFORM_SPEND.set(42.5)
        HOURLY_PLATFORM_SPEND.set(3.2)
        assert DAILY_PLATFORM_SPEND._value.get() == 42.5
        assert HOURLY_PLATFORM_SPEND._value.get() == 3.2


# ---------------------------------------------------------------------------
# Structured JSON logging — verify JSON output
# ---------------------------------------------------------------------------


class TestStructuredLogging:
    def test_json_log_format_produces_valid_json(self):
        from logging_config import configure_logging, set_request_context

        configure_logging(fmt="json", level="DEBUG")
        set_request_context(request_id="test-req-123")

        # Capture log output via a stream
        log_stream = io.StringIO()
        root = logging.getLogger()
        handler = logging.StreamHandler(log_stream)
        if root.handlers and root.handlers[0].filters:
            handler.addFilter(root.handlers[0].filters[0])
        if root.handlers:
            handler.setFormatter(root.handlers[0].formatter)
        root.addHandler(handler)

        test_logger = logging.getLogger("test.metrics")
        test_logger.info("Test message for JSON logging")

        root.removeHandler(handler)
        log_output = log_stream.getvalue().strip()
        assert log_output
        parsed = json.loads(log_output)
        assert parsed["message"] == "Test message for JSON logging"
        assert parsed["request_id"] == "test-req-123"
        assert parsed["level"] == "INFO"

    def test_text_log_format_works(self):
        from logging_config import configure_logging

        configure_logging(fmt="text", level="DEBUG")

        log_stream = io.StringIO()
        root = logging.getLogger()
        handler = logging.StreamHandler(log_stream)
        if root.handlers and root.handlers[0].filters:
            handler.addFilter(root.handlers[0].filters[0])
        if root.handlers:
            handler.setFormatter(root.handlers[0].formatter)
        root.addHandler(handler)

        test_logger = logging.getLogger("test.metrics.text")
        test_logger.info("Text format test message")

        root.removeHandler(handler)
        log_output = log_stream.getvalue().strip()
        assert "Text format test message" in log_output
        assert not log_output.startswith("{")

    def test_request_context_sets_and_gets(self):
        from logging_config import set_request_context, get_log_context, generate_request_id

        req_id = generate_request_id()
        set_request_context(request_id=req_id, user_id="alice", thread_id="t1")
        ctx = get_log_context()
        assert ctx["request_id"] == req_id
        assert ctx["user_id"] == "alice"
        assert ctx["thread_id"] == "t1"


# ---------------------------------------------------------------------------
# Bug #4 — update_session_total must preserve created_at
# Bug #5 — daily window must be computed in UTC, not local time
# ---------------------------------------------------------------------------


class TestCreatedAtPreserved:
    @pytest.mark.asyncio
    async def test_update_session_total_preserves_created_at(self):
        """Second update on the same thread keeps the original created_at."""
        store = CostStore()
        with patch.object(CostStore, "_get_redis", _no_redis):
            await store.update_session_total(
                thread_id="t1", user_id="alice",
                total_input_tokens=100, total_output_tokens=50,
                total_cost_usd=0.05, budget_limit_usd=0.50,
                budget_reached=False,
            )
            first = await store.get_session_cost("t1")
            assert first is not None
            original_created = first["created_at"]

            time.sleep(0.05)
            await store.update_session_total(
                thread_id="t1", user_id="alice",
                total_input_tokens=200, total_output_tokens=100,
                total_cost_usd=0.15, budget_limit_usd=0.50,
                budget_reached=False,
            )
            second = await store.get_session_cost("t1")
            assert second is not None
            assert second["created_at"] == pytest.approx(original_created, abs=1e-6)
            assert second["total_cost_usd"] == pytest.approx(0.15, abs=1e-6)

    @pytest.mark.asyncio
    async def test_resumed_old_thread_not_counted_in_hourly_spend(self):
        """A resumed old thread's cumulative cost must not enter the last-hour window."""
        store = CostStore()
        with patch.object(CostStore, "_get_redis", _no_redis):
            await store.update_session_total(
                thread_id="t1", user_id="alice",
                total_input_tokens=100, total_output_tokens=50,
                total_cost_usd=0.05, budget_limit_usd=0.50,
                budget_reached=False,
            )
            # Backdate the session to 3 hours ago
            db = await sqlite_fallback.get_sqlite_connection()
            old_ts = time.time() - 3 * 3600
            await db.execute(
                "UPDATE costs_session SET created_at = ? WHERE thread_id = ?",
                (old_ts, "t1"),
            )
            await db.commit()

            # Resume the thread — cumulative total grows
            await store.update_session_total(
                thread_id="t1", user_id="alice",
                total_input_tokens=200, total_output_tokens=100,
                total_cost_usd=0.50, budget_limit_usd=0.50,
                budget_reached=False,
            )

            assert await store.get_hourly_platform_spend() == 0.0


class TestUtcStartOfDay:
    def test_aligned_to_epoch_day(self):
        """Result must be an exact multiple of 86400 — true UTC midnight."""
        from cost_store import _utc_start_of_day
        ts = 1789756237.5  # arbitrary instant
        result = _utc_start_of_day(ts)
        assert result % 86400 == 0
        assert result <= ts < result + 86400

    def test_independent_of_local_tz(self):
        """Result must not change with the TZ environment variable."""
        from cost_store import _utc_start_of_day
        ts = 1789756237.5
        expected = _utc_start_of_day(ts)
        for tz in ("America/New_York", "Asia/Kolkata", "Pacific/Auckland"):
            os.environ["TZ"] = tz
            time.tzset()
            try:
                assert _utc_start_of_day(ts) == expected
            finally:
                os.environ.pop("TZ", None)
                time.tzset()

    @pytest.mark.asyncio
    async def test_daily_spend_boundary_utc(self):
        """Sessions just before UTC midnight excluded; just after included."""
        from cost_store import _utc_start_of_day
        store = CostStore()
        with patch.object(CostStore, "_get_redis", _no_redis):
            now = time.time()
            sod = _utc_start_of_day(now)
            await store.update_session_total(
                thread_id="old", user_id="alice",
                total_input_tokens=10, total_output_tokens=5,
                total_cost_usd=1.0, budget_limit_usd=10.0,
                budget_reached=False,
            )
            await store.update_session_total(
                thread_id="new", user_id="alice",
                total_input_tokens=10, total_output_tokens=5,
                total_cost_usd=2.0, budget_limit_usd=10.0,
                budget_reached=False,
            )
            db = await sqlite_fallback.get_sqlite_connection()
            await db.execute(
                "UPDATE costs_session SET created_at = ? WHERE thread_id = 'old'",
                (sod - 1,),
            )
            await db.execute(
                "UPDATE costs_session SET created_at = ? WHERE thread_id = 'new'",
                (sod + 1,),
            )
            await db.commit()
            assert await store.get_user_daily_spend("alice") == pytest.approx(2.0, abs=1e-6)
