"""Tests for tool functions — validate_constraints (pure logic), dispatch map."""

from __future__ import annotations

import pytest

from tools import (
    tool_validate_constraints,
    TOOL_DISPATCH,
)


class TestValidateConstraints:
    def test_valid_itinerary_within_budget(self, sample_itinerary_dict):
        result = tool_validate_constraints(
            sample_itinerary_dict, budget_usd=1000
        )
        assert result["valid"] is True
        assert result["budget_status"] == "within"
        assert result["calculated_total_cost"] == 750
        assert result["issues"] == []

    def test_valid_itinerary_under_budget(self, sample_itinerary_dict):
        result = tool_validate_constraints(
            sample_itinerary_dict, budget_usd=2000
        )
        assert result["valid"] is True
        assert result["budget_status"] == "under"
        assert result["calculated_total_cost"] == 750

    def test_over_budget(self, sample_itinerary_dict):
        result = tool_validate_constraints(
            sample_itinerary_dict, budget_usd=500
        )
        assert result["valid"] is False
        assert result["budget_status"] == "over"
        assert "exceeds budget" in result["issues"][0]

    def test_under_budget(self, sample_itinerary_dict):
        result = tool_validate_constraints(
            sample_itinerary_dict, budget_usd=5000
        )
        assert result["valid"] is True
        assert result["budget_status"] == "under"
        assert "less than 50%" in result["warnings"][0]

    def test_day_count_mismatch(self, sample_itinerary_dict):
        data = dict(sample_itinerary_dict)
        data["total_days"] = 5
        result = tool_validate_constraints(data, budget_usd=2000)
        assert result["valid"] is False
        assert any("Day count mismatch" in i for i in result["issues"])

    def test_cost_mismatch_warning(self, sample_itinerary_dict):
        data = dict(sample_itinerary_dict)
        data["estimated_total_cost_usd"] = 9999
        result = tool_validate_constraints(data, budget_usd=2000)
        assert result["valid"] is True
        assert any("differs from sum" in w for w in result["warnings"])

    def test_activity_cost_exceeds_daily(self):
        data = {
            "destination": "Test",
            "total_days": 1,
            "estimated_total_cost_usd": 200,
            "budget_status": "within",
            "visa_note": "",
            "best_season_note": "",
            "days": [
                {
                    "day": 1,
                    "theme": "Test",
                    "morning": {"activity": "A", "location": "L", "cost_usd": 100, "duration": "1h"},
                    "afternoon": {"activity": "A", "location": "L", "cost_usd": 100, "duration": "1h"},
                    "evening": {"activity": "A", "location": "L", "cost_usd": 100, "duration": "1h"},
                    "transport": "Walk",
                    "accommodation": "None",
                    "daily_cost_usd": 200,
                    "tips": [],
                }
            ],
            "warnings": [],
            "packing_essentials": [],
        }
        result = tool_validate_constraints(data, budget_usd=500)
        assert result["valid"] is True
        assert any("activity costs" in w for w in result["warnings"])

    def test_dietary_warning(self, sample_itinerary_dict):
        result = tool_validate_constraints(
            sample_itinerary_dict, budget_usd=2000, dietary="vegan"
        )
        assert any("vegan" in w.lower() for w in result["warnings"])

    def test_constraints_warning(self, sample_itinerary_dict):
        result = tool_validate_constraints(
            sample_itinerary_dict, budget_usd=2000, constraints="wheelchair accessible"
        )
        assert any("wheelchair" in w.lower() for w in result["warnings"])

    def test_lru_cache_hit(self, sample_itinerary_dict):
        result1 = tool_validate_constraints(sample_itinerary_dict, budget_usd=2000)
        result2 = tool_validate_constraints(sample_itinerary_dict, budget_usd=2000)
        assert result1 == result2

    def test_empty_itinerary(self):
        result = tool_validate_constraints(
            {"days": [], "total_days": 0, "estimated_total_cost_usd": 0},
            budget_usd=100,
        )
        assert result["valid"] is True
        assert result["calculated_total_cost"] == 0


class TestToolDispatch:
    def test_dispatch_has_all_tools(self):
        assert "generate_itinerary" in TOOL_DISPATCH
        assert "validate_constraints" in TOOL_DISPATCH
        assert "enrich_day" in TOOL_DISPATCH

    def test_dispatch_validate_is_sync(self):
        import inspect
        handler = TOOL_DISPATCH["validate_constraints"]
        assert not inspect.iscoroutinefunction(handler)

    def test_dispatch_generate_is_async(self):
        import inspect
        handler = TOOL_DISPATCH["generate_itinerary"]
        assert inspect.iscoroutinefunction(handler)

    def test_dispatch_enrich_is_async(self):
        import inspect
        handler = TOOL_DISPATCH["enrich_day"]
        assert inspect.iscoroutinefunction(handler)
