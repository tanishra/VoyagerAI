"""Tests for message editing: endpoint validation, SSE streaming, cancel, and error handling."""

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


class TestEditEndpoint:
    def test_edit_requires_thread_id(self, client):
        resp = client.post("/chat/edit", json={"message": "edited text"})
        assert resp.status_code == 400

    def test_edit_requires_message(self, client):
        scoped = _scoped_thread_id("edit-test")
        resp = client.post("/chat/edit", json={"thread_id": scoped})
        assert resp.status_code == 400

    def test_edit_scopes_thread_id_per_user(self, client, monkeypatch):
        """Cross-user thread_id gets re-scoped to the current user (no cross-user leak)."""
        import main as main_module

        captured_thread_id = []

        async def fake_edit(*, thread_id, new_message, user_id, locale, timezone, cancel_event):
            captured_thread_id.append(thread_id)
            yield {"event": "done", "data": None}

        monkeypatch.setattr(main_module, "edit_chat_agent", fake_edit)

        alice_tag = hashlib.sha256(b"alice").hexdigest()[:12]
        alice_thread = f"chat:{alice_tag}:some-thread"

        with client.stream(
            "POST", "/chat/edit",
            json={"thread_id": alice_thread, "message": "edited"},
        ) as r:
            assert r.status_code == 200
            list(r.iter_lines())

        dev_tag = hashlib.sha256(b"dev@localhost").hexdigest()[:12]
        assert captured_thread_id
        assert captured_thread_id[0].startswith(f"chat:{dev_tag}:")

    def test_edit_returns_sse_stream(self, client, monkeypatch):
        """Edit endpoint returns a valid SSE stream with events."""
        import main as main_module

        async def fake_edit(*, thread_id, new_message, user_id, locale, timezone, cancel_event):
            yield {"event": "on_chat_model_stream", "data": {"chunk": "Hi"}}
            yield {"event": "done", "data": None}

        monkeypatch.setattr(main_module, "edit_chat_agent", fake_edit)

        scoped = _scoped_thread_id("edit-stream")
        with client.stream(
            "POST", "/chat/edit",
            json={"thread_id": scoped, "message": "edited content"},
        ) as r:
            assert r.status_code == 200
            lines = list(r.iter_lines())
            data_lines = [l for l in lines if l.startswith("data: ")]
            assert len(data_lines) >= 2

    def test_edit_cancel_works(self, client, monkeypatch):
        """Cancel event is respected during edit."""
        import main as main_module

        async def fake_edit(*, thread_id, new_message, user_id, locale, timezone, cancel_event):
            yield {"event": "on_chat_model_stream", "data": {"chunk": "partial"}}
            if cancel_event:
                cancel_event.set()
            yield {"event": "cancelled", "data": None}

        monkeypatch.setattr(main_module, "edit_chat_agent", fake_edit)

        scoped = _scoped_thread_id("edit-cancel")
        with client.stream(
            "POST", "/chat/edit",
            json={"thread_id": scoped, "message": "edited"},
        ) as r:
            assert r.status_code == 200
            lines = list(r.iter_lines())
            events = [l for l in lines if l.startswith("event: ")]
            assert any("cancelled" in e for e in events)

    def test_edit_error_yields_error_event(self, client, monkeypatch):
        """If edit raises, an error SSE event is emitted."""
        import main as main_module

        async def failing_edit(*, thread_id, new_message, user_id, locale, timezone, cancel_event):
            raise RuntimeError("boom")

        monkeypatch.setattr(main_module, "edit_chat_agent", failing_edit)

        scoped = _scoped_thread_id("edit-error")
        with client.stream(
            "POST", "/chat/edit",
            json={"thread_id": scoped, "message": "edited"},
        ) as r:
            assert r.status_code == 200
            lines = list(r.iter_lines())
            events = [l for l in lines if l.startswith("event: ")]
            assert any("error" in e for e in events)

    def test_edit_passes_new_message_to_agent(self, client, monkeypatch):
        """The edited message content is passed to edit_chat_agent."""
        import main as main_module

        captured_message = []

        async def fake_edit(*, thread_id, new_message, user_id, locale, timezone, cancel_event):
            captured_message.append(new_message)
            yield {"event": "done", "data": None}

        monkeypatch.setattr(main_module, "edit_chat_agent", fake_edit)

        scoped = _scoped_thread_id("edit-message")
        with client.stream(
            "POST", "/chat/edit",
            json={"thread_id": scoped, "message": "10 days in Japan"},
        ) as r:
            assert r.status_code == 200
            list(r.iter_lines())

        assert captured_message
        assert captured_message[0] == "10 days in Japan"
