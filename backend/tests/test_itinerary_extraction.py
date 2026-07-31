"""Tests for chat itinerary extraction — tagged and fallback JSON paths."""

from __future__ import annotations

from agents.deep_agent import _extract_chat_itinerary


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
