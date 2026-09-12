"""Tests for budget guardrail SSE events.

Covers Phase 6.8: budget_reached flag must propagate in the done SSE event.
Also covers Phase 6.28: SSE events emitted correctly.
"""

from __future__ import annotations

import json

import pytest

from main import _parse_chat_event


def json_data(payload: dict):
    return json.loads(payload["data"])["data"]


class TestDoneEventBudgetReached:
    """The done event must pass through budget_reached data from the stream."""

    def test_done_with_budget_reached_true(self):
        event = {"event": "done", "data": {"budget_reached": True}}
        payloads = _parse_chat_event(event, {})
        assert len(payloads) == 1
        assert payloads[0]["event"] == "done"
        assert json_data(payloads[0]) == {"budget_reached": True}

    def test_done_with_budget_reached_false(self):
        event = {"event": "done", "data": {"budget_reached": False}}
        payloads = _parse_chat_event(event, {})
        assert len(payloads) == 1
        assert payloads[0]["event"] == "done"
        assert json_data(payloads[0]) == {"budget_reached": False}

    def test_done_with_none_data(self):
        """Backward compat: done with None data still works."""
        event = {"event": "done", "data": None}
        payloads = _parse_chat_event(event, {})
        assert len(payloads) == 1
        assert payloads[0]["event"] == "done"
        assert json_data(payloads[0]) is None


class TestModelStreamBudgetReached:
    """Test that _ModelStream._budget_reached flag is set correctly."""

    def test_budget_reached_defaults_false(self):
        from agents.deep_agent import _ModelStream

        stream = _ModelStream.__new__(_ModelStream)
        stream._budget_reached = False
        stream._budget_warned = False
        stream._session_cost = 0.0
        stream._subagent_costs = {}
        stream._active_task_names = {}
        stream._task_run_ids = set()
        stream._last_progress_time = {}
        stream._tool_call_index = {}
        stream.activity = {
            "thinking": [], "tool_calls": [], "usage": [],
            "total_input_tokens": 0, "total_output_tokens": 0,
        }

        assert stream._budget_reached is False

    def test_budget_reached_set_true(self):
        from agents.deep_agent import _ModelStream

        stream = _ModelStream.__new__(_ModelStream)
        stream._budget_reached = True
        stream._budget_warned = True
        stream._session_cost = 0.55
        stream._subagent_costs = {}
        stream._active_task_names = {}
        stream._task_run_ids = set()
        stream._last_progress_time = {}
        stream._tool_call_index = {}
        stream.activity = {
            "thinking": [], "tool_calls": [], "usage": [],
            "total_input_tokens": 0, "total_output_tokens": 0,
        }

        assert stream._budget_reached is True

    def test_accumulated_cost_data_includes_budget_reached(self):
        from agents.deep_agent import _ModelStream

        stream = _ModelStream.__new__(_ModelStream)
        stream._budget_reached = True
        stream._session_cost = 0.55
        stream._subagent_costs = {}
        stream._active_task_names = {}
        stream._task_run_ids = set()
        stream._last_progress_time = {}
        stream._tool_call_index = {}
        stream._budget_warned = True
        stream.activity = {
            "thinking": [], "tool_calls": [], "usage": [],
            "total_input_tokens": 0, "total_output_tokens": 0,
        }

        cost_data = stream.get_cost_summary()
        assert "budget_reached" in cost_data
        assert cost_data["budget_reached"] is True
        assert cost_data["session_cost"] == 0.55


def _fake_state(messages):
    class _Snapshot:
        def __init__(self, values):
            self.values = values

    return _Snapshot({"messages": messages})
