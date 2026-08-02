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
                self.stream_calls = 0

            async def astream_events(self, *args, **kwargs):
                self.stream_calls += 1
                yield {"event": "on_chat_model_stream", "data": {"chunk": None}}

            async def aget_state(self, config):
                self.get_state_calls += 1
                if self.get_state_calls == 1:
                    return _fake_state([_Msg("Just some prose, no JSON here.")])
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
            def __init__(self):
                self.stream_calls = 0

            async def astream_events(self, *args, **kwargs):
                self.stream_calls += 1
                yield {"event": "on_chat_model_stream", "data": {"chunk": None}}

            async def aget_state(self, config):
                return _fake_state([_Msg('{"destination": "Paris", "days": []}')])

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
        assert events[-1] == ("done", None)

    def test_retry_uses_hint_and_formatter_recovers(self, monkeypatch):
        import asyncio

        import agents.deep_agent as deep_agent_module

        class _Msg:
            def __init__(self, content):
                self.content = content

        prose = "Here is a lovely trip plan for Paris with great food. " * 50

        class _FakeAgent:
            def __init__(self):
                self.inputs = []

            async def astream_events(self, inputs, *args, **kwargs):
                self.inputs.append(inputs)
                yield {"event": "on_chat_model_stream", "data": {"chunk": None}}

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
        assert events[-1] == ("done", None)

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

        assert events[-1] == ("done", None)
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
        assert fake.get_state_calls == 0  # stream text alone was sufficient
        assert events[-2] == (
            "itinerary",
            {"destination": "Udaipur, India", "total_days": 1, "days": []},
        )
        assert events[-1] == ("done", None)

    def test_hint_prefers_stream_text_over_state(self, monkeypatch):
        import asyncio

        import agents.deep_agent as deep_agent_module

        class _Msg:
            def __init__(self, content):
                self.content = content

        full_prose = "Here is the complete revised plan. " * 60

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
        import agents.deep_agent as deep_agent_module
        from langgraph.checkpoint.redis.aio import AsyncRedisSaver

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

        import agents.deep_agent as deep_agent_module
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

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

        import agents.deep_agent as deep_agent_module
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        db = tmp_path / "checkpoints.sqlite"
        monkeypatch.setattr(deep_agent_module, "_sqlite_checkpointer", None)
        monkeypatch.setattr(deep_agent_module.settings, "CHECKPOINTER_DB_PATH", str(db))
        monkeypatch.setattr(deep_agent_module.settings, "CHECKPOINTER_BACKEND", "sqlite")

        saver = asyncio.run(deep_agent_module.create_checkpointer())
        assert isinstance(saver, AsyncSqliteSaver)

    def test_checkpointer_backend_redis_falls_back_gracefully(self, tmp_path, monkeypatch):
        import asyncio

        import agents.deep_agent as deep_agent_module
        from langgraph.checkpoint.memory import MemorySaver

        monkeypatch.setattr(deep_agent_module.settings, "CHECKPOINTER_BACKEND", "redis")
        monkeypatch.setattr(deep_agent_module, "create_redis_checkpointer", _raise_on_call)
        monkeypatch.setattr(deep_agent_module, "create_sqlite_checkpointer", _raise_on_call)

        saver = asyncio.run(deep_agent_module.create_checkpointer())
        assert isinstance(saver, MemorySaver)


async def _raise_on_call(*args, **kwargs):
    raise RuntimeError("forced failure")


class TestChatStreamEndpoint:
    """End-to-end SSE wiring: /chat/stream must deliver the full event sequence."""

    def test_event_sequence(self, monkeypatch):
        import json as _json

        import main as main_module
        from fastapi.testclient import TestClient

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

        import main as main_module
        from fastapi.testclient import TestClient

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

    def test_thread_id_is_user_scoped(self, monkeypatch):
        import hashlib
        import json as _json

        import main as main_module
        from fastapi.testclient import TestClient

        async def fake_stream_chat_agent(message, thread_id, user_id=None):
            yield {"event": "done", "data": None}

        monkeypatch.setattr(main_module, "stream_chat_agent", fake_stream_chat_agent)
        user_tag = hashlib.sha256(b"user-a").hexdigest()[:12]

        with TestClient(main_module.app) as c, c.stream(
            "POST", "/chat/stream",
            json={"message": "hello"},
            headers={"X-User-Id": "user-a"},
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

        import main as main_module
        from fastapi.testclient import TestClient

        async def fake_stream_chat_agent(message, thread_id, user_id=None):
            yield {"event": "done", "data": None}

        monkeypatch.setattr(main_module, "stream_chat_agent", fake_stream_chat_agent)
        user_tag = hashlib.sha256(b"user-a").hexdigest()[:12]
        resume_id = f"chat:{user_tag}:abc123"

        with TestClient(main_module.app) as c, c.stream(
            "POST", "/chat/stream",
            json={"message": "hello", "thread_id": resume_id},
            headers={"X-User-Id": "user-a"},
        ) as r:
            parsed = []
            for line in r.iter_lines():
                if line.startswith("data: "):
                    parsed.append(_json.loads(line[6:]))

        assert parsed[0]["data"]["thread_id"] == resume_id

    def test_unscoped_client_thread_id_gets_scoped(self, monkeypatch):
        import hashlib
        import json as _json

        import main as main_module
        from fastapi.testclient import TestClient

        async def fake_stream_chat_agent(message, thread_id, user_id=None):
            yield {"event": "done", "data": None}

        monkeypatch.setattr(main_module, "stream_chat_agent", fake_stream_chat_agent)
        user_tag = hashlib.sha256(b"user-a").hexdigest()[:12]

        with TestClient(main_module.app) as c, c.stream(
            "POST", "/chat/stream",
            json={"message": "hello", "thread_id": "plain-id"},
            headers={"X-User-Id": "user-a"},
        ) as r:
            parsed = []
            for line in r.iter_lines():
                if line.startswith("data: "):
                    parsed.append(_json.loads(line[6:]))

        assert parsed[0]["data"]["thread_id"] == f"chat:{user_tag}:plain-id"

    def test_agent_exception_yields_error_event(self, monkeypatch):
        import json as _json

        import main as main_module
        from fastapi.testclient import TestClient

        async def failing_stream_chat_agent(message, thread_id, user_id=None):
            yield {"event": "on_chat_model_stream", "data": {"chunk": "part"}}
            raise RuntimeError("boom")

        monkeypatch.setattr(main_module, "stream_chat_agent", failing_stream_chat_agent)
        with TestClient(main_module.app) as c, c.stream(
            "POST", "/chat/stream",
            json={"message": "hello"},
            headers={"X-User-Id": "tester"},
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
