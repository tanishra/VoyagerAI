"""Tests for R4: payload replay on history load.

Cards are delivered via one-shot payload keys; a durable per-id record in
thread state lets history re-attach them. Payload tool messages must not
render as raw JSON.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _comparison() -> dict:
    return {
        "plans": [
            {"tier": "budget", "itinerary": {"destination": "Delhi", "total_days": 5, "currency": "INR", "estimated_total_cost_usd": 30000}},
            {"tier": "balanced", "itinerary": {"destination": "Delhi", "total_days": 5, "currency": "INR", "estimated_total_cost_usd": 48000}},
            {"tier": "premium", "itinerary": {"destination": "Delhi", "total_days": 5, "currency": "INR", "estimated_total_cost_usd": 75000}},
        ],
        "comparison_matrix": {"total_cost": {"budget": 30000, "balanced": 48000, "premium": 75000}},
    }


def _itinerary() -> dict:
    return {"destination": "Delhi", "total_days": 5, "currency": "INR", "estimated_total_cost_usd": 48000, "days": []}


class TestStorePayload:
    def test_writes_per_id_record_and_latest_keys(self, monkeypatch):
        from agents import pipeline

        writes = {}

        async def fake_store(pid, kind, data):
            writes["one_shot"] = (pid, kind, data)

        async def fake_set(tid, key, data):
            writes[key] = data

        monkeypatch.setattr(pipeline.payload_store, "store", fake_store)
        monkeypatch.setattr(pipeline.payload_store, "set_thread_state", fake_set)

        pid = _run(pipeline.store_payload("tid", "comparison", _comparison()))

        assert writes["one_shot"][0] == pid
        assert writes[f"payload:{pid}"] == {"kind": "comparison", "data": _comparison()}
        assert writes["latest_comparison"] == _comparison()
        assert writes["latest_comparison_id"] == pid

    def test_itinerary_kind_gets_latest_itinerary(self, monkeypatch):
        from agents import pipeline

        writes = {}

        async def fake_store(pid, kind, data):
            pass

        async def fake_set(tid, key, data):
            writes[key] = data

        monkeypatch.setattr(pipeline.payload_store, "store", fake_store)
        monkeypatch.setattr(pipeline.payload_store, "set_thread_state", fake_set)

        pid = _run(pipeline.store_payload("tid", "itinerary", _itinerary()))
        assert writes["latest_itinerary"] == _itinerary()
        assert writes["latest_itinerary_id"] == pid


# ---------------------------------------------------------------------------
# History endpoint replay
# ---------------------------------------------------------------------------


def _create_dev_session():
    from oauth import DEV_USER, create_session
    return _run(create_session(DEV_USER))


@pytest.fixture
def client(monkeypatch):
    import main as main_module

    mock_thread_store = MagicMock()
    mock_thread_store.list_threads = AsyncMock(return_value=[])
    mock_thread_store.count_threads = AsyncMock(return_value=0)
    mock_thread_store.update_status = AsyncMock()
    mock_thread_store.upsert_thread = AsyncMock()

    session_id = _create_dev_session()

    # Skip geocoding on replayed itineraries
    async def _ident(it):
        return it
    monkeypatch.setattr(main_module, "_enrich_itinerary_with_coordinates", _ident)

    with (
        patch.object(main_module, "thread_store", mock_thread_store),
        TestClient(main_module.app) as c,
    ):
        c.cookies.set("voyager_session", session_id)
        c.cookies.set("voyager_csrf", "test-csrf-token")
        yield c


def _scoped(raw: str) -> str:
    tag = hashlib.sha256(b"dev@localhost").hexdigest()[:12]
    return f"chat:{tag}:{raw}"


class _Msg:
    def __init__(self, msg_type, content):
        self.type = msg_type
        self.content = content


def _tool_msg(payload_id: str) -> _Msg:
    return _Msg("tool", json.dumps({
        "_pipeline_payload_id": payload_id,
        "_stage_usage": {},
        "message": "Plans generated. Briefly compare...",
    }))


def _wire(monkeypatch, messages, records: dict):
    """records: {payload_id: {"kind":..., "data":...} | None}"""
    import main as main_module
    import payload_store as ps_module

    async def fake_read(tid, checkpoint_id=None):
        return {"messages": messages}

    async def fake_get_state(tid, key):
        if key.startswith("payload:"):
            return records.get(key[len("payload:"):])
        return None

    monkeypatch.setattr(main_module, "_read_thread_values", fake_read)
    monkeypatch.setattr(main_module, "load_all_activity", AsyncMock(return_value=None), raising=False)
    monkeypatch.setattr(ps_module.payload_store, "get_thread_state", fake_get_state)


class TestHistoryReplay:
    def test_card_attached_to_next_assistant_and_tool_hidden(self, client, monkeypatch):
        rec = {"kind": "comparison", "data": _comparison()}
        _wire(monkeypatch, [
            _Msg("human", "Plan a Delhi trip"),
            _tool_msg("p1"),
            _Msg("ai", "Here are three options for you."),
        ], {"p1": rec})

        resp = client.get(f"/threads/{_scoped('h1')}/history")
        assert resp.status_code == 200
        data = resp.json()
        # Tool JSON not rendered as a message
        assert all("_pipeline_payload_id" not in (m["content"] or "") for m in data)
        assert len(data) == 2
        assert data[1]["role"] == "assistant"
        assert data[1]["comparison"]["plans"][0]["tier"] == "budget"

    def test_orphan_tool_msg_emits_card_only_entry(self, client, monkeypatch):
        rec = {"kind": "comparison", "data": _comparison()}
        _wire(monkeypatch, [
            _Msg("human", "Plan a Delhi trip"),
            _tool_msg("p1"),
        ], {"p1": rec})

        resp = client.get(f"/threads/{_scoped('h2')}/history")
        data = resp.json()
        assert len(data) == 2
        assert data[1]["comparison"]["plans"][1]["tier"] == "balanced"
        assert "_pipeline_payload_id" not in data[1]["content"]

    def test_missing_record_hides_tool_and_no_card(self, client, monkeypatch):
        _wire(monkeypatch, [
            _Msg("human", "Plan a Delhi trip"),
            _tool_msg("gone"),
            _Msg("ai", "Done."),
        ], {})

        resp = client.get(f"/threads/{_scoped('h3')}/history")
        data = resp.json()
        assert len(data) == 2
        assert "comparison" not in data[1]
        assert "_pipeline_payload_id" not in (data[1]["content"] or "")

    def test_multiple_payloads_attach_to_own_turns(self, client, monkeypatch):
        c1, c2 = _comparison(), _comparison()
        c2["plans"][0]["itinerary"]["estimated_total_cost_usd"] = 99999
        _wire(monkeypatch, [
            _Msg("human", "Plan Delhi"),
            _tool_msg("p1"),
            _Msg("ai", "First comparison."),
            _Msg("human", "Try again"),
            _tool_msg("p2"),
            _Msg("ai", "Second comparison."),
        ], {"p1": {"kind": "comparison", "data": c1},
            "p2": {"kind": "comparison", "data": c2}})

        resp = client.get(f"/threads/{_scoped('h4')}/history")
        data = resp.json()
        assistants = [m for m in data if m["role"] == "assistant"]
        assert len(assistants) == 2
        assert assistants[0]["comparison"]["plans"][0]["itinerary"]["estimated_total_cost_usd"] == 30000
        assert assistants[1]["comparison"]["plans"][0]["itinerary"]["estimated_total_cost_usd"] == 99999

    def test_itinerary_replay(self, client, monkeypatch):
        _wire(monkeypatch, [
            _Msg("human", "Plan Delhi"),
            _tool_msg("pi"),
            _Msg("ai", "Here's your itinerary."),
        ], {"pi": {"kind": "itinerary", "data": _itinerary()}})

        resp = client.get(f"/threads/{_scoped('h5')}/history")
        data = resp.json()
        assert data[1]["itinerary"]["destination"] == "Delhi"

    def test_legacy_tag_extraction_still_works(self, client, monkeypatch):
        tagged = 'Sure! <comparison>{"plans": [{"tier": "budget", "itinerary": {"destination": "Goa", "total_days": 2, "currency": "INR", "estimated_total_cost_usd": 10000}}, {"tier": "balanced", "itinerary": {"destination": "Goa", "total_days": 2, "currency": "INR", "estimated_total_cost_usd": 20000}}, {"tier": "premium", "itinerary": {"destination": "Goa", "total_days": 2, "currency": "INR", "estimated_total_cost_usd": 30000}}], "comparison_matrix": {}}</comparison>'
        _wire(monkeypatch, [
            _Msg("human", "Plan Goa"),
            _Msg("ai", tagged),
        ], {})

        resp = client.get(f"/threads/{_scoped('h6')}/history")
        data = resp.json()
        assert data[1]["comparison"]["plans"][0]["tier"] == "budget"
        assert "<comparison>" not in data[1]["content"]

    def test_store_error_does_not_break_history(self, client, monkeypatch):
        import main as main_module
        import payload_store as ps_module

        async def fake_read(tid, checkpoint_id=None):
            return {"messages": [_Msg("human", "hi"), _tool_msg("x"), _Msg("ai", "ok")]}

        async def boom(tid, key):
            raise RuntimeError("redis down")

        monkeypatch.setattr(main_module, "_read_thread_values", fake_read)
        monkeypatch.setattr(ps_module.payload_store, "get_thread_state", boom)

        resp = client.get(f"/threads/{_scoped('h7')}/history")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2  # tool msg hidden, card absent


def _clarify() -> dict:
    return {"questions": [
        {"field": "travel_style", "header": "Travel style", "question": "What pace do you prefer?",
         "options": [{"label": "Relaxed"}, {"label": "Adventurous"}], "multi_select": False},
    ]}


class TestClarifyReplay:
    def test_clarify_card_attached_on_reload(self, client, monkeypatch):
        _wire(monkeypatch, [
            _Msg("human", "Plan a trip"),
            _tool_msg("pc"),
            _Msg("ai", "A few quick questions:"),
        ], {"pc": {"kind": "clarify", "data": _clarify()}})

        resp = client.get(f"/threads/{_scoped('c1')}/history")
        data = resp.json()
        assert len(data) == 2
        assert data[1]["clarify"]["questions"][0]["field"] == "travel_style"


class TestClarifyTool:
    def test_tool_stores_payload_and_clamps(self, monkeypatch):
        import agents.tools.pipeline_tools as pt
        from agents.tools.visuals import set_current_thread_id

        stored = {}

        async def fake_store(tid, kind, data):
            stored["kind"] = kind
            stored["data"] = data
            return "pid1"

        monkeypatch.setattr(pt, "store_payload", fake_store)
        set_current_thread_id("t1")

        qs = [
            pt.ClarifyQuestion(
                field="f", header="h", question="q?",
                options=[pt.ClarifyOption(label=f"o{i}") for i in range(6)],
            )
            for _ in range(6)
        ]
        result = _run(pt.ask_clarifying_questions.ainvoke({"questions": [q.model_dump() for q in qs]}))

        assert stored["kind"] == "clarify"
        assert len(stored["data"]["questions"]) == 4  # clamped
        assert len(stored["data"]["questions"][0]["options"]) == 4
        assert "_pipeline_payload_id" in result

    def test_empty_questions_returns_text_fallback(self, monkeypatch):
        import agents.tools.pipeline_tools as pt
        from agents.tools.visuals import set_current_thread_id
        set_current_thread_id("t1")
        result = _run(pt.ask_clarifying_questions.ainvoke({"questions": []}))
        assert "plain text" in result

    def test_clarify_is_pipeline_tool(self):
        from agents.pipeline import is_pipeline_tool
        assert is_pipeline_tool("ask_clarifying_questions")
        assert is_pipeline_tool("generate_trip_plans")
