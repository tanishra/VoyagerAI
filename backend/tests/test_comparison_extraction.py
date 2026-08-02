"""Tests for comparison (multi-plan) extraction from streamed text."""

from __future__ import annotations

import json

from agents.deep_agent import (
    _extract_comparison_from_text,
    _find_largest_comparison_object,
)

_SAMPLE_COMPARISON = {
    "plans": [
        {
            "tier": "budget",
            "itinerary": {"destination": "Tokyo", "total_days": 3, "days": []},
            "cost_breakdown": {"accommodation": 150, "food": 120, "activities": 200, "transport": 80, "total": 720},
            "tradeoffs": ["Budget: street food only"],
        },
        {
            "tier": "balanced",
            "itinerary": {"destination": "Tokyo", "total_days": 3, "days": []},
            "cost_breakdown": {"accommodation": 300, "food": 200, "activities": 300, "transport": 150, "total": 1200},
            "tradeoffs": ["Balanced: mid-range hotels"],
        },
        {
            "tier": "premium",
            "itinerary": {"destination": "Tokyo", "total_days": 3, "days": []},
            "cost_breakdown": {"accommodation": 500, "food": 400, "activities": 500, "transport": 300, "total": 1800},
            "tradeoffs": ["Premium: 4-star hotels"],
        },
    ],
    "comparison_matrix": {
        "total_cost": {"budget": 720, "balanced": 1200, "premium": 1800},
        "accommodation_type": {"budget": "Hostel", "balanced": "3-star", "premium": "4-star"},
        "food_style": {"budget": "Street food", "balanced": "Local restaurants", "premium": "Fine dining"},
        "activity_count": {"budget": 9, "balanced": 9, "premium": 9},
        "transport_mode": {"budget": "Public transit", "balanced": "Transit + rideshare", "premium": "Taxi/rental"},
    },
}


class TestComparisonTagExtraction:
    def test_extracts_from_comparison_tags(self):
        text = f"Here are your plans:\n<comparison>{json.dumps(_SAMPLE_COMPARISON)}</comparison>"
        result = _extract_comparison_from_text(text)
        assert result is not None
        assert len(result["plans"]) == 3
        assert result["plans"][0]["tier"] == "budget"

    def test_returns_none_for_empty_text(self):
        assert _extract_comparison_from_text("") is None
        assert _extract_comparison_from_text(None) is None

    def test_returns_none_for_text_without_comparison(self):
        assert _extract_comparison_from_text("Just a regular chat message") is None

    def test_handles_invalid_json_in_tags(self):
        text = "<comparison>not valid json</comparison>"
        result = _extract_comparison_from_text(text)
        assert result is None


class TestComparisonFallbackExtraction:
    def test_finds_largest_comparison_object(self):
        text = f"Here are plans: {json.dumps(_SAMPLE_COMPARISON)} end."
        result = _find_largest_comparison_object(text)
        assert result is not None
        assert "plans" in result
        assert len(result["plans"]) == 3

    def test_returns_none_for_itinerary_json(self):
        itinerary_json = json.dumps({"destination": "Tokyo", "days": []})
        assert _find_largest_comparison_object(itinerary_json) is None

    def test_returns_none_for_plain_text(self):
        assert _find_largest_comparison_object("no json here") is None
