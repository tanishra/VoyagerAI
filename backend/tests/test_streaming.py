"""Regression tests for chat stream v2 event parsing.

Covers the Phase 4.2 bug fix: raw langchain v2 astream_events were dropped by
/chat/stream, so tokens never streamed and subagent status never reached the UI.
"""

from __future__ import annotations

from main import _parse_chat_event


class _Chunk:
    def __init__(self, content):
        self.content = content


def _ev(event: str, name: str = "", run_id: str = "", data=None) -> dict:
    return {"event": event, "name": name, "run_id": run_id, "data": data}


class TestTokenStreaming:
    def test_text_delta_emits_token(self):
        event = _ev("on_chat_model_stream", data={"chunk": _Chunk([{"type": "text-delta", "text": "Hello"}])})
        payloads = _parse_chat_event(event, {})
        assert len(payloads) == 1
        assert payloads[0]["event"] == "token"
        assert json_data(payloads[0]) == "Hello"

    def test_empty_text_delta_emits_nothing(self):
        event = _ev("on_chat_model_stream", data={"chunk": _Chunk([{"type": "text-delta", "text": ""}])})
        assert _parse_chat_event(event, {}) == []
    def test_string_content_emits_token(self):
        event = _ev("on_chat_model_stream", data={"chunk": _Chunk("Hello")})
        payloads = _parse_chat_event(event, {})
        assert json_data(payloads[0]) == "Hello"

    def test_tool_use_block_emits_status(self):
        event = _ev("on_chat_model_stream", data={"chunk": _Chunk([{"type": "tool_use", "name": "internet_search"}])})
        payloads = _parse_chat_event(event, {})
        assert json_data(payloads[0]) == {"tool": "internet_search", "status": "running"}

    def test_task_tool_use_block_is_filtered(self):
        event = _ev("on_chat_model_stream", data={"chunk": _Chunk([{"type": "tool_use", "name": "task"}])})
        assert _parse_chat_event(event, {}) == []

    def test_non_text_blocks_ignored(self):
        event = _ev("on_chat_model_stream", data={"chunk": _Chunk([{"type": "image"}])})
        assert _parse_chat_event(event, {}) == []

class TestSubagentStatus:
    def test_task_start_emits_running_status(self):
        event = _ev(
            "on_tool_start",
            name="task",
            run_id="run-1",
            data={"input": {"description": "Research hotels", "subagent_type": "researcher"}},
        )
        active = {}
        payloads = _parse_chat_event(event, active)
        assert json_data(payloads[0]) == {"tool": "researcher", "status": "running"}
        assert active == {"run-1": "researcher"}

    def test_task_end_emits_done_status(self):
        active = {"run-1": "risk_detector"}
        event = _ev("on_tool_end", name="task", run_id="run-1", data={"output": "..."})
        payloads = _parse_chat_event(event, active)
        assert json_data(payloads[0]) == {"tool": "risk_detector", "status": "done"}
        assert active == {}

    def test_untracked_task_end_emits_nothing(self):
        event = _ev("on_tool_end", name="task", run_id="unknown", data={"output": "..."})
        assert _parse_chat_event(event, {}) == []

    def test_non_task_tool_start_emits_nothing(self):
        event = _ev("on_tool_start", name="write_todos", data={"input": {}})
        assert _parse_chat_event(event, {}) == []


class TestRawEventsDropped:
    def test_on_chain_start_dropped(self):
        event = _ev("on_chain_start", name="TravelAgent", data={"input": {}})
        assert _parse_chat_event(event, {}) == []

    def test_on_chain_end_dropped(self):
        event = _ev("on_chain_end", name="TravelAgent", data={"output": {}})
        assert _parse_chat_event(event, {}) == []

    def test_on_chat_model_end_dropped(self):
        event = _ev("on_chat_model_end", data={"output": {"content": "x"}})
        assert _parse_chat_event(event, {}) == []


class TestSyntheticEvents:
    def test_itinerary_passthrough(self):
        event = {"event": "itinerary", "data": {"destination": "Paris"}}
        payloads = _parse_chat_event(event, {})
        assert payloads[0]["event"] == "itinerary"
        assert json_data(payloads[0]) == {"destination": "Paris"}

    def test_done_passthrough(self):
        payloads = _parse_chat_event({"event": "done", "data": None}, {})
        assert payloads[0]["event"] == "done"
        assert json_data(payloads[0]) is None

    def test_error_passthrough(self):
        payloads = _parse_chat_event({"event": "error", "data": "boom"}, {})
        assert payloads[0]["event"] == "error"
        assert json_data(payloads[0]) == "boom"

    def test_malformed_event_returns_empty(self):
        assert _parse_chat_event({}, {}) == []


def json_data(payload: dict):
    import json

    return json.loads(payload["data"])["data"]
