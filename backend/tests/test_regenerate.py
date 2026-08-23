"""Tests for message regeneration: endpoint, branch listing, and history with checkpoint_id."""

from __future__ import annotations

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    """TestClient with dev bypass and mocked thread_store."""
    import main as main_module

    monkeypatch.setattr("config.settings.AUTH_DEV_BYPASS", True)

    mock_thread_store = MagicMock()
    mock_thread_store.list_threads = AsyncMock(return_value=[])
    mock_thread_store.count_threads = AsyncMock(return_value=0)
    mock_thread_store.update_status = AsyncMock()
    mock_thread_store.upsert_thread = AsyncMock()

    with (
        patch.object(main_module, "thread_store", mock_thread_store),
        TestClient(main_module.app) as c,
    ):
        yield c


def _scoped_thread_id(raw: str = "test-thread") -> str:
    user_id = "dev@localhost"
    user_tag = hashlib.sha256(user_id.encode()).hexdigest()[:12]
    return f"chat:{user_tag}:{raw}"


class TestRegenerateEndpoint:
    def test_regenerate_requires_thread_id(self, client):
        resp = client.post("/chat/regenerate", json={})
        assert resp.status_code == 400

    def test_regenerate_scopes_thread_id_per_user(self, client, monkeypatch):
        """Cross-user thread_id gets re-scoped to the current user (no cross-user leak)."""
        import main as main_module

        captured_thread_id = []

        async def fake_regenerate(*, thread_id, user_id, locale, cancel_event):
            captured_thread_id.append(thread_id)
            yield {"event": "done", "data": None}

        monkeypatch.setattr(main_module, "regenerate_chat_agent", fake_regenerate)

        # Alice's thread — should get re-scoped to dev user
        alice_tag = hashlib.sha256(b"alice").hexdigest()[:12]
        alice_thread = f"chat:{alice_tag}:some-thread"

        with client.stream(
            "POST", "/chat/regenerate",
            json={"thread_id": alice_thread},
        ) as r:
            assert r.status_code == 200
            # Consume the stream
            list(r.iter_lines())

        # The thread_id passed to regenerate_chat_agent should be scoped to dev user
        dev_tag = hashlib.sha256(b"dev@localhost").hexdigest()[:12]
        assert captured_thread_id
        assert captured_thread_id[0].startswith(f"chat:{dev_tag}:")

    def test_regenerate_returns_sse_stream(self, client, monkeypatch):
        """Regenerate endpoint returns a valid SSE stream with events."""
        import main as main_module

        async def fake_regenerate(*, thread_id, user_id, locale, cancel_event):
            yield {"event": "on_chat_model_stream", "data": {"chunk": "Hi"}}
            yield {"event": "done", "data": None}

        monkeypatch.setattr(main_module, "regenerate_chat_agent", fake_regenerate)

        scoped = _scoped_thread_id("regen-test")
        with client.stream(
            "POST", "/chat/regenerate",
            json={"thread_id": scoped},
        ) as r:
            assert r.status_code == 200
            lines = list(r.iter_lines())
            # Should have thread_id, status, token, done events
            data_lines = [l for l in lines if l.startswith("data: ")]
            assert len(data_lines) >= 2  # at least thread_id + done

    def test_regenerate_cancel_works(self, client, monkeypatch):
        """Cancel event is respected during regeneration."""
        import main as main_module

        async def fake_regenerate(*, thread_id, user_id, locale, cancel_event):
            yield {"event": "on_chat_model_stream", "data": {"chunk": "partial"}}
            if cancel_event:
                cancel_event.set()
            yield {"event": "cancelled", "data": None}

        monkeypatch.setattr(main_module, "regenerate_chat_agent", fake_regenerate)

        scoped = _scoped_thread_id("regen-cancel")
        with client.stream(
            "POST", "/chat/regenerate",
            json={"thread_id": scoped},
        ) as r:
            assert r.status_code == 200
            lines = list(r.iter_lines())
            # Should contain a cancelled event
            events = [l for l in lines if l.startswith("event: ")]
            assert any("cancelled" in e for e in events)

    def test_regenerate_error_yields_error_event(self, client, monkeypatch):
        """If regenerate raises, an error SSE event is emitted."""
        import main as main_module

        async def failing_regenerate(*, thread_id, user_id, locale, cancel_event):
            raise RuntimeError("boom")

        monkeypatch.setattr(main_module, "regenerate_chat_agent", failing_regenerate)

        scoped = _scoped_thread_id("regen-error")
        with client.stream(
            "POST", "/chat/regenerate",
            json={"thread_id": scoped},
        ) as r:
            assert r.status_code == 200
            lines = list(r.iter_lines())
            events = [l for l in lines if l.startswith("event: ")]
            assert any("error" in e for e in events)


class TestBranchesEndpoint:
    def test_branches_scopes_thread_id_per_user(self, client):
        """Cross-user thread access returns 403."""
        alice_tag = hashlib.sha256(b"alice").hexdigest()[:12]
        thread_id = f"chat:{alice_tag}:some-thread"
        resp = client.get(f"/threads/{thread_id}/branches")
        assert resp.status_code == 403

    def test_branches_returns_empty_for_no_fork_point(self, client, monkeypatch):
        """When _find_fork_checkpoint returns None, branches is empty."""
        import main as main_module

        async def fake_find_fork(agent, config):
            return None

        monkeypatch.setattr(main_module, "_find_fork_checkpoint", fake_find_fork)

        scoped = _scoped_thread_id("no-branches")
        resp = client.get(f"/threads/{scoped}/branches")
        assert resp.status_code == 200
        assert resp.json() == {"branches": []}

    def test_branches_returns_branch_list(self, client, monkeypatch):
        """When forks exist, branches endpoint returns them."""
        import main as main_module

        fork_checkpoint_id = "fork-parent-123"
        branch_1_id = "branch-1"
        branch_2_id = "branch-2"

        class _FakeSnapshot:
            def __init__(self, config, parent_config, messages):
                self.config = config
                self.parent_config = parent_config
                self.values = {"messages": messages}

        class _FakeMsg:
            def __init__(self, content):
                self.content = content

        class _FakeState:
            config = {"configurable": {"checkpoint_id": branch_1_id}}
            values = {"messages": []}

        class _FakeAgent:
            async def aget_state(self, config):
                return _FakeState()

            async def aget_state_history(self, config):
                # Yield two branches from the same fork point
                yield _FakeSnapshot(
                    config={"configurable": {"checkpoint_id": branch_1_id}},
                    parent_config={"configurable": {"checkpoint_id": fork_checkpoint_id}},
                    messages=[_FakeMsg("Response 1")],
                )
                yield _FakeSnapshot(
                    config={"configurable": {"checkpoint_id": branch_2_id}},
                    parent_config={"configurable": {"checkpoint_id": fork_checkpoint_id}},
                    messages=[_FakeMsg("Response 2")],
                )

        async def fake_find_fork(agent, config):
            return {"configurable": {"checkpoint_id": fork_checkpoint_id}}

        async def fake_create(**kw):
            return _FakeAgent()

        monkeypatch.setattr(main_module, "_find_fork_checkpoint", fake_find_fork)
        monkeypatch.setattr(main_module, "create_chat_agent", fake_create)

        scoped = _scoped_thread_id("with-branches")
        resp = client.get(f"/threads/{scoped}/branches")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["branches"]) == 2
        assert data["branches"][0]["checkpoint_id"] == branch_1_id
        assert data["branches"][0]["is_current"] is True
        assert data["branches"][1]["checkpoint_id"] == branch_2_id
        assert data["branches"][1]["is_current"] is False


class TestHistoryWithCheckpointId:
    def test_history_accepts_checkpoint_id_param(self, client, monkeypatch):
        """History endpoint accepts optional checkpoint_id query param."""
        import main as main_module

        class _Msg:
            def __init__(self, msg_type, content):
                self.type = msg_type
                self.content = content

        class _FakeState:
            values = {
                "messages": [
                    _Msg("human", "Plan a trip"),
                    _Msg("ai", "Sure!"),
                ]
            }

        class _FakeAgent:
            async def aget_state(self, config):
                # Verify checkpoint_id is in config
                assert "checkpoint_id" in config.get("configurable", {})
                assert config["configurable"]["checkpoint_id"] == "branch-xyz"
                return _FakeState()

        async def fake_create(**kw):
            return _FakeAgent()

        monkeypatch.setattr(main_module, "create_chat_agent", fake_create)

        scoped = _scoped_thread_id("history-branch")
        resp = client.get(f"/threads/{scoped}/history?checkpoint_id=branch-xyz")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["role"] == "user"
        assert data[1]["role"] == "assistant"

    def test_history_without_checkpoint_id_works(self, client, monkeypatch):
        """History endpoint still works without checkpoint_id (backward compat)."""
        import main as main_module

        class _Msg:
            def __init__(self, msg_type, content):
                self.type = msg_type
                self.content = content

        class _FakeState:
            values = {
                "messages": [
                    _Msg("human", "Hello"),
                    _Msg("ai", "Hi there!"),
                ]
            }

        class _FakeAgent:
            async def aget_state(self, config):
                # checkpoint_id should NOT be in config
                assert "checkpoint_id" not in config.get("configurable", {})
                return _FakeState()

        async def fake_create(**kw):
            return _FakeAgent()

        monkeypatch.setattr(main_module, "create_chat_agent", fake_create)

        scoped = _scoped_thread_id("history-normal")
        resp = client.get(f"/threads/{scoped}/history")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
