"""Tests for chat itinerary extraction — tagged and fallback JSON paths."""

from __future__ import annotations

from agents.deep_agent import (
    _extract_chat_itinerary,
    _looks_like_comparison_draft,
    _looks_like_itinerary_draft,
    _strip_untagged_plan_prose,
)


class _Msg:
    def __init__(self, content):
        self.content = content


def _state(content):
    return {"messages": [_Msg(content)]}


class TestTaggedItinerary:
    def test_extracts_from_tags(self):
        text = 'Here is the plan: <itinerary>{"destination": "Paris", "days": []}</itinerary> Enjoy!'
        assert _extract_chat_itinerary(_state(text)) == {"destination": "Paris", "days": []}

    def test_extracts_whitespace_padded_tags(self):
        text = '<itinerary>\n  {"destination": "Rome", "days": []}\n</itinerary>'
        assert _extract_chat_itinerary(_state(text)) == {"destination": "Rome", "days": []}

    def test_invalid_json_in_tags_falls_back(self):
        text = 'summary <itinerary>not json</itinerary> trailing {"destination": "Oslo", "days": []}'
        assert _extract_chat_itinerary(_state(text)) == {"destination": "Oslo", "days": []}


class TestFallbackExtraction:
    def test_extracts_plain_json_with_prose(self):
        text = 'Plan ready: {"destination": "Paris", "days": []} done!'
        assert _extract_chat_itinerary(_state(text)) == {"destination": "Paris", "days": []}

    def test_extracts_nested_json_object(self):
        text = '{"meta": "x", "destination": "Paris", "days": [{"day": 1}]}'
        out = _extract_chat_itinerary(_state(text))
        assert out == {"meta": "x", "destination": "Paris", "days": [{"day": 1}]}

    def test_extracts_markdown_fenced_json(self):
        text = '```json\n{"destination": "Paris", "days": []}\n```'
        assert _extract_chat_itinerary(_state(text)) == {"destination": "Paris", "days": []}

    def test_rejects_non_itinerary_json(self):
        text = 'Here is some json: {"hello": "world"}'
        assert _extract_chat_itinerary(_state(text)) is None

    def test_returns_none_for_plain_prose(self):
        assert _extract_chat_itinerary(_state("Just chatting about Paris!")) is None

    def test_returns_none_for_empty_state(self):
        assert _extract_chat_itinerary({"messages": []}) is None

    def test_checks_last_message_first(self):
        msgs = [
            _Msg('{"destination": "Rome", "days": []}'),
            _Msg("final thoughts, no plan here"),
        ]
        assert _extract_chat_itinerary({"messages": msgs}) == {"destination": "Rome", "days": []}


class TestLooksLikeItineraryDraft:
    """Regression: the model sometimes writes a full day-by-day itinerary in
    prose without wrapping it in <itinerary>/<comparison> tags. This heuristic
    lets the untagged-response gate still trigger structured extraction and
    the _format_itinerary recovery pass, instead of silently dropping the
    itinerary card."""

    def test_detects_untagged_day_by_day_plan(self):
        text = (
            "Day 1: Explore the Heart of Chandigarh\n\n"
            "Morning:\nActivity: Visit the Rock Garden\nTiming: 9:00 AM - 11:00 AM\n\n"
            "Afternoon:\nActivity: Stroll around Sukhna Lake\nTiming: 12:00 PM - 2:00 PM\n\n"
            "Evening:\nActivity: Shopping at Sector 17\nTiming: 4:00 PM - 7:00 PM\n\n"
            "Day 2: Cultural and Leisure Activities\n\n"
            "Morning:\nActivity: Visit the Rose Garden\nTiming: 9:00 AM - 11:00 AM\n"
        )
        assert _looks_like_itinerary_draft(text) is True

    def test_ignores_plain_conversation(self):
        text = "Do you have any specific accessibility needs or preferences for transportation?"
        assert _looks_like_itinerary_draft(text) is False

    def test_ignores_single_day_mention(self):
        text = "Day 1 sounds great, morning: let's start with breakfast."
        assert _looks_like_itinerary_draft(text) is False

    def test_empty_text(self):
        assert _looks_like_itinerary_draft("") is False
        assert _looks_like_itinerary_draft(None) is False


class TestLooksLikeComparisonDraft:
    """Regression: the model sometimes writes a full 3-tier comparison plan
    (Budget/Balanced/Premium) in prose without wrapping it in <comparison>
    tags. This heuristic lets the untagged-response gate still trigger
    structured extraction and the _format_comparison recovery pass."""

    def test_detects_untagged_comparison_plan(self):
        text = (
            "Here are three itinerary options for your 2-day trip to Chandigarh:\n\n"
            "Budget Plan\n"
            "Accommodation: Budget Hostel\n"
            "Food: Street food\n"
            "Activities: Free attractions\n"
            "Transport: Walking\n"
            "Total Cost: ₹90 per person\n\n"
            "Balanced Plan\n"
            "Accommodation: Mid-range hotel\n"
            "Food: Mix of local restaurants and street food\n"
            "Activities: Includes some paid activities\n"
            "Transport: Public transport\n"
            "Total Cost: ₹270 per person\n\n"
            "Premium Plan\n"
            "Accommodation: Luxury hotel\n"
            "Food: Fine dining\n"
            "Activities: Private tours\n"
            "Transport: Taxi\n"
            "Total Cost: ₹860 per person\n"
        )
        assert _looks_like_comparison_draft(text) is True

    def test_ignores_plain_conversation(self):
        text = "I'd prefer the premium option, what do you think?"
        assert _looks_like_comparison_draft(text) is False

    def test_ignores_single_tier_mention(self):
        text = "The budget plan sounds great. Let me know the total cost."
        assert _looks_like_comparison_draft(text) is False

    def test_empty_text(self):
        assert _looks_like_comparison_draft("") is False
        assert _looks_like_comparison_draft(None) is False


class TestStripUntaggedPlanProse:
    """Tests for stripping untagged plan prose from displayed chat text."""

    def test_strips_untagged_itinerary_prose(self):
        text = (
            "Here's your plan for Chandigarh.\n\n"
            "Day 1: Explore the city\n"
            "Morning: Visit Rock Garden\n"
            "Afternoon: Sukhna Lake\n"
        )
        result = _strip_untagged_plan_prose(text, "itinerary")
        assert "Day 1" not in result
        assert "See the plan below." in result

    def test_strips_untagged_comparison_prose(self):
        text = (
            "Here are three options:\n\n"
            "Budget Plan\nAccommodation: Hostel\nTotal Cost: ₹90\n\n"
            "Balanced Plan\nAccommodation: Hotel\nTotal Cost: ₹270\n"
        )
        result = _strip_untagged_plan_prose(text, "comparison")
        assert "Budget Plan" not in result
        assert "See the plan below." in result

    def test_keeps_text_without_marker(self):
        text = "Just a conversational reply with no plan markers."
        result = _strip_untagged_plan_prose(text, "itinerary")
        assert result == text

    def test_empty_text(self):
        assert _strip_untagged_plan_prose("", "itinerary") == ""
        assert _strip_untagged_plan_prose(None, "comparison") is None
