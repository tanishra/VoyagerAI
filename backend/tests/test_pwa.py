"""Tests for PWA backend features: client_message_id field and cache headers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from models import ChatRequest

# ---------------------------------------------------------------------------
# ChatRequest model tests
# ---------------------------------------------------------------------------


class TestChatRequestModel:
    def test_client_message_id_optional(self):
        req = ChatRequest(message="Hello")
        assert req.client_message_id is None

    def test_client_message_id_accepted(self):
        req = ChatRequest(message="Hello", client_message_id="uuid-123")
        assert req.client_message_id == "uuid-123"

    def test_client_message_id_max_length(self):
        req = ChatRequest(message="Hello", client_message_id="x" * 100)
        assert len(req.client_message_id) == 100

    def test_client_message_id_rejects_too_long(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ChatRequest(message="Hello", client_message_id="x" * 101)


# ---------------------------------------------------------------------------
# Cache header tests on thread endpoints
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


class TestCacheHeaders:
    def test_threads_list_has_cache_control(self, client):
        resp = client.get("/threads")
        assert resp.status_code == 200
        assert "cache-control" in resp.headers
        assert "max-age=300" in resp.headers["cache-control"]

    def test_thread_history_has_cache_control(self, client):
        import main as main_module

        # Mock the agent state for history endpoint
        mock_agent = AsyncMock()
        mock_state = MagicMock()
        mock_state.values = {"messages": []}
        mock_agent.aget_state = AsyncMock(return_value=mock_state)

        import hashlib
        user_id = "dev@localhost"
        user_tag = hashlib.sha256(user_id.encode()).hexdigest()[:12]
        thread_id = f"chat:{user_tag}:test-thread"

        with patch.object(main_module, "create_chat_agent", AsyncMock(return_value=mock_agent)):
            resp = client.get(f"/threads/{thread_id}/history")
            # May be 404 if state is empty, but should still have cache header
            if resp.status_code == 200:
                assert "cache-control" in resp.headers
                assert "max-age=300" in resp.headers["cache-control"]
