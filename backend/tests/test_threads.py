"""Tests for ThreadStore and thread management endpoints.

Uses in-memory ThreadStore (no Redis required) and TestClient with mocked
stream_chat_agent — same pattern as test_preferences.py and test_streaming.py.
"""

from __future__ import annotations

import asyncio
import hashlib
from typing import ClassVar
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from threads import ThreadStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fresh_store():
    """A ThreadStore with no Redis connection — uses in-memory fallback."""
    store = ThreadStore()
    # Force in-memory mode by making _get_redis return None
    store._redis = None
    return store


@pytest.fixture
def client(fresh_store):
    """TestClient with the thread_store patched to use in-memory."""
    import main as main_module

    with (
        patch.object(main_module, "thread_store", fresh_store),
        patch.object(main_module, "stream_chat_agent", _fake_stream),
        TestClient(main_module.app) as c,
    ):
        yield c


async def _fake_stream(message, thread_id, user_id=None):
    yield {"event": "done", "data": None}


# ---------------------------------------------------------------------------
# TestThreadStore — unit tests for the store
# ---------------------------------------------------------------------------


class TestThreadStore:
    @pytest.mark.asyncio
    async def test_list_empty_returns_empty_list(self, fresh_store):
        result = await fresh_store.list_threads("alice")
        assert result == []

    @pytest.mark.asyncio
    async def test_upsert_then_list_returns_thread(self, fresh_store):
        await fresh_store.upsert_thread("alice", "chat:abc:thread1", "Plan a Tokyo trip")
        threads = await fresh_store.list_threads("alice")
        assert len(threads) == 1
        assert threads[0].thread_id == "chat:abc:thread1"
        assert threads[0].summary == "Plan a Tokyo trip"

    @pytest.mark.asyncio
    async def test_upsert_updates_existing_thread(self, fresh_store):
        await fresh_store.upsert_thread("alice", "chat:abc:t1", "First message")
        original = (await fresh_store.list_threads("alice"))[0]
        created = original.created_at

        await asyncio.sleep(0.01)
        await fresh_store.upsert_thread("alice", "chat:abc:t1", "Second message")
        threads = await fresh_store.list_threads("alice")
        assert len(threads) == 1
        assert threads[0].summary == "Second message"
        assert threads[0].created_at == created
        assert threads[0].updated_at > created

    @pytest.mark.asyncio
    async def test_delete_removes_thread(self, fresh_store):
        await fresh_store.upsert_thread("alice", "chat:abc:t1", "Hello")
        assert await fresh_store.delete_thread("alice", "chat:abc:t1") is True
        assert await fresh_store.list_threads("alice") == []

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_false(self, fresh_store):
        assert await fresh_store.delete_thread("alice", "chat:abc:nonexistent") is False

    @pytest.mark.asyncio
    async def test_namespace_isolation(self, fresh_store):
        await fresh_store.upsert_thread("alice", "chat:alice_hash:t1", "Alice's trip")
        await fresh_store.upsert_thread("bob", "chat:bob_hash:t2", "Bob's trip")

        alice_threads = await fresh_store.list_threads("alice")
        bob_threads = await fresh_store.list_threads("bob")

        assert len(alice_threads) == 1
        assert alice_threads[0].summary == "Alice's trip"
        assert len(bob_threads) == 1
        assert bob_threads[0].summary == "Bob's trip"

    @pytest.mark.asyncio
    async def test_list_sorted_by_updated_at_descending(self, fresh_store):
        await fresh_store.upsert_thread("alice", "chat:abc:t1", "First")
        await asyncio.sleep(0.01)
        await fresh_store.upsert_thread("alice", "chat:abc:t2", "Second")
        await asyncio.sleep(0.01)
        await fresh_store.upsert_thread("alice", "chat:abc:t3", "Third")

        threads = await fresh_store.list_threads("alice")
        assert threads[0].summary == "Third"
        assert threads[1].summary == "Second"
        assert threads[2].summary == "First"

    @pytest.mark.asyncio
    async def test_get_thread_returns_metadata(self, fresh_store):
        await fresh_store.upsert_thread("alice", "chat:abc:t1", "My trip")
        result = await fresh_store.get_thread("alice", "chat:abc:t1")
        assert result is not None
        assert result.summary == "My trip"

    @pytest.mark.asyncio
    async def test_get_thread_nonexistent_returns_none(self, fresh_store):
        assert await fresh_store.get_thread("alice", "chat:abc:nope") is None


# ---------------------------------------------------------------------------
# TestThreadsEndpoint — API tests with TestClient
# ---------------------------------------------------------------------------


class TestThreadsEndpoint:
    def test_get_threads_empty_returns_empty_array(self, client):
        resp = client.get("/threads", headers={"X-User-Id": "alice"})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_threads_returns_list(self, client, fresh_store):
        import asyncio

        asyncio.run(fresh_store.upsert_thread("alice", "chat:abc:t1", "Tokyo trip"))
        resp = client.get("/threads", headers={"X-User-Id": "alice"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["thread_id"] == "chat:abc:t1"
        assert data[0]["summary"] == "Tokyo trip"

    def test_delete_thread_returns_ok(self, client, fresh_store):
        import asyncio

        user_tag = hashlib.sha256(b"alice").hexdigest()[:12]
        thread_id = f"chat:{user_tag}:t1"
        asyncio.run(fresh_store.upsert_thread("alice", thread_id, "Trip"))
        resp = client.delete(f"/threads/{thread_id}", headers={"X-User-Id": "alice"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_delete_thread_cross_user_returns_403(self, client, fresh_store):
        import asyncio

        alice_tag = hashlib.sha256(b"alice").hexdigest()[:12]
        thread_id = f"chat:{alice_tag}:t1"
        asyncio.run(fresh_store.upsert_thread("alice", thread_id, "Alice trip"))
        # Bob tries to delete Alice's thread — the prefix won't match bob's hash
        resp = client.delete(f"/threads/{thread_id}", headers={"X-User-Id": "bob"})
        assert resp.status_code == 403

    def test_delete_nonexistent_returns_404(self, client):
        user_tag = hashlib.sha256(b"alice").hexdigest()[:12]
        fake_id = f"chat:{user_tag}:nonexistent"
        resp = client.delete(f"/threads/{fake_id}", headers={"X-User-Id": "alice"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# TestThreadHistoryEndpoint — API tests for history replay
# ---------------------------------------------------------------------------


class TestThreadHistoryEndpoint:
    def test_get_history_cross_user_returns_403(self, client):
        user_tag = hashlib.sha256(b"alice").hexdigest()[:12]
        thread_id = f"chat:{user_tag}:t1"
        # Bob tries to access Alice's thread history
        resp = client.get(f"/threads/{thread_id}/history", headers={"X-User-Id": "bob"})
        assert resp.status_code == 403

    def test_get_history_nonexistent_returns_404(self, client, monkeypatch):
        user_tag = hashlib.sha256(b"alice").hexdigest()[:12]
        thread_id = f"chat:{user_tag}:nonexistent"

        # Mock create_chat_agent to return an agent with empty state
        class _FakeState:
            values: ClassVar[dict] = {}

        class _FakeAgent:
            async def aget_state(self, config):
                return _FakeState()

        import main as main_module

        async def _fake_create(**kw):
            return _FakeAgent()

        monkeypatch.setattr(main_module, "create_chat_agent", _fake_create)
        resp = client.get(f"/threads/{thread_id}/history", headers={"X-User-Id": "alice"})
        assert resp.status_code == 404

    def test_get_history_returns_messages(self, client, monkeypatch):
        user_tag = hashlib.sha256(b"alice").hexdigest()[:12]
        thread_id = f"chat:{user_tag}:t1"

        class _Msg:
            def __init__(self, msg_type, content):
                self.type = msg_type
                self.content = content

        class _FakeState:
            values: ClassVar[dict] = {
                "messages": [
                    _Msg("human", "Plan a Tokyo trip"),
                    _Msg("ai", "Sure! Let me help you plan that."),
                ]
            }

        class _FakeAgent:
            async def aget_state(self, config):
                return _FakeState()

        import main as main_module

        async def _fake_create(**kw):
            return _FakeAgent()

        monkeypatch.setattr(main_module, "create_chat_agent", _fake_create)
        resp = client.get(f"/threads/{thread_id}/history", headers={"X-User-Id": "alice"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["role"] == "user"
        assert data[0]["content"] == "Plan a Tokyo trip"
        assert data[1]["role"] == "assistant"
        assert data[1]["content"] == "Sure! Let me help you plan that."


# ---------------------------------------------------------------------------
# TestThreadAutoSave — verify chat stream saves thread metadata
# ---------------------------------------------------------------------------


class TestThreadAutoSave:
    def test_chat_stream_saves_thread_metadata(self, client, fresh_store):
        import asyncio
        import json as _json

        with client.stream(
            "POST", "/chat/stream",
            json={"message": "Plan a 3-day Tokyo trip"},
            headers={"X-User-Id": "alice"},
        ) as r:
            assert r.status_code == 200
            for line in r.iter_lines():
                if line.startswith("data: "):
                    _json.loads(line[6:])  # consume all events

        # The thread metadata should now be in the store
        threads = asyncio.run(fresh_store.list_threads("alice"))
        assert len(threads) == 1
        assert "Tokyo" in threads[0].summary
