"""Tests for cost tracking, budget guardrails, and admin analytics."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pricing import calculate_cost, get_pricing, PRICING_TABLE, DEFAULT_PRICING
from cost_store import CostStore
from config.settings import settings


# --- Pricing tests ---

class TestPricing:
    def test_calculate_cost_known_model(self):
        """Cost calculation is correct for a known model."""
        # gemini/gemini-3.7-flash: $0.0003/1k input, $0.0006/1k output
        cost = calculate_cost("gemini/gemini-3.7-flash", 1000, 1000)
        assert cost == pytest.approx(0.0009, rel=1e-3)

    def test_calculate_cost_unknown_model(self):
        """Unknown model falls back to default pricing (no crash)."""
        cost = calculate_cost("unknown/fake-model", 1000, 1000)
        expected = (1000 / 1000 * DEFAULT_PRICING["input_per_1k"]) + (
            1000 / 1000 * DEFAULT_PRICING["output_per_1k"]
        )
        assert cost == pytest.approx(expected, rel=1e-6)

    def test_calculate_cost_zero_tokens(self):
        """Zero tokens = zero cost."""
        cost = calculate_cost("gemini/gemini-3.7-flash", 0, 0)
        assert cost == 0.0

    def test_get_pricing_returns_table_entry(self):
        """get_pricing returns the correct table entry for a known model."""
        pricing = get_pricing("openai/gpt-4o")
        assert pricing["input_per_1k"] == 0.0025
        assert pricing["output_per_1k"] == 0.01

    def test_get_pricing_returns_default_for_unknown(self):
        """get_pricing returns default for unknown model."""
        pricing = get_pricing("unknown/model")
        assert pricing == DEFAULT_PRICING


# --- CostStore tests (in-memory fallback) ---

class TestCostStore:
    @pytest.fixture
    def store(self):
        """Create a CostStore that uses in-memory fallback (no Redis)."""
        s = CostStore()
        s._redis = None  # Force in-memory mode
        return s

    @pytest.mark.asyncio
    async def test_record_and_get_subagent_cost(self, store):
        """Record subagent cost and retrieve it."""
        await store.record_subagent_cost(
            thread_id="test-thread-1",
            user_id="user1",
            subagent_name="researcher",
            input_tokens=500,
            output_tokens=200,
            cost_usd=0.001,
            model_used="gemini/gemini-3.5-flash-lite",
        )
        breakdown = await store.get_subagent_breakdown("test-thread-1")
        assert len(breakdown) == 1
        assert breakdown[0]["subagent_name"] == "researcher"
        assert breakdown[0]["input_tokens"] == 500
        assert breakdown[0]["output_tokens"] == 200
        assert breakdown[0]["cost_usd"] == 0.001

    @pytest.mark.asyncio
    async def test_update_and_get_session_total(self, store):
        """Update session total and retrieve it."""
        await store.update_session_total(
            thread_id="test-thread-2",
            user_id="user2",
            total_input_tokens=2000,
            total_output_tokens=800,
            total_cost_usd=0.005,
            budget_limit_usd=0.50,
            budget_reached=False,
        )
        result = await store.get_session_cost("test-thread-2")
        assert result is not None
        assert result["total_input_tokens"] == 2000
        assert result["total_output_tokens"] == 800
        assert result["total_cost_usd"] == 0.005
        assert result["budget_reached"] is False
        # efficiency_ratio = input / max(output, 1) = 2000/800 = 2.5
        assert result["efficiency_ratio"] == pytest.approx(2.5, rel=1e-2)

    @pytest.mark.asyncio
    async def test_aggregate_stats_multiple_sessions(self, store):
        """Aggregate stats correctly across multiple sessions."""
        await store.update_session_total(
            "t1", "user1", 1000, 500, 0.003, 0.50, False,
        )
        await store.update_session_total(
            "t2", "user2", 2000, 1000, 0.006, 0.50, False,
        )
        await store.record_subagent_cost(
            "t1", "user1", "researcher", 500, 200, 0.001, "gemini/gemini-3.5-flash-lite",
        )
        await store.record_subagent_cost(
            "t2", "user2", "validator", 300, 100, 0.0005, "gemini/gemini-3.5-flash-lite",
        )

        stats = await store.get_aggregate_stats(period="month")
        assert stats["total_conversations"] == 2
        assert stats["total_cost"] == pytest.approx(0.009, rel=1e-2)
        assert stats["avg_cost_per_conversation"] == pytest.approx(0.0045, rel=1e-2)
        assert len(stats["per_subagent"]) == 2
        assert len(stats["top_users"]) == 2

    @pytest.mark.asyncio
    async def test_efficiency_ratio_poor(self, store):
        """Sessions with >50:1 ratio are flagged in poor_efficiency_sessions."""
        await store.update_session_total(
            "t-poor", "user1", 5000, 50, 0.01, 0.50, False,
        )
        stats = await store.get_aggregate_stats(period="month")
        assert len(stats["poor_efficiency_sessions"]) == 1
        assert stats["poor_efficiency_sessions"][0]["thread_id"] == "t-poor"
        assert stats["poor_efficiency_sessions"][0]["efficiency_ratio"] == pytest.approx(100.0, rel=1e-1)

    @pytest.mark.asyncio
    async def test_empty_stats(self, store):
        """Empty store returns zero stats."""
        stats = await store.get_aggregate_stats(period="week")
        assert stats["total_cost"] == 0.0
        assert stats["total_conversations"] == 0
        assert stats["per_day"] == []
        assert stats["per_subagent"] == []


# --- Budget guardrail tests ---

class TestBudgetGuardrails:
    def test_budget_check_under_limit(self):
        """_check_budget returns False when under limit."""
        from agents.deep_agent import _ModelStream
        stream = _ModelStream.__new__(_ModelStream)
        stream._session_cost = 0.10
        stream._budget_reached = False
        stream._budget_warned = False
        stream._subagent_costs = {}
        stream._active_task_names = {}
        stream._task_run_ids = set()
        stream._last_progress_time = {}
        stream._tool_call_index = {}
        stream.activity = {
            "thinking": [], "tool_calls": [], "usage": [],
            "total_input_tokens": 0, "total_output_tokens": 0,
        }
        # Default budget is 0.50
        assert stream._check_budget() is False

    def test_budget_check_at_limit(self):
        """_check_budget returns True when at limit."""
        from agents.deep_agent import _ModelStream
        stream = _ModelStream.__new__(_ModelStream)
        stream._session_cost = 0.50
        stream._budget_reached = False
        stream._budget_warned = False
        stream._subagent_costs = {}
        stream._active_task_names = {}
        stream._task_run_ids = set()
        stream._last_progress_time = {}
        stream._tool_call_index = {}
        stream.activity = {
            "thinking": [], "tool_calls": [], "usage": [],
            "total_input_tokens": 0, "total_output_tokens": 0,
        }
        assert stream._check_budget() is True

    def test_budget_check_over_limit(self):
        """_check_budget returns True when over limit."""
        from agents.deep_agent import _ModelStream
        stream = _ModelStream.__new__(_ModelStream)
        stream._session_cost = 0.75
        stream._budget_reached = False
        stream._budget_warned = False
        stream._subagent_costs = {}
        stream._active_task_names = {}
        stream._task_run_ids = set()
        stream._last_progress_time = {}
        stream._tool_call_index = {}
        stream.activity = {
            "thinking": [], "tool_calls": [], "usage": [],
            "total_input_tokens": 0, "total_output_tokens": 0,
        }
        assert stream._check_budget() is True

    def test_get_cost_summary(self):
        """get_cost_summary returns correct structure."""
        from agents.deep_agent import _ModelStream
        stream = _ModelStream.__new__(_ModelStream)
        stream._session_cost = 0.123456789
        stream._budget_reached = False
        stream._subagent_costs = {
            "researcher": {
                "input_tokens": 1000,
                "output_tokens": 500,
                "cost": 0.001,
                "model": "gemini/gemini-3.5-flash-lite",
            },
        }
        stream.activity = {
            "thinking": [], "tool_calls": [], "usage": [],
            "total_input_tokens": 1000,
            "total_output_tokens": 500,
        }
        summary = stream.get_cost_summary()
        assert summary["session_cost"] == 0.123457  # rounded to 6 decimals
        assert summary["budget_reached"] is False
        assert "researcher" in summary["subagent_costs"]
        assert summary["subagent_costs"]["researcher"]["cost"] == 0.001
        assert summary["total_input_tokens"] == 1000


# --- Admin endpoint tests ---

class TestAdminEndpoints:
    @pytest.mark.asyncio
    async def test_admin_rejects_non_admin(self):
        """Admin endpoint returns 403 for non-admin users."""
        from oauth import verify_admin
        from fastapi import HTTPException

        with patch.object(settings, "AUTH_DEV_BYPASS", False), \
             patch.object(settings, "ADMIN_EMAILS", "admin@example.com"):

            with pytest.raises(HTTPException) as exc_info:
                await verify_admin(user={"user_id": "u1", "email": "user@example.com"})
            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_rejects_when_not_configured(self):
        """Admin endpoint returns 403 when ADMIN_EMAILS is empty."""
        from oauth import verify_admin
        from fastapi import HTTPException

        with patch.object(settings, "AUTH_DEV_BYPASS", False), \
             patch.object(settings, "ADMIN_EMAILS", ""):

            with pytest.raises(HTTPException) as exc_info:
                await verify_admin(user={"user_id": "u1", "email": "user@example.com"})
            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_allows_admin_user(self):
        """Admin endpoint allows admin users."""
        from oauth import verify_admin

        with patch.object(settings, "AUTH_DEV_BYPASS", False), \
             patch.object(settings, "ADMIN_EMAILS", "admin@example.com,other@admin.com"):

            result = await verify_admin(user={"user_id": "u1", "email": "admin@example.com"})
            assert result["email"] == "admin@example.com"

    @pytest.mark.asyncio
    async def test_admin_dev_bypass(self):
        """Admin endpoint allows dev bypass."""
        from oauth import verify_admin

        with patch.object(settings, "AUTH_DEV_BYPASS", True), \
             patch.object(settings, "ADMIN_EMAILS", ""):

            result = await verify_admin(user={"user_id": "dev", "email": "dev@localhost"})
            assert result is not None
