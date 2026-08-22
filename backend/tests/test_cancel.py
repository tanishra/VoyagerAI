"""Tests for chat stream cancellation: cancel registry, endpoint, and event parsing."""

from __future__ import annotations

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from cancel_registry import _cancel_events, cancel_stream, register_cancel, unregister_cancel
from main import _parse_chat_event


# ---------------------------------------------------------------------------
# Cancel registry unit tests
# ---------------------------------------------------------------------------


class TestCancelRegistry:
    def test_register_and_cancel(self):
        unregister_cancel("test-thread-1")
        event = register_cancel("test-thread-1")
        assert not event.is_set()
        result = cancel_stream("test-thread-1")
        assert result is True
        assert event.is_set()
        unregister_cancel("test-thread-1")

    def test_cancel_unknown_returns_false(self):
        unregister_cancel("nonexistent-thread")
        result = cancel_stream("nonexistent-thread")
        assert result is False

    def test_unregister_removes_entry(self):
        register_cancel("test-thread-2")
        assert "test-thread-2" in _cancel_events
        unregister_cancel("test-thread-2")
        assert "test-thread-2" not in _cancel_events

    def test_unregister_unknown_is_noop(self):
        unregister_cancel("never-registered")
        assert "never-registered" not in _cancel_events

    def test_register_replaces_existing(self):
        event1 = register_cancel("test-thread-3")
        event2 = register_cancel("test-thread-3")
        assert event1 is not event2
        assert _cancel_events["test-thread-3"] is event2
        unregister_cancel("test-thread-3")


# ---------------------------------------------------------------------------
# _parse_chat_event — cancelled event
# ---------------------------------------------------------------------------


class TestCancelledEventParsing:
    def test_cancelled_event_emits_sse(self):
        event = {"event": "cancelled", "data": None}
        payloads = _parse_chat_event(event, {})
        assert len(payloads) == 1
        assert payloads[0]["event"] == "cancelled"

    def test_cancelled_event_not_filtered_by_subagent_ids(self):
        subagent_run_ids = {"task-run-1"}
        event = {"event": "cancelled", "data": None}
        payloads = _parse_chat_event(event, {}, subagent_run_ids)
        assert len(payloads) == 1
        assert payloads[0]["event"] == "cancelled"


# ---------------------------------------------------------------------------
# Cancel endpoint tests
# ---------------------------------------------------------------------------


@pytest.fixture
def client(monkeypatch):
    """TestClient with dev bypass and mocked thread_store."""
    import main as main_module

    monkeypatch.setattr("config.settings.AUTH_DEV_BYPASS", True)

    mock_thread_store = MagicMock()
    mock_thread_store.list_threads = AsyncMock(return_value=[])
    mock_thread_store.count_threads = AsyncMock(return_value=0)
    mock_thread_store.update_status = AsyncMock()

    with (
        patch.object(main_module, "thread_store", mock_thread_store),
        TestClient(main_module.app) as c,
    ):
        yield c


class TestCancelEndpoint:
    def test_cancel_returns_true_for_registered_thread(self, client):
        user_id = "dev@localhost"
        user_tag = hashlib.sha256(user_id.encode()).hexdigest()[:12]
        thread_id = f"chat:{user_tag}:test-cancel"

        register_cancel(thread_id)
        try:
            resp = client.post("/chat/cancel", json={"thread_id": thread_id})
            assert resp.status_code == 200
            assert resp.json() == {"cancelled": True}
        finally:
            unregister_cancel(thread_id)

    def test_cancel_returns_false_for_unknown_thread(self, client):
        resp = client.post("/chat/cancel", json={"thread_id": "chat:unknown:xyz"})
        assert resp.status_code == 200
        assert resp.json() == {"cancelled": False}

    def test_cancel_requires_thread_id(self, client):
        resp = client.post("/chat/cancel", json={})
        assert resp.status_code == 400

    def test_cancel_scopes_thread_id_per_user(self, client):
        """A raw thread_id from the client gets scoped with the user hash."""
        user_id = "dev@localhost"
        user_tag = hashlib.sha256(user_id.encode()).hexdigest()[:12]
        scoped = f"chat:{user_tag}:my-thread"

        register_cancel(scoped)
        try:
            # Client sends un-scoped thread_id; endpoint scopes it
            resp = client.post("/chat/cancel", json={"thread_id": "my-thread"})
            assert resp.status_code == 200
            assert resp.json() == {"cancelled": True}
        finally:
            unregister_cancel(scoped)
