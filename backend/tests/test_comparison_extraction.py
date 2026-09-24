"""Tests for comparison (multi-plan) extraction from streamed text."""

from __future__ import annotations

import json

from agents.deep_agent import (
    _detect_plan_kind,
    _extract_comparison_from_text,
    _find_largest_comparison_object,
    _format_comparison,
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


class TestFormatComparison:
    """Tests for the _format_comparison structured-recovery pass."""

    def test_returns_dict_on_success(self, monkeypatch):
        from agents import deep_agent as _da

        class _MockResult:
            def model_dump(self):
                return _SAMPLE_COMPARISON

        async def _fake_ainvoke(self, messages):
            return _MockResult()

        monkeypatch.setattr(_da, "_comparison_formatter_model", type("M", (), {"ainvoke": _fake_ainvoke})())
        result = _format_comparison.__wrapped__("draft text", "user msg") if hasattr(_format_comparison, "__wrapped__") else None

        # If not wrapped, call directly via asyncio
        if result is None:
            import asyncio as _aio

            result = _aio.run(_format_comparison("draft text", "user msg"))
        assert result is not None
        assert "plans" in result
        assert len(result["plans"]) == 3

    def test_returns_none_on_exception(self, monkeypatch):
        import asyncio as _aio

        from agents import deep_agent as _da

        async def _raising_ainvoke(self, messages):
            raise RuntimeError("model down")

        monkeypatch.setattr(_da, "_comparison_formatter_model", type("M", (), {"ainvoke": _raising_ainvoke})())
        result = _aio.run(_format_comparison("draft", "msg"))
        assert result is None


class TestComparisonProseParsing:
    """Models sometimes emit tier plans as markdown prose instead of
    <comparison> JSON. The deterministic prose parser must recover them."""

    _PROSE = (
        "Here are three different itinerary options for your 5-day trip to Tokyo, "
        "each catering to different budget levels:\n"
        "Budget Plan\n"
        "- Total Cost: ₹45,000\n"
        "- Accommodation: Hostel\n"
        "- Food Style: Street food\n"
        "- Transport: Public transit\n"
        "- Highlights: Explore cultural sites like Senso-ji Temple.\n"
        "Balanced Plan\n"
        "- Total Cost: ₹75,000\n"
        "- Accommodation: 3-star hotel\n"
        "- Food Style: Local restaurants\n"
        "- Transport: Transit + occasional rideshare\n"
        "- Highlights: Visit Akihabara and shop in Harajuku.\n"
        "Premium Plan\n"
        "- Total Cost: ₹1,12,500\n"
        "- Accommodation: 4-star hotel\n"
        "- Food Style: Fine dining\n"
        "- Transport: Private car\n"
        "- Highlights: High-end dining and private tours.\n"
        "Which tier do you prefer?"
    )

    def test_parses_untagged_tier_prose(self):
        result = _extract_comparison_from_text(self._PROSE)
        assert result is not None
        tiers = [p["tier"] for p in result["plans"]]
        assert tiers == ["budget", "balanced", "premium"]

    def test_parses_costs_including_indian_grouping(self):
        result = _extract_comparison_from_text(self._PROSE)
        costs = [p["itinerary"]["estimated_total_cost_usd"] for p in result["plans"]]
        assert costs == [45000.0, 75000.0, 112500.0]

    def test_extracts_destination_and_days(self):
        result = _extract_comparison_from_text(self._PROSE)
        assert result["plans"][0]["itinerary"]["destination"] == "Tokyo"
        assert result["plans"][0]["itinerary"]["total_days"] == 5

    def test_builds_comparison_matrix(self):
        result = _extract_comparison_from_text(self._PROSE)
        m = result["comparison_matrix"]
        assert m["total_cost"]["premium"] == 112500.0
        assert m["accommodation_type"]["budget"] == "Hostel"
        assert m["food_style"]["balanced"] == "Local restaurants"
        assert m["transport_mode"]["premium"] == "Private car"

    def test_single_tier_prose_returns_none(self):
        text = "Budget Plan\n- Total Cost: ₹45,000\nJust one plan here."
        assert _extract_comparison_from_text(text) is None

    def test_prefers_tagged_json_over_prose(self):
        text = f"Budget Plan\n- Total Cost: 1\nBalanced Plan\n- Total Cost: 2\n<comparison>{json.dumps(_SAMPLE_COMPARISON)}</comparison>"
        result = _extract_comparison_from_text(text)
        assert result == _SAMPLE_COMPARISON


class TestDetectPlanKind:
    """Tests for the _detect_plan_kind shared dispatcher."""

    def test_comparison_tag_detected(self):
        import asyncio as _aio

        text = f"<comparison>{json.dumps(_SAMPLE_COMPARISON)}</comparison>"
        assert _aio.run(_detect_plan_kind(text)) == "comparison"

    def test_itinerary_tag_detected(self):
        import asyncio as _aio

        text = '<itinerary>{"destination": "Paris", "days": []}</itinerary>'
        assert _aio.run(_detect_plan_kind(text)) == "itinerary"

    def test_comparison_heuristic_detected(self):
        import asyncio as _aio

        text = (
            "Budget Plan\nAccommodation: Hostel\nTotal Cost: ₹90\n\n"
            "Balanced Plan\nAccommodation: Hotel\nTotal Cost: ₹270\n"
        )
        assert _aio.run(_detect_plan_kind(text)) == "comparison"

    def test_itinerary_heuristic_detected(self):
        import asyncio as _aio

        text = (
            "Day 1: Explore\nMorning: Visit museum\nAfternoon: Walk\nEvening: Dinner\n"
            "Day 2: More\nMorning: Cafe\nAfternoon: Park\nEvening: Show\n"
        )
        assert _aio.run(_detect_plan_kind(text)) == "itinerary"

    def test_none_for_empty_text(self):
        import asyncio as _aio

        assert _aio.run(_detect_plan_kind("")) == "none"
        assert _aio.run(_detect_plan_kind(None)) == "none"

    def test_classifier_fallback_returns_none_for_short_text(self):
        import asyncio as _aio

        assert _aio.run(_detect_plan_kind("Short conversational reply")) == "none"
