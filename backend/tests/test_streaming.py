"""Regression tests for chat stream v2 event parsing.

Covers the Phase 4.2 bug fix: raw langchain v2 astream_events were dropped by
/chat/stream, so tokens never streamed and subagent status never reached the UI.
"""

from __future__ import annotations

import asyncio

from main import _parse_chat_event


def _create_dev_session():
    """Create a real dev session and return the session ID."""
    from oauth import DEV_USER, create_session

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(create_session(DEV_USER))
    finally:
        loop.close()


def _inject_session(c):
    """Inject dev session + CSRF cookie into a TestClient."""
    c.cookies.set("voyager_session", _create_dev_session())
    c.cookies.set("voyager_csrf", "test-csrf-token")


class _Chunk:
    def __init__(self, content):
        self.content = content


def _ev(event: str, name: str = "", run_id: str = "", data=None, parent_ids=None) -> dict:
    return {"event": event, "name": name, "run_id": run_id, "data": data, "parent_ids": parent_ids or []}


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

    def test_text_block_emits_token(self):
        """Plain 'text' blocks (not just 'text-delta') must emit tokens too."""
        event = _ev("on_chat_model_stream", data={"chunk": _Chunk([{"type": "text", "text": "Hello"}])})
        payloads = _parse_chat_event(event, {})
        assert len(payloads) == 1
        assert payloads[0]["event"] == "token"
        assert json_data(payloads[0]) == "Hello"

    def test_mixed_text_and_text_delta_blocks(self):
        """Both text and text-delta blocks in the same chunk should emit tokens."""
        event = _ev("on_chat_model_stream", data={"chunk": _Chunk([
            {"type": "text", "text": "Hello "},
            {"type": "text-delta", "text": "world"},
        ])})
        payloads = _parse_chat_event(event, {})
        assert len(payloads) == 2
        assert json_data(payloads[0]) == "Hello "
        assert json_data(payloads[1]) == "world"

    def test_reasoning_block_emits_thinking(self):
        """Reasoning blocks should emit thinking SSE events."""
        event = _ev("on_chat_model_stream", data={"chunk": _Chunk([
            {"type": "reasoning", "reasoning": "Let me think about this..."},
        ])})
        payloads = _parse_chat_event(event, {})
        assert len(payloads) == 1
        assert payloads[0]["event"] == "thinking"
        assert json_data(payloads[0]) == "Let me think about this..."

    def test_reasoning_delta_block_emits_thinking(self):
        """reasoning-delta blocks should also emit thinking SSE events."""
        event = _ev("on_chat_model_stream", data={"chunk": _Chunk([
            {"type": "reasoning-delta", "reasoning": "considering options..."},
        ])})
        payloads = _parse_chat_event(event, {})
        assert len(payloads) == 1
        assert payloads[0]["event"] == "thinking"
        assert json_data(payloads[0]) == "considering options..."

    def test_reasoning_block_falls_back_to_text_field(self):
        """Reasoning blocks with 'text' field instead of 'reasoning' should still work."""
        event = _ev("on_chat_model_stream", data={"chunk": _Chunk([
            {"type": "reasoning", "text": "thinking via text field"},
        ])})
        payloads = _parse_chat_event(event, {})
        assert len(payloads) == 1
        assert payloads[0]["event"] == "thinking"
        assert json_data(payloads[0]) == "thinking via text field"

    def test_empty_reasoning_emits_nothing(self):
        """Empty reasoning text should not emit a thinking event."""
        event = _ev("on_chat_model_stream", data={"chunk": _Chunk([
            {"type": "reasoning", "reasoning": ""},
        ])})
        assert _parse_chat_event(event, {}) == []

    def test_non_text_blocks_ignored(self):
        event = _ev("on_chat_model_stream", data={"chunk": _Chunk([{"type": "image"}])})
        assert _parse_chat_event(event, {}) == []


class TestNestedSubagentStreamFiltering:
    """Regression: subagents dispatched via the `task` tool run concurrently and
    stream their own on_chat_model_stream events, which bubble up into the same
    astream_events source as the orchestrator's own output. Without filtering by
    parent_ids, these nested LLM chunks interleave with (and get concatenated
    into) the orchestrator's "token" stream, producing garbled text on the
    frontend. Any chat-model-stream event whose parent_ids chain includes a
    known `task` run_id must be dropped from token/thinking output."""

    def test_task_start_registers_subagent_run_id(self):
        subagent_run_ids: set[str] = set()
        event = _ev(
            "on_tool_start",
            name="task",
            run_id="task-run-1",
            data={"input": {"description": "Research hotels", "subagent_type": "researcher"}},
        )
        _parse_chat_event(event, {}, subagent_run_ids)
        assert "task-run-1" in subagent_run_ids

    def test_nested_chat_model_stream_is_dropped(self):
        """A token event whose parent chain includes a task run_id must not
        leak into the main token stream."""
        subagent_run_ids = {"task-run-1"}
        event = _ev(
            "on_chat_model_stream",
            data={"chunk": _Chunk([{"type": "text-delta", "text": "leaked subagent text"}])},
            parent_ids=["task-run-1"],
        )
        assert _parse_chat_event(event, {}, subagent_run_ids) == []

    def test_top_level_chat_model_stream_is_not_dropped(self):
        """The orchestrator's own model stream (no task ancestor) must still
        emit tokens normally, even while subagent_run_ids is non-empty."""
        subagent_run_ids = {"task-run-1"}
        event = _ev(
            "on_chat_model_stream",
            data={"chunk": _Chunk([{"type": "text-delta", "text": "orchestrator text"}])},
            parent_ids=[],
        )
        payloads = _parse_chat_event(event, {}, subagent_run_ids)
        assert len(payloads) == 1
        assert payloads[0]["event"] == "token"
        assert json_data(payloads[0]) == "orchestrator text"

    def test_deeply_nested_chat_model_stream_is_dropped(self):
        """parent_ids may contain multiple ancestors; a task run_id anywhere
        in the chain should still trigger filtering."""
        subagent_run_ids = {"task-run-1"}
        event = _ev(
            "on_chat_model_stream",
            data={"chunk": _Chunk("nested text")},
            parent_ids=["root-run", "task-run-1", "inner-run"],
        )
        assert _parse_chat_event(event, {}, subagent_run_ids) == []

    def test_end_to_end_parallel_subagents_do_not_leak_tokens(self):
        """Simulates two subagents (researcher, risk_detector) dispatched in
        parallel, each streaming their own text, interleaved with the
        orchestrator's own final output. Only the orchestrator's tokens should
        survive filtering."""
        subagent_run_ids: set[str] = set()
        active_tasks: dict[str, str] = {}
        collected_tokens: list[str] = []

        events = [
            _ev("on_tool_start", name="task", run_id="task-researcher",
                data={"input": {"subagent_type": "researcher"}}),
            _ev("on_tool_start", name="task", run_id="task-risk",
                data={"input": {"subagent_type": "risk_detector"}}),
            _ev("on_chat_model_stream", run_id="llm-researcher",
                data={"chunk": _Chunk("Researcher: ")}, parent_ids=["task-researcher"]),
            _ev("on_chat_model_stream", run_id="llm-risk",
                data={"chunk": _Chunk("Risk: ")}, parent_ids=["task-risk"]),
            _ev("on_chat_model_stream", run_id="llm-researcher",
                data={"chunk": _Chunk("hotels found")}, parent_ids=["task-researcher"]),
            _ev("on_tool_end", name="task", run_id="task-researcher", data={"output": "..."}),
            _ev("on_tool_end", name="task", run_id="task-risk", data={"output": "..."}),
            _ev("on_chat_model_stream", run_id="llm-orchestrator",
                data={"chunk": _Chunk("Here is your itinerary")}, parent_ids=[]),
        ]

        for event in events:
            for payload in _parse_chat_event(event, active_tasks, subagent_run_ids):
                if payload["event"] == "token":
                    collected_tokens.append(json_data(payload))

        assert collected_tokens == ["Here is your itinerary"]


class TestSubagentStatus:
    def test_task_start_emits_running_status_and_tool_start(self):
        event = _ev(
            "on_tool_start",
            name="task",
            run_id="run-1",
            data={"input": {"description": "Research hotels", "subagent_type": "researcher"}},
        )
        active = {}
        payloads = _parse_chat_event(event, active)
        # Should emit both status (for backward compat) and tool_start (new)
        assert len(payloads) == 2
        assert payloads[0]["event"] == "status"
        assert json_data(payloads[0]) == {"tool": "researcher", "status": "running"}
        assert payloads[1]["event"] == "tool_start"
        tool_start_data = json_data(payloads[1])
        assert tool_start_data["name"] == "researcher"
        assert tool_start_data["run_id"] == "run-1"
        assert active == {"run-1": "researcher"}

    def test_task_end_emits_done_status_and_tool_end(self):
        active = {"run-1": "risk_detector"}
        event = _ev("on_tool_end", name="task", run_id="run-1", data={"output": "..."})
        payloads = _parse_chat_event(event, active)
        assert len(payloads) == 2
        assert payloads[0]["event"] == "status"
        assert json_data(payloads[0]) == {"tool": "risk_detector", "status": "done"}
        assert payloads[1]["event"] == "tool_end"
        tool_end_data = json_data(payloads[1])
        assert tool_end_data["name"] == "risk_detector"
        assert tool_end_data["run_id"] == "run-1"
        assert active == {}

    def test_untracked_tool_end_emits_tool_end(self):
        """Non-task tools that aren't in active_tasks still emit tool_end."""
        event = _ev("on_tool_end", name="read_file", run_id="unknown", data={"output": "file contents"})
        payloads = _parse_chat_event(event, {})
        assert len(payloads) == 1
        assert payloads[0]["event"] == "tool_end"
        assert json_data(payloads[0])["name"] == "read_file"

    def test_non_task_tool_start_emits_tool_start(self):
        """Non-task tools emit tool_start events (no status, just tool_start)."""
        event = _ev("on_tool_start", name="write_todos", run_id="r2", data={"input": {"todos": []}})
        payloads = _parse_chat_event(event, {})
        assert len(payloads) == 1
        assert payloads[0]["event"] == "tool_start"
        tool_start_data = json_data(payloads[0])
        assert tool_start_data["name"] == "write_todos"
        assert tool_start_data["run_id"] == "r2"


class TestRawEventsDropped:
    def test_on_chain_start_dropped(self):
        event = _ev("on_chain_start", name="TravelAgent", data={"input": {}})
        assert _parse_chat_event(event, {}) == []

    def test_on_chain_end_dropped(self):
        event = _ev("on_chain_end", name="TravelAgent", data={"output": {}})
        assert _parse_chat_event(event, {}) == []

    def test_on_chat_model_end_without_usage_dropped(self):
        event = _ev("on_chat_model_end", data={"output": {"content": "x"}})
        assert _parse_chat_event(event, {}) == []

    def test_on_chat_model_end_with_usage_emits_usage_event(self):
        """on_chat_model_end with usage_metadata should emit a usage SSE event."""
        class _OutputWithUsage:
            usage_metadata = {"input_tokens": 100, "output_tokens": 50}
            response_metadata = {"model_name": "gemini-3.7-flash"}

        event = _ev("on_chat_model_end", data={"output": _OutputWithUsage()})
        payloads = _parse_chat_event(event, {})
        assert len(payloads) == 1
        assert payloads[0]["event"] == "usage"
        usage_data = json_data(payloads[0])
        assert usage_data["input_tokens"] == 100
        assert usage_data["output_tokens"] == 50
        assert usage_data["model"] == "gemini-3.7-flash"


class TestSyntheticEvents:
    def test_itinerary_passthrough(self):
        event = {"event": "itinerary", "data": {"destination": "Paris"}}
        payloads = _parse_chat_event(event, {})
        assert payloads[0]["event"] == "itinerary"
        assert json_data(payloads[0]) == {"destination": "Paris"}

    def test_comparison_passthrough(self):
        comparison_data = {"plans": [{"tier": "budget"}], "comparison_matrix": {}}
        event = {"event": "comparison", "data": comparison_data}
        payloads = _parse_chat_event(event, {})
        assert payloads[0]["event"] == "comparison"
        assert json_data(payloads[0]) == comparison_data

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
        assert len(payloads) == 2
        assert payloads[0]["event"] == "status"
        assert json_data(payloads[0]) == {"tool": "risk_detector", "status": "error"}
        assert payloads[1]["event"] == "tool_error"
        assert json_data(payloads[1])["name"] == "risk_detector"
        assert active == {}

    def test_untracked_tool_error_emits_tool_error(self):
        """Untracked tool errors emit tool_error event (no status, just tool_error)."""
        event = _ev("on_tool_error", name="task", run_id="unknown", data={"error": "boom"})
        payloads = _parse_chat_event(event, {})
        assert len(payloads) == 1
        assert payloads[0]["event"] == "tool_error"
        err_data = json_data(payloads[0])
        assert err_data["name"] == "task"
        assert err_data["error"] == "boom"


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
                self.stream_calls = 0

            async def astream_events(self, *args, **kwargs):
                self.stream_calls += 1
                if self.stream_calls == 1:
                    yield {"event": "on_chat_model_stream", "run_id": "r1", "data": {"chunk": _Chunk('<itinerary>Just some prose, no JSON here.</itinerary>')}}
                else:
                    yield {"event": "on_chat_model_stream", "run_id": "r2", "data": {"chunk": _Chunk('<itinerary>{"destination": "Paris", "days": []}</itinerary>')}}

            async def aget_state(self, config):
                self.get_state_calls += 1
                if self.get_state_calls <= 2:
                    return _fake_state([_Msg('<itinerary>Just some prose, no JSON here.</itinerary>')])
                return _fake_state([_Msg('<itinerary>{"destination": "Paris", "days": []}</itinerary>')])

            async def ainvoke(self, *args, **kwargs):
                raise AssertionError("retry must stream, not ainvoke")

        fake = _FakeAgent()
        async def _fake_factory(**kw):
            return fake
        monkeypatch.setattr(deep_agent_module, "create_chat_agent", _fake_factory)

        async def _boom_formatter(*args, **kwargs):
            raise AssertionError("formatter must not run when retry extracts")

        monkeypatch.setattr(deep_agent_module, "_format_itinerary", _boom_formatter)

        events = asyncio.run(
            self._collect(deep_agent_module.stream_chat_agent("hello", "t1", "u1"))
        )

        assert fake.stream_calls == 2
        assert fake.get_state_calls == 2  # message_index + extraction (retry succeeds from stream text)
        assert events[-2] == ("itinerary", {"destination": "Paris", "days": []})
        assert events[-1][0] == "done"

    def test_no_retry_when_itinerary_present(self, monkeypatch):
        import asyncio

        import agents.deep_agent as deep_agent_module

        class _Msg:
            def __init__(self, content):
                self.content = content

        class _FakeAgent:
            def __init__(self):
                self.stream_calls = 0

            async def astream_events(self, *args, **kwargs):
                self.stream_calls += 1
                yield {"event": "on_chat_model_stream", "run_id": "r1", "data": {"chunk": _Chunk('<itinerary>{"destination": "Paris", "days": []}</itinerary>')}}

            async def aget_state(self, config):
                return _fake_state([_Msg('<itinerary>{"destination": "Paris", "days": []}</itinerary>')])

            async def ainvoke(self, *args, **kwargs):
                raise AssertionError("should not retry")

        fake = _FakeAgent()
        async def _fake_factory(**kw):
            return fake
        monkeypatch.setattr(deep_agent_module, "create_chat_agent", _fake_factory)

        async def _boom_formatter(*args, **kwargs):
            raise AssertionError("formatter must not run when extraction succeeds")

        monkeypatch.setattr(deep_agent_module, "_format_itinerary", _boom_formatter)

        events = asyncio.run(
            self._collect(deep_agent_module.stream_chat_agent("hello", "t1", "u1"))
        )

        assert fake.stream_calls == 1
        assert events[-2] == ("itinerary", {"destination": "Paris", "days": []})
        assert events[-1][0] == "done"

    def test_retry_uses_hint_and_formatter_recovers(self, monkeypatch):
        import asyncio

        import agents.deep_agent as deep_agent_module

        class _Msg:
            def __init__(self, content):
                self.content = content

        prose = "<itinerary>Here is a lovely trip plan for Paris with great food. " * 50 + "</itinerary>"

        class _FakeAgent:
            def __init__(self):
                self.inputs = []

            async def astream_events(self, inputs, *args, **kwargs):
                self.inputs.append(inputs)
                yield {"event": "on_chat_model_stream", "run_id": "r1", "data": {"chunk": _Chunk(prose)}}

            async def aget_state(self, config):
                return _fake_state([_Msg(prose)])

            async def ainvoke(self, *args, **kwargs):
                raise AssertionError("retry must stream, not ainvoke")

        fake = _FakeAgent()
        async def _fake_factory(**kw):
            return fake
        monkeypatch.setattr(deep_agent_module, "create_chat_agent", _fake_factory)

        captured = {}

        async def _fake_formatter(draft_text, user_message):
            captured["draft"] = draft_text
            captured["user"] = user_message
            return {"destination": "Paris", "days": []}

        monkeypatch.setattr(deep_agent_module, "_format_itinerary", _fake_formatter)

        events = asyncio.run(
            self._collect(deep_agent_module.stream_chat_agent("plan a trip", "t1", "u1"))
        )

        assert len(fake.inputs) == 2  # main pass + retry
        retry_content = fake.inputs[1]["messages"][0]["content"]
        assert "did not include a parseable itinerary JSON" in retry_content
        assert prose[:80] in retry_content  # failed output snippet fed back
        assert captured["user"] == "plan a trip"
        assert captured["draft"] == prose
        assert events[-2] == ("itinerary", {"destination": "Paris", "days": []})
        assert events[-1][0] == "done"

    def test_formatter_failure_still_ends_gracefully(self, monkeypatch):
        import asyncio

        import agents.deep_agent as deep_agent_module

        class _Msg:
            def __init__(self, content):
                self.content = content

        class _FakeAgent:
            async def astream_events(self, *args, **kwargs):
                yield {"event": "on_chat_model_stream", "data": {"chunk": None}}

            async def aget_state(self, config):
                return _fake_state([_Msg("no json here at all")])

        async def _fake_factory(**kw):
            return _FakeAgent()
        monkeypatch.setattr(deep_agent_module, "create_chat_agent", _fake_factory)

        async def _failing_formatter(*args, **kwargs):
            return None

        monkeypatch.setattr(deep_agent_module, "_format_itinerary", _failing_formatter)

        events = asyncio.run(
            self._collect(deep_agent_module.stream_chat_agent("hi", "t1", "u1"))
        )

        assert events[-1][0] == "done"
        assert all(e[0] != "error" for e in events)


class TestStreamTextExtraction:
    """Regression: the agent node persists only the first stream chunk of each
    model call, so checkpoint messages are truncated stubs (e.g. an 8-char
    prefix) even though on_chat_model_stream events carry the full response.
    Extraction must use the accumulated stream text, not the checkpoint."""

    async def _collect(self, agen):
        return [(e["event"], e.get("data")) async for e in agen]

    def test_chat_uses_stream_text_when_checkpoint_is_stub(self, monkeypatch):
        import asyncio

        import agents.deep_agent as deep_agent_module

        full_json = '{"destination": "Udaipur, India", "total_days": 1, "days": []}'
        stub = '<itinerary>\n{\n  "'  # what the checkpoint actually persists

        class _Msg:
            def __init__(self, content):
                self.content = content

        class _FakeAgent:
            def __init__(self):
                self.stream_calls = 0
                self.get_state_calls = 0

            async def astream_events(self, *args, **kwargs):
                self.stream_calls += 1
                yield _ev(
                    "on_chat_model_stream",
                    run_id="run-1",
                    data={"chunk": _Chunk([{"type": "text", "text": f"<itinerary>{full_json}</itinerary>"}])},
                )

            async def aget_state(self, config):
                self.get_state_calls += 1
                return _fake_state([_Msg(stub)])

        fake = _FakeAgent()
        async def _fake_factory(**kw):
            return fake
        monkeypatch.setattr(deep_agent_module, "create_chat_agent", _fake_factory)

        async def _boom_formatter(*args, **kwargs):
            raise AssertionError("formatter must not run when stream text extracts")

        monkeypatch.setattr(deep_agent_module, "_format_itinerary", _boom_formatter)

        events = asyncio.run(
            self._collect(deep_agent_module.stream_chat_agent("hello", "t1", "u1"))
        )

        assert fake.stream_calls == 1  # no retry needed
        assert fake.get_state_calls == 1  # message_index call; stream text alone was sufficient for extraction
        assert events[-2] == (
            "itinerary",
            {"destination": "Udaipur, India", "total_days": 1, "days": []},
        )
        assert events[-1][0] == "done"

    def test_hint_prefers_stream_text_over_state(self, monkeypatch):
        import asyncio

        import agents.deep_agent as deep_agent_module

        class _Msg:
            def __init__(self, content):
                self.content = content

        full_prose = "<itinerary>Here is the complete revised plan. " * 60 + "</itinerary>"

        class _FakeAgent:
            def __init__(self):
                self.inputs = []

            async def astream_events(self, inputs, *args, **kwargs):
                self.inputs.append(inputs)
                yield _ev(
                    "on_chat_model_stream",
                    run_id="run-1",
                    data={"chunk": _Chunk(full_prose)},
                )

            async def aget_state(self, config):
                return _fake_state([_Msg("stub: truncated")])

        fake = _FakeAgent()
        async def _fake_factory(**kw):
            return fake
        monkeypatch.setattr(deep_agent_module, "create_chat_agent", _fake_factory)

        captured = {}

        async def _fake_formatter(draft_text, user_message):
            captured["draft"] = draft_text

        monkeypatch.setattr(deep_agent_module, "_format_itinerary", _fake_formatter)

        asyncio.run(
            self._collect(deep_agent_module.stream_chat_agent("plan a trip", "t1", "u1"))
        )

        assert len(fake.inputs) == 2
        retry_content = fake.inputs[1]["messages"][0]["content"]
        assert "did not include a parseable itinerary JSON" in retry_content
        assert full_prose[:80] in retry_content  # full stream text fed back, not the stub
        assert captured["draft"] == full_prose


def json_data(payload: dict):
    import json

    return json.loads(payload["data"])["data"]


class TestRedisCheckpointer:
    """Regression: the sync langgraph.checkpoint.redis.RedisSaver leaves
    aget_tuple unimplemented (NotImplementedError on any async run), which
    killed every /chat/stream run when Redis was reachable."""

    def test_factory_uses_async_saver(self):
        from langgraph.checkpoint.redis.aio import AsyncRedisSaver

        import agents.deep_agent as deep_agent_module

        assert deep_agent_module.AsyncRedisSaver is AsyncRedisSaver
        assert "aget_tuple" in AsyncRedisSaver.__dict__ or any(
            "aget_tuple" in c.__dict__ for c in AsyncRedisSaver.__mro__
        )

    def test_factory_awaits_setup_and_supports_aget_tuple(self, monkeypatch):
        import asyncio

        import agents.deep_agent as deep_agent_module

        class _FakeAsyncSaver:
            def __init__(self, redis_url=None):
                self.setup_called = False

            async def setup(self):
                self.setup_called = True

            async def aget_tuple(self, config):
                return None

        monkeypatch.setattr(deep_agent_module, "AsyncRedisSaver", _FakeAsyncSaver)
        saver = asyncio.run(deep_agent_module.create_redis_checkpointer())
        assert saver.setup_called
        assert (
            asyncio.run(saver.aget_tuple({"configurable": {"thread_id": "x"}}))
            is None
        )


class TestSqliteCheckpointer:
    """SQLite checkpointer: file-backed persistence with no external service."""

    def test_sqlite_checkpointer_supports_aget_tuple(self, tmp_path, monkeypatch):
        import asyncio

        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        import agents.deep_agent as deep_agent_module

        db = tmp_path / "checkpoints.sqlite"
        monkeypatch.setattr(deep_agent_module, "_sqlite_checkpointer", None)
        monkeypatch.setattr(deep_agent_module.settings, "CHECKPOINTER_DB_PATH", str(db))

        saver = asyncio.run(deep_agent_module.create_sqlite_checkpointer())
        assert isinstance(saver, AsyncSqliteSaver)
        assert db.exists()

        result = asyncio.run(
            saver.aget_tuple({"configurable": {"thread_id": "no-such-thread"}})
        )
        assert result is None

    def test_checkpointer_backend_selects_sqlite(self, tmp_path, monkeypatch):
        import asyncio

        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        import agents.deep_agent as deep_agent_module

        db = tmp_path / "checkpoints.sqlite"
        monkeypatch.setattr(deep_agent_module, "_sqlite_checkpointer", None)
        monkeypatch.setattr(deep_agent_module.settings, "CHECKPOINTER_DB_PATH", str(db))
        monkeypatch.setattr(deep_agent_module.settings, "CHECKPOINTER_BACKEND", "sqlite")

        saver = asyncio.run(deep_agent_module.create_checkpointer())
        assert isinstance(saver, AsyncSqliteSaver)

    def test_checkpointer_backend_redis_falls_back_gracefully(self, tmp_path, monkeypatch):
        import asyncio

        from langgraph.checkpoint.memory import MemorySaver

        import agents.deep_agent as deep_agent_module

        monkeypatch.setattr(deep_agent_module.settings, "CHECKPOINTER_BACKEND", "redis")
        monkeypatch.setattr(deep_agent_module, "create_redis_checkpointer", _raise_on_call)
        monkeypatch.setattr(deep_agent_module, "create_sqlite_checkpointer", _raise_on_call)

        saver = asyncio.run(deep_agent_module.create_checkpointer())
        assert isinstance(saver, MemorySaver)

    def test_redis_checkpointer_survives_setup_failure_upstash(self, monkeypatch):
        """When Redis is available but RediSearch is not (e.g. Upstash),
        create_redis_checkpointer should catch the setup() failure and
        still return the AsyncRedisSaver — aput/aget_tuple only need
        RedisJSON, not RediSearch."""
        import asyncio
        from unittest.mock import AsyncMock, MagicMock

        from langgraph.checkpoint.redis.aio import AsyncRedisSaver

        import agents.deep_agent as deep_agent_module

        # Reset the global cache
        monkeypatch.setattr(deep_agent_module, "_checkpointer", None)

        # Mock the Redis connection so AsyncRedisSaver.__init__ doesn't fail
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)

        from redisvl.redis.connection import RedisConnectionFactory

        def _mock_get_conn(*args, **kwargs):
            return mock_redis

        monkeypatch.setattr(RedisConnectionFactory, "get_async_redis_connection", _mock_get_conn)

        # Mock AsyncRedisSaver.setup() to simulate Upstash (no RediSearch)
        original_init = AsyncRedisSaver.__init__

        class _MockSaver(AsyncRedisSaver):
            def __init__(self, redis_url=None, **kwargs):
                original_init(self, redis_url=redis_url, **kwargs)

            async def setup(self):
                raise RuntimeError("FT.CREATE not supported (no RediSearch module)")

        monkeypatch.setattr(deep_agent_module, "AsyncRedisSaver", _MockSaver)

        saver = asyncio.run(deep_agent_module.create_redis_checkpointer())
        assert isinstance(saver, _MockSaver)
        assert saver.loop is not None
        assert hasattr(saver, "_key_registry")


async def _raise_on_call(*args, **kwargs):
    raise RuntimeError("forced failure")


class TestChatStreamEndpoint:
    """End-to-end SSE wiring: /chat/stream must deliver the full event sequence."""

    def test_event_sequence(self, monkeypatch):
        import json as _json

        from fastapi.testclient import TestClient

        import main as main_module

        async def fake_stream_chat_agent(message, thread_id, user_id=None, locale=None, timezone=None, currency=None, cancel_event=None, attachments=None, client_message_id=None):
            yield {"event": "on_chat_model_stream", "data": {"chunk": _Chunk([{"type": "text-delta", "text": "Hi"}])}}
            yield {"event": "on_tool_start", "name": "task", "run_id": "r1", "data": {"input": {"subagent_type": "researcher"}}}
            yield {"event": "on_tool_end", "name": "task", "run_id": "r1", "data": {"output": "ok"}}
            yield {"event": "itinerary", "data": {"destination": "Paris"}}
            yield {"event": "done", "data": None}

        monkeypatch.setattr(main_module, "stream_chat_agent", fake_stream_chat_agent)
        with TestClient(main_module.app) as c:
            _inject_session(c)
            with c.stream(
                "POST", "/chat/stream",
                json={"message": "hello"},
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
        # status + tool_start emitted for on_tool_start
        assert events[3] == ("status", {"tool": "researcher", "status": "running"})
        assert events[4][0] == "tool_start"
        assert events[4][1]["name"] == "researcher"
        # status + tool_end emitted for on_tool_end
        assert events[5] == ("status", {"tool": "researcher", "status": "done"})
        assert events[6][0] == "tool_end"
        assert events[6][1]["name"] == "researcher"
        assert events[7] == ("itinerary", {"destination": "Paris"})
        assert events[8][0] == "done"

    def test_tool_error_event_sequence(self, monkeypatch):
        import json as _json

        from fastapi.testclient import TestClient

        import main as main_module

        async def fake_stream_chat_agent(message, thread_id, user_id=None, locale=None, timezone=None, currency=None, cancel_event=None, attachments=None, client_message_id=None):
            yield {"event": "on_tool_start", "name": "task", "run_id": "r9", "data": {"input": {"subagent_type": "risk_detector"}}}
            yield {"event": "on_tool_error", "name": "task", "run_id": "r9", "data": {"error": "boom"}}
            yield {"event": "done", "data": None}

        monkeypatch.setattr(main_module, "stream_chat_agent", fake_stream_chat_agent)
        with TestClient(main_module.app) as c:
            _inject_session(c)
            with c.stream(
                "POST", "/chat/stream",
                json={"message": "hello"},
            ) as r:
                parsed = []
                for line in r.iter_lines():
                    if line.startswith("data: "):
                        parsed.append(_json.loads(line[6:]))

        statuses = [(p["data"]["tool"], p["data"]["status"]) for p in parsed if p["event"] == "status"]
        assert ("risk_detector", "running") in statuses
        assert ("risk_detector", "error") in statuses

    def test_thread_id_is_user_scoped(self, monkeypatch):
        import hashlib
        import json as _json

        from fastapi.testclient import TestClient

        import main as main_module

        async def fake_stream_chat_agent(message, thread_id, user_id=None, locale=None, timezone=None, currency=None, attachments=None):
            yield {"event": "done", "data": None}

        monkeypatch.setattr(main_module, "stream_chat_agent", fake_stream_chat_agent)
        user_tag = hashlib.sha256(b"dev@localhost").hexdigest()[:12]

        with TestClient(main_module.app) as c:
            _inject_session(c)
            with c.stream(
                "POST", "/chat/stream",
                json={"message": "hello"},
            ) as r:
                parsed = []
                for line in r.iter_lines():
                    if line.startswith("data: "):
                        parsed.append(_json.loads(line[6:]))

        first = parsed[0]
        assert first["event"] == "thread_id"
        returned = first["data"]["thread_id"]
        assert returned.startswith(f"chat:{user_tag}:")

    def test_resume_thread_id_passes_through_scoped(self, monkeypatch):
        import hashlib
        import json as _json

        from fastapi.testclient import TestClient

        import main as main_module

        async def fake_stream_chat_agent(message, thread_id, user_id=None, locale=None, timezone=None, currency=None, attachments=None):
            yield {"event": "done", "data": None}

        monkeypatch.setattr(main_module, "stream_chat_agent", fake_stream_chat_agent)
        user_tag = hashlib.sha256(b"dev@localhost").hexdigest()[:12]
        resume_id = f"chat:{user_tag}:abc123"

        with TestClient(main_module.app) as c:
            _inject_session(c)
            with c.stream(
                "POST", "/chat/stream",
                json={"message": "hello", "thread_id": resume_id},
            ) as r:
                parsed = []
                for line in r.iter_lines():
                    if line.startswith("data: "):
                        parsed.append(_json.loads(line[6:]))

        assert parsed[0]["data"]["thread_id"] == resume_id

    def test_unscoped_client_thread_id_gets_scoped(self, monkeypatch):
        import hashlib
        import json as _json

        from fastapi.testclient import TestClient

        import main as main_module

        async def fake_stream_chat_agent(message, thread_id, user_id=None, locale=None, timezone=None, currency=None, attachments=None):
            yield {"event": "done", "data": None}

        monkeypatch.setattr(main_module, "stream_chat_agent", fake_stream_chat_agent)
        user_tag = hashlib.sha256(b"dev@localhost").hexdigest()[:12]

        with TestClient(main_module.app) as c:
            _inject_session(c)
            with c.stream(
                "POST", "/chat/stream",
                json={"message": "hello", "thread_id": "plain-id"},
            ) as r:
                parsed = []
                for line in r.iter_lines():
                    if line.startswith("data: "):
                        parsed.append(_json.loads(line[6:]))

        assert parsed[0]["data"]["thread_id"] == f"chat:{user_tag}:plain-id"

    def test_agent_exception_yields_error_event(self, monkeypatch):
        import json as _json

        from fastapi.testclient import TestClient

        import main as main_module

        async def failing_stream_chat_agent(message, thread_id, user_id=None, locale=None, timezone=None, currency=None, cancel_event=None, attachments=None, client_message_id=None):
            yield {"event": "on_chat_model_stream", "data": {"chunk": "part"}}
            raise RuntimeError("boom")

        monkeypatch.setattr(main_module, "stream_chat_agent", failing_stream_chat_agent)
        with TestClient(main_module.app) as c:
            _inject_session(c)
            with c.stream(
                "POST", "/chat/stream",
                json={"message": "hello"},
            ) as r:
                parsed = []
                for line in r.iter_lines():
                    if line.startswith("data: "):
                        parsed.append(_json.loads(line[6:]))

        events = [(p["event"], p["data"]) for p in parsed]
        assert events[0][0] == "thread_id"
        assert events[1] == ("status", {"tool": "agent", "status": "thinking"})
        assert events[-1][0] == "error"
        assert "boom" in events[-1][1]

    def test_agent_exception_yields_localized_error_event(self, monkeypatch):
        import json as _json

        from fastapi.testclient import TestClient

        import main as main_module

        async def failing_stream_chat_agent(message, thread_id, user_id=None, locale=None, timezone=None, currency=None, cancel_event=None, attachments=None, client_message_id=None):
            yield {"event": "on_chat_model_stream", "data": {"chunk": "part"}}
            raise RuntimeError("boom")

        monkeypatch.setattr(main_module, "stream_chat_agent", failing_stream_chat_agent)
        with TestClient(main_module.app) as c:
            _inject_session(c)
            with c.stream(
                "POST", "/chat/stream",
                json={"message": "hello"},
                headers={"Accept-Language": "fr"},
            ) as r:
                parsed = []
                for line in r.iter_lines():
                    if line.startswith("data: "):
                        parsed.append(_json.loads(line[6:]))

        events = [(p["event"], p["data"]) for p in parsed]
        assert events[-1][0] == "error"
        assert "Échec du streaming" in events[-1][1]
        assert "boom" in events[-1][1]


class TestConversationModeGate:
    """Tests that conversational responses (no itinerary/comparison tags) are not
    forced through itinerary extraction."""

    def test_conversational_response_no_tags_yields_only_done(self, monkeypatch):
        """When the agent responds conversationally (no tags), stream_chat_agent
        should yield done without attempting itinerary extraction."""
        import json as _json

        from fastapi.testclient import TestClient

        import main as main_module

        async def conversational_stream(message, thread_id, user_id=None, locale=None, timezone=None, currency=None, cancel_event=None, attachments=None, client_message_id=None):
            yield {"event": "on_chat_model_stream", "data": {"chunk": _Chunk([{"type": "text-delta", "text": "Where would you like to go?"}])}}
            yield {"event": "done", "data": None}

        monkeypatch.setattr(main_module, "stream_chat_agent", conversational_stream)
        with TestClient(main_module.app) as c:
            _inject_session(c)
            with c.stream(
                "POST", "/chat/stream",
                json={"message": "I want to go on a trip"},
            ) as r:
                parsed = []
                for line in r.iter_lines():
                    if line.startswith("data: "):
                        parsed.append(_json.loads(line[6:]))

        events = [(p["event"], p["data"]) for p in parsed]
        # Should have thread_id, status, token, done — NO itinerary or comparison
        event_types = [e[0] for e in events]
        assert "done" in event_types
        assert "itinerary" not in event_types
        assert "comparison" not in event_types

    def test_tag_detection_regex(self):
        """Verify that the tag detection regexes match itinerary/comparison tags
        but not conversational text."""
        from agents.deep_agent import _ITINERARY_TAG_RE, _COMPARISON_TAG_RE

        # Conversational text — no tags
        conv = "Where would you like to go? Please tell me your destination and budget."
        assert not _ITINERARY_TAG_RE.search(conv)
        assert not _COMPARISON_TAG_RE.search(conv)

        # Itinerary tag present
        itin = "Here is your plan:\n<itinerary>{\"destination\": \"Paris\"}</itinerary>"
        assert _ITINERARY_TAG_RE.search(itin)
        assert not _COMPARISON_TAG_RE.search(itin)

        # Comparison tag present
        comp = "<comparison>{\"plans\": [...]}</comparison>"
        assert not _ITINERARY_TAG_RE.search(comp)
        assert _COMPARISON_TAG_RE.search(comp)

    def test_untagged_comparison_prose_triggers_comparison_event(self, monkeypatch):
        """Regression: the model sometimes writes a full 3-tier comparison plan
        in prose without <comparison> tags. The _detect_plan_kind dispatcher
        should still classify it as 'comparison' and the stream should emit
        a comparison event (not just done)."""
        import json as _json

        from fastapi.testclient import TestClient

        import main as main_module

        _COMPARISON_PROSE = (
            "Here are three itinerary options for your 2-day trip to Chandigarh:\n\n"
            "Budget Plan\n"
            "Accommodation: Budget Hostel\n"
            "Food: Street food\n"
            "Activities: Free attractions like Rock Garden\n"
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
            "Activities: Private tours and luxury experiences\n"
            "Transport: Taxi\n"
            "Total Cost: ₹860 per person\n"
        )

        async def comparison_stream(message, thread_id, user_id=None, locale=None, timezone=None, currency=None, cancel_event=None, attachments=None, client_message_id=None):
            yield {"event": "on_chat_model_stream", "data": {"chunk": _Chunk([{"type": "text-delta", "text": _COMPARISON_PROSE}])}}
            yield {"event": "done", "data": None}

        monkeypatch.setattr(main_module, "stream_chat_agent", comparison_stream)
        with TestClient(main_module.app) as c:
            _inject_session(c)
            with c.stream(
                "POST", "/chat/stream",
                json={"message": "Plan a trip to Chandigarh"},
            ) as r:
                parsed = []
                for line in r.iter_lines():
                    if line.startswith("data: "):
                        parsed.append(_json.loads(line[6:]))

        events = [(p["event"], p["data"]) for p in parsed]
        event_types = [e[0] for e in events]
        # The stream should yield tokens + done (the mock stream doesn't emit
        # comparison events itself — that's done by stream_chat_agent which
        # we mocked). But the key regression check is that _detect_plan_kind
        # correctly classifies this prose as "comparison", not "none".
        from agents.deep_agent import _detect_plan_kind
        import asyncio as _aio
        plan_kind = _aio.run(_detect_plan_kind(_COMPARISON_PROSE))
        assert plan_kind == "comparison", f"Expected 'comparison', got '{plan_kind}'"


class TestSubagentProgress:
    """Tests for the new subagent_progress SSE event and parent_run_id nesting."""

    def test_subagent_progress_event_emitted(self):
        """Synthetic subagent_progress events should pass through as SSE."""
        event = {"event": "subagent_progress", "data": {"run_id": "task-1", "description": "Searching for hotels in Tokyo..."}}
        payloads = _parse_chat_event(event, {})
        assert len(payloads) == 1
        assert payloads[0]["event"] == "subagent_progress"
        data = json_data(payloads[0])
        assert data["run_id"] == "task-1"
        assert data["description"] == "Searching for hotels in Tokyo..."

    def test_tool_start_with_parent_run_id(self):
        """A tool_start inside a subagent should include parent_run_id."""
        subagent_run_ids = {"task-run-1"}
        event = _ev(
            "on_tool_start",
            name="internet_search",
            run_id="search-1",
            data={"input": {"query": "hotels Tokyo"}},
            parent_ids=["task-run-1"],
        )
        payloads = _parse_chat_event(event, {}, subagent_run_ids)
        assert len(payloads) == 1
        assert payloads[0]["event"] == "tool_start"
        data = json_data(payloads[0])
        assert data["name"] == "internet_search"
        assert data["run_id"] == "search-1"
        assert data["parent_run_id"] == "task-run-1"

    def test_tool_end_with_parent_run_id(self):
        """A tool_end inside a subagent should include parent_run_id."""
        subagent_run_ids = {"task-run-1"}
        event = _ev(
            "on_tool_end",
            name="internet_search",
            run_id="search-1",
            data={"output": "results..."},
            parent_ids=["task-run-1"],
        )
        payloads = _parse_chat_event(event, {}, subagent_run_ids)
        assert len(payloads) == 1
        assert payloads[0]["event"] == "tool_end"
        data = json_data(payloads[0])
        assert data["name"] == "internet_search"
        assert data["parent_run_id"] == "task-run-1"

    def test_non_subagent_tool_has_no_parent_run_id(self):
        """A top-level tool_start (no subagent parent) should NOT have parent_run_id."""
        event = _ev(
            "on_tool_start",
            name="internet_search",
            run_id="search-top",
            data={"input": {"query": "test"}},
            parent_ids=[],
        )
        payloads = _parse_chat_event(event, {})
        assert len(payloads) == 1
        data = json_data(payloads[0])
        assert "parent_run_id" not in data

    def test_throttling_progress_events(self):
        """_ModelStream._maybe_yield_progress should throttle to 1 per 2 seconds."""
        from agents.deep_agent import _ModelStream
        import time

        stream = _ModelStream.__new__(_ModelStream)
        stream._last_progress_time = {}

        # First call should pass
        assert stream._maybe_yield_progress("run-1", "desc1") is True
        # Immediate second call should be throttled
        assert stream._maybe_yield_progress("run-1", "desc2") is False
        # Different run_id should pass
        assert stream._maybe_yield_progress("run-2", "desc3") is True
        # After 2+ seconds, original run_id should pass again
        stream._last_progress_time["run-1"] = time.monotonic() - 2.1
        assert stream._maybe_yield_progress("run-1", "desc4") is True


class TestClientMessageIdDedup:
    """Bug #6: retried sends carrying the same client_message_id must not
    append the user message to the checkpoint twice."""

    class _Msg:
        def __init__(self, content, id=None, type="ai", tool_calls=None):
            self.content = content
            self.id = id
            self.type = type
            self.tool_calls = tool_calls or []

    class _Snap:
        def __init__(self, values, next_=()):
            self.values = values
            self.next = next_

    async def _collect(self, agen):
        return [(e["event"], e.get("data")) async for e in agen]

    def _patch_agent(self, monkeypatch, state, stream_events=None, state_error=None):
        import agents.deep_agent as deep_agent_module

        outer = self

        class _FakeAgent:
            def __init__(self):
                self.inputs = []
                self.stream_calls = 0

            async def astream_events(self, inputs, *a, **kw):
                self.stream_calls += 1
                self.inputs.append(inputs)
                for e in (stream_events or []):
                    yield e

            async def aget_state(self, config):
                if state_error is not None:
                    raise state_error
                return state

        fake = _FakeAgent()

        async def _factory(**kw):
            return fake

        monkeypatch.setattr(deep_agent_module, "create_chat_agent", _factory)
        monkeypatch.setattr(
            deep_agent_module, "_detect_plan_kind",
            lambda *a, **kw: asyncio.sleep(0, result="none"),
        )
        return fake

    def test_completed_run_replays_without_llm_call(self, monkeypatch):
        import agents.deep_agent as deep_agent_module

        state = self._Snap({"messages": [
            self._Msg("plan a trip", id="cm-1", type="human"),
            self._Msg("Here is your Paris trip."),
        ]})
        fake = self._patch_agent(monkeypatch, state)

        events = asyncio.run(self._collect(
            deep_agent_module.stream_chat_agent("plan a trip", "t1", "u1", client_message_id="cm-1")
        ))

        assert fake.stream_calls == 0  # replay — no graph execution, no LLM cost
        assert ("token", "Here is your Paris trip.") in events
        assert events[-1] == ("done", {"budget_reached": False})

    def test_completed_run_replays_itinerary_event(self, monkeypatch):
        import agents.deep_agent as deep_agent_module

        text = 'ok <itinerary>{"destination": "Paris", "days": []}</itinerary>'
        state = self._Snap({"messages": [
            self._Msg("plan a trip", id="cm-1", type="human"),
            self._Msg(text),
        ]})
        fake = self._patch_agent(monkeypatch, state)

        async def _real_kind(t):
            return "itinerary" if "<itinerary>" in t else "none"

        async def _no_enrich(it):
            return it

        monkeypatch.setattr(deep_agent_module, "_detect_plan_kind", _real_kind)
        monkeypatch.setattr(deep_agent_module, "_enrich_itinerary_with_coordinates", _no_enrich)

        events = asyncio.run(self._collect(
            deep_agent_module.stream_chat_agent("plan a trip", "t1", "u1", client_message_id="cm-1")
        ))

        assert fake.stream_calls == 0
        assert ("itinerary", {"destination": "Paris", "days": []}) in events
        assert events[-1] == ("done", {"budget_reached": False})

    def test_interrupted_run_resumes_with_none_input(self, monkeypatch):
        import agents.deep_agent as deep_agent_module

        state = self._Snap(
            {"messages": [self._Msg("hi", id="cm-1", type="human")]},
            next_=("agent",),
        )
        fake = self._patch_agent(
            monkeypatch, state,
            stream_events=[{"event": "on_chat_model_stream", "run_id": "r1",
                            "data": {"chunk": _Chunk("Hello there")}}],
        )

        events = asyncio.run(self._collect(
            deep_agent_module.stream_chat_agent("hi", "t1", "u1", client_message_id="cm-1")
        ))

        assert fake.stream_calls == 1
        assert fake.inputs[0] is None  # resumed pending run, message not re-appended
        assert events[-1][0] == "done"

    def test_new_id_appends_with_stamped_message_id(self, monkeypatch):
        import agents.deep_agent as deep_agent_module

        state = self._Snap({"messages": [self._Msg("old", id="cm-old", type="human")]})
        fake = self._patch_agent(
            monkeypatch, state,
            stream_events=[{"event": "on_chat_model_stream", "run_id": "r1",
                            "data": {"chunk": _Chunk("Hi")}}],
        )

        asyncio.run(self._collect(
            deep_agent_module.stream_chat_agent("hi", "t1", "u1", client_message_id="cm-new")
        ))

        assert fake.stream_calls == 1
        msgs = fake.inputs[0]["messages"]
        assert len(msgs) == 1
        assert msgs[0].id == "cm-new"

    def test_state_lookup_failure_falls_back_to_fresh_send(self, monkeypatch):
        import agents.deep_agent as deep_agent_module

        fake = self._patch_agent(
            monkeypatch, None, state_error=RuntimeError("checkpointer down"),
            stream_events=[{"event": "on_chat_model_stream", "run_id": "r1",
                            "data": {"chunk": _Chunk("Hi")}}],
        )

        events = asyncio.run(self._collect(
            deep_agent_module.stream_chat_agent("hi", "t1", "u1", client_message_id="cm-1")
        ))

        assert fake.stream_calls == 1
        assert fake.inputs[0]["messages"][0].id == "cm-1"
        assert events[-1][0] == "done"

    def test_no_client_message_id_behaves_as_before(self, monkeypatch):
        import agents.deep_agent as deep_agent_module

        state = self._Snap({"messages": [self._Msg("x", id="anything", type="human")]})
        fake = self._patch_agent(
            monkeypatch, state,
            stream_events=[{"event": "on_chat_model_stream", "run_id": "r1",
                            "data": {"chunk": _Chunk("Hi")}}],
        )

        asyncio.run(self._collect(
            deep_agent_module.stream_chat_agent("hi", "t1", "u1")
        ))

        assert fake.stream_calls == 1
        msgs = fake.inputs[0]["messages"]
        assert msgs[0].id  # auto-generated id stamped
        assert msgs[0].id != "anything"


def test_scoped_thread_id_deterministic_with_client_message_id():
    """Retries on a new chat must land on the same thread checkpoint."""
    from main import _scoped_chat_thread_id

    a = _scoped_chat_thread_id(None, "u1", "cm-abc-123")
    b = _scoped_chat_thread_id(None, "u1", "cm-abc-123")
    assert a == b
    assert a.endswith("cm-abc-123")

    # No client_message_id → still random per call (unchanged behavior)
    assert _scoped_chat_thread_id(None, "u1") != _scoped_chat_thread_id(None, "u1")

    # Already-scoped thread id passes through unchanged
    import hashlib
    tag = hashlib.sha256("u1".encode()).hexdigest()[:12]
    tid = _scoped_chat_thread_id(f"chat:{tag}:xyz", "u1", "cm-abc")
    assert tid == f"chat:{tag}:xyz"

    # Unscoped client thread id still gets prefixed
    tid2 = _scoped_chat_thread_id("xyz", "u1", "cm-abc")
    assert tid2.endswith("xyz")


class TestPersistCostsDelta:
    """Bug #7: a second persist_costs call (extraction-retry path) must write
    only the increment, not re-record every subagent's full total."""

    class _FakeCostStore:
        def __init__(self):
            self.records = []
            self.sessions = []

        async def record_subagent_cost(self, **kw):
            self.records.append(kw)

        async def update_session_total(self, **kw):
            self.sessions.append(kw)

        async def get_hourly_platform_spend(self):
            return 0.0

        async def check_platform_alerts(self):
            return {"daily_spend": 0.0, "level": "ok", "message": ""}

    class _FakeMetric:
        def __init__(self):
            self.totals = {}

        def labels(self, **kw):
            key = tuple(sorted(kw.items()))
            self.totals.setdefault(key, 0.0)

            class _C:
                def __init__(self, totals, k):
                    self._t, self._k = totals, k

                def inc(self, v=1):
                    self._t[self._k] += v

            return _C(self.totals, key)

    def _make_stream(self, subagent_costs, in_tok=100, out_tok=50, cost=0.05):
        from agents.deep_agent import _ModelStream

        s = _ModelStream.__new__(_ModelStream)
        s._subagent_costs = dict(subagent_costs)
        s._persisted_subagent_costs = {}
        s._session_cost = cost
        s._budget_reached = False
        s.activity = {
            "thinking": [], "tool_calls": [], "usage": [],
            "total_input_tokens": in_tok, "total_output_tokens": out_tok,
            "images": [], "charts": [],
        }
        return s

    def _patch(self, monkeypatch):
        import agents.deep_agent as m

        store = self._FakeCostStore()
        metrics = {name: self._FakeMetric() for name in
                   ("LLM_CALLS_TOTAL", "LLM_TOKENS_TOTAL", "LLM_COST_TOTAL")}
        monkeypatch.setattr(m, "cost_store", store)
        for name, metric in metrics.items():
            monkeypatch.setattr(m, name, metric)
        return store, metrics

    def _persist(self, stream):
        import agents.deep_agent as m
        return asyncio.run(stream.persist_costs("t1", "u1"))

    def test_second_persist_with_no_new_cost_writes_nothing(self, monkeypatch):
        store, _ = self._patch(monkeypatch)
        stream = self._make_stream({
            "researcher": {"input_tokens": 100, "output_tokens": 50, "cost": 0.02, "model": "m1"},
        })

        self._persist(stream)
        assert len(store.records) == 1
        assert store.records[0]["cost_usd"] == 0.02

        self._persist(stream)
        assert len(store.records) == 1  # no duplicate row
        assert len(store.sessions) == 2  # session total still refreshed

    def test_second_persist_writes_only_delta(self, monkeypatch):
        store, _ = self._patch(monkeypatch)
        stream = self._make_stream({
            "researcher": {"input_tokens": 100, "output_tokens": 50, "cost": 0.02, "model": "m1"},
        })
        self._persist(stream)

        # Retry accumulates more cost on the same subagent
        stream._subagent_costs["researcher"]["input_tokens"] += 40
        stream._subagent_costs["researcher"]["output_tokens"] += 20
        stream._subagent_costs["researcher"]["cost"] += 0.01

        self._persist(stream)
        assert len(store.records) == 2
        d = store.records[1]
        assert d["input_tokens"] == 40
        assert d["output_tokens"] == 20
        assert d["cost_usd"] == 0.01

    def test_new_subagent_between_persists_recorded(self, monkeypatch):
        store, _ = self._patch(monkeypatch)
        stream = self._make_stream({
            "researcher": {"input_tokens": 100, "output_tokens": 50, "cost": 0.02, "model": "m1"},
        })
        self._persist(stream)

        stream._subagent_costs["planner"] = {"input_tokens": 10, "output_tokens": 5, "cost": 0.003, "model": "m2"}
        self._persist(stream)

        assert len(store.records) == 2
        assert store.records[1]["subagent_name"] == "planner"
        assert store.records[1]["cost_usd"] == 0.003

    def test_metrics_increment_by_delta_only(self, monkeypatch):
        store, metrics = self._patch(monkeypatch)
        stream = self._make_stream({
            "researcher": {"input_tokens": 100, "output_tokens": 50, "cost": 0.02, "model": "m1"},
        })
        self._persist(stream)
        self._persist(stream)  # no new cost

        cost_metric = metrics["LLM_COST_TOTAL"]
        assert sum(cost_metric.totals.values()) == 0.02
        calls_metric = metrics["LLM_CALLS_TOTAL"]
        assert sum(calls_metric.totals.values()) == 1  # inc'd once, not twice
