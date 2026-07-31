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


class TestToolError:
    def test_tool_error_clears_active_task(self):
        active = {"run-7": "risk_detector"}
        event = _ev("on_tool_error", name="task", run_id="run-7", data={"error": "boom"})
        payloads = _parse_chat_event(event, active)
        assert json_data(payloads[0]) == {"tool": "risk_detector", "status": "error"}
        assert active == {}

    def test_untracked_tool_error_emits_nothing(self):
        event = _ev("on_tool_error", name="task", run_id="unknown", data={"error": "boom"})
        assert _parse_chat_event(event, {}) == []


def _fake_state(messages):
    class _Snapshot:
        def __init__(self, values):
            self.values = values

    return _Snapshot({"messages": messages})


class TestStreamChatAgentRetry:
    """stream_chat_agent must retry once when no itinerary is extractable."""

    async def _collect(self, agen):
        return [(e["event"], e.get("data")) async for e in agen]

    def test_retries_when_extraction_fails(self, monkeypatch):
        import asyncio

        import agents.deep_agent as deep_agent_module

        class _Msg:
            def __init__(self, content):
                self.content = content

        class _FakeAgent:
            def __init__(self):
                self.get_state_calls = 0
                self.invoke_calls = 0

            async def astream_events(self, *args, **kwargs):
                yield {"event": "on_chat_model_stream", "data": {"chunk": None}}

            async def aget_state(self, config):
                self.get_state_calls += 1
                if self.get_state_calls == 1:
                    return _fake_state([_Msg("Just some prose, no JSON here.")])
                return _fake_state([_Msg('<itinerary>{"destination": "Paris", "days": []}</itinerary>')])

            async def ainvoke(self, *args, **kwargs):
                self.invoke_calls += 1

        fake = _FakeAgent()
        monkeypatch.setattr(deep_agent_module, "create_chat_agent", lambda **kw: fake)

        events = asyncio.run(
            self._collect(deep_agent_module.stream_chat_agent("hello", "t1", "u1"))
        )

        assert fake.invoke_calls == 1
        assert fake.get_state_calls == 2
        assert events[-2] == ("itinerary", {"destination": "Paris", "days": []})
        assert events[-1] == ("done", None)

    def test_no_retry_when_itinerary_present(self, monkeypatch):
        import asyncio

        import agents.deep_agent as deep_agent_module

        class _Msg:
            def __init__(self, content):
                self.content = content

        class _FakeAgent:
            async def astream_events(self, *args, **kwargs):
                yield {"event": "on_chat_model_stream", "data": {"chunk": None}}

            async def aget_state(self, config):
                return _fake_state([_Msg('{"destination": "Paris", "days": []}')])

            async def ainvoke(self, *args, **kwargs):
                raise AssertionError("should not retry")

        monkeypatch.setattr(deep_agent_module, "create_chat_agent", lambda **kw: _FakeAgent())

        events = asyncio.run(
            self._collect(deep_agent_module.stream_chat_agent("hello", "t1", "u1"))
        )

        assert events[-2] == ("itinerary", {"destination": "Paris", "days": []})
        assert events[-1] == ("done", None)


def json_data(payload: dict):
    import json

    return json.loads(payload["data"])["data"]


class TestChatStreamEndpoint:
    """End-to-end SSE wiring: /chat/stream must deliver the full event sequence."""

    def test_event_sequence(self, monkeypatch):
        import json as _json

        from fastapi.testclient import TestClient

        import main as main_module

        async def fake_stream_chat_agent(message, thread_id, user_id=None):
            yield {"event": "on_chat_model_stream", "data": {"chunk": _Chunk([{"type": "text-delta", "text": "Hi"}])}}
            yield {"event": "on_tool_start", "name": "task", "run_id": "r1", "data": {"input": {"subagent_type": "researcher"}}}
            yield {"event": "on_tool_end", "name": "task", "run_id": "r1", "data": {"output": "ok"}}
            yield {"event": "itinerary", "data": {"destination": "Paris"}}
            yield {"event": "done", "data": None}

        monkeypatch.setattr(main_module, "stream_chat_agent", fake_stream_chat_agent)
        with TestClient(main_module.app) as c, c.stream(
            "POST", "/chat/stream",
            json={"message": "hello"},
            headers={"X-User-Id": "tester"},
        ) as r:
            assert r.status_code == 200
            parsed = []
            for line in r.iter_lines():
                if line.startswith("data: "):
                    parsed.append(_json.loads(line[6:]))

        events = [(p["event"], p["data"]) for p in parsed]
        assert events[0][0] == "thread_id"
        assert events[1] == ("status", {"tool": "agent", "status": "thinking"})
        assert events[2] == ("token", "Hi")
        assert events[3] == ("status", {"tool": "researcher", "status": "running"})
        assert events[4] == ("status", {"tool": "researcher", "status": "done"})
        assert events[5] == ("itinerary", {"destination": "Paris"})
        assert events[6] == ("done", None)

    def test_tool_error_event_sequence(self, monkeypatch):
        import json as _json

        from fastapi.testclient import TestClient

        import main as main_module

        async def fake_stream_chat_agent(message, thread_id, user_id=None):
            yield {"event": "on_tool_start", "name": "task", "run_id": "r9", "data": {"input": {"subagent_type": "risk_detector"}}}
            yield {"event": "on_tool_error", "name": "task", "run_id": "r9", "data": {"error": "boom"}}
            yield {"event": "done", "data": None}

        monkeypatch.setattr(main_module, "stream_chat_agent", fake_stream_chat_agent)
        with TestClient(main_module.app) as c, c.stream(
            "POST", "/chat/stream",
            json={"message": "hello"},
            headers={"X-User-Id": "tester"},
        ) as r:
            parsed = []
            for line in r.iter_lines():
                if line.startswith("data: "):
                    parsed.append(_json.loads(line[6:]))

        statuses = [(p["data"]["tool"], p["data"]["status"]) for p in parsed if p["event"] == "status"]
        assert ("risk_detector", "running") in statuses
        assert ("risk_detector", "error") in statuses
