"""Tests for thread pinning & favoriting functionality."""

from __future__ import annotations

import asyncio
import hashlib
from typing import ClassVar
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from threads import ThreadStore


@pytest.fixture
def fresh_store():
    """A ThreadStore with no Redis connection — uses in-memory fallback."""
    store = ThreadStore()
    store._redis = None
    return store


@pytest.fixture
def client(fresh_store, monkeypatch):
    """TestClient with the thread_store patched to use in-memory."""
    import main as main_module

    monkeypatch.setattr("config.settings.AUTH_DEV_BYPASS", True)
    with (
        patch.object(main_module, "thread_store", fresh_store),
        patch.object(main_module, "stream_chat_agent", _fake_stream),
        TestClient(main_module.app) as c,
    ):
        yield c


async def _fake_stream(message, thread_id, user_id=None, locale=None, timezone=None, cancel_event=None):
    yield {"event": "done", "data": None}


class TestThreadPinningStore:
    @pytest.mark.asyncio
    async def test_pin_thread(self, fresh_store):
        """Pinning a thread sets pinned=True and pinned_at > 0."""
        store = fresh_store
        await store.upsert_thread("alice", "chat:abc:t1", "Tokyo trip")
        ok = await store.update_pin_status("alice", "chat:abc:t1", True)
        assert ok is True
        thread = await store.get_thread("alice", "chat:abc:t1")
        assert thread is not None
        assert thread.pinned is True
        assert thread.pinned_at > 0

    @pytest.mark.asyncio
    async def test_unpin_thread(self, fresh_store):
        """Unpinning a thread sets pinned=False and pinned_at=0."""
        store = fresh_store
        await store.upsert_thread("alice", "chat:abc:t1", "Tokyo trip")
        await store.update_pin_status("alice", "chat:abc:t1", True)
        ok = await store.update_pin_status("alice", "chat:abc:t1", False)
        assert ok is True
        thread = await store.get_thread("alice", "chat:abc:t1")
        assert thread is not None
        assert thread.pinned is False
        assert thread.pinned_at == 0.0

    @pytest.mark.asyncio
    async def test_pinned_threads_sort_first(self, fresh_store):
        """Pinned threads appear before unpinned ones in list_threads."""
        store = fresh_store
        await store.upsert_thread("alice", "chat:abc:t1", "Tokyo trip")
        await asyncio.sleep(0.01)
        await store.upsert_thread("alice", "chat:abc:t2", "Paris trip")
        await asyncio.sleep(0.01)
        await store.upsert_thread("alice", "chat:abc:t3", "Rome trip")

        # Pin the oldest thread (t1)
        await store.update_pin_status("alice", "chat:abc:t1", True)

        threads = await store.list_threads("alice")
        assert threads[0].thread_id == "chat:abc:t1"
        assert threads[0].pinned is True
        assert threads[1].pinned is False

    @pytest.mark.asyncio
    async def test_pinned_sorted_by_pinned_at_desc(self, fresh_store):
        """Multiple pinned threads are sorted by pinned_at descending."""
        store = fresh_store
        await store.upsert_thread("alice", "chat:abc:t1", "Tokyo trip")
        await store.upsert_thread("alice", "chat:abc:t2", "Paris trip")

        # Pin t1 first, then t2
        await store.update_pin_status("alice", "chat:abc:t1", True)
        await asyncio.sleep(0.01)
        await store.update_pin_status("alice", "chat:abc:t2", True)

        threads = await store.list_threads("alice")
        # t2 was pinned more recently, should be first
        assert threads[0].thread_id == "chat:abc:t2"
        assert threads[1].thread_id == "chat:abc:t1"

    @pytest.mark.asyncio
    async def test_pin_nonexistent_returns_false(self, fresh_store):
        """Pinning a non-existent thread returns False."""
        store = fresh_store
        ok = await store.update_pin_status("alice", "chat:abc:nonexistent", True)
        assert ok is False

    @pytest.mark.asyncio
    async def test_upsert_preserves_pinned_status(self, fresh_store):
        """Upserting an existing thread preserves its pinned state."""
        store = fresh_store
        await store.upsert_thread("alice", "chat:abc:t1", "Tokyo trip")
        await store.update_pin_status("alice", "chat:abc:t1", True)

        # Simulate a new message in the thread — upsert should preserve pinned
        await store.upsert_thread("alice", "chat:abc:t1", "Tokyo trip updated")
        thread = await store.get_thread("alice", "chat:abc:t1")
        assert thread is not None
        assert thread.pinned is True
        assert thread.pinned_at > 0


class TestThreadPinningEndpoint:
    def test_patch_endpoint_pin(self, client, fresh_store):
        """PATCH /threads/{thread_id} with pinned=true pins the thread."""
        user_tag = hashlib.sha256(b"dev@localhost").hexdigest()[:12]
        thread_id = f"chat:{user_tag}:t1"
        asyncio.run(fresh_store.upsert_thread("dev@localhost", thread_id, "Tokyo trip"))

        resp = client.patch(f"/threads/{thread_id}", json={"pinned": True})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

        # Verify via GET /threads
        resp = client.get("/threads")
        data = resp.json()
        thread = next(t for t in data["threads"] if t["thread_id"] == thread_id)
        assert thread["pinned"] is True
        assert thread["pinned_at"] > 0

    def test_patch_endpoint_unpin(self, client, fresh_store):
        """PATCH /threads/{thread_id} with pinned=false unpins the thread."""
        user_tag = hashlib.sha256(b"dev@localhost").hexdigest()[:12]
        thread_id = f"chat:{user_tag}:t1"
        asyncio.run(fresh_store.upsert_thread("dev@localhost", thread_id, "Tokyo trip"))
        asyncio.run(fresh_store.update_pin_status("dev@localhost", thread_id, True))

        resp = client.patch(f"/threads/{thread_id}", json={"pinned": False})
        assert resp.status_code == 200

        # Verify via GET /threads
        resp = client.get("/threads")
        data = resp.json()
        thread = next(t for t in data["threads"] if t["thread_id"] == thread_id)
        assert thread["pinned"] is False

    def test_patch_endpoint_cross_user_403(self, client, fresh_store):
        """Patching another user's thread returns 403."""
        alice_tag = hashlib.sha256(b"alice").hexdigest()[:12]
        thread_id = f"chat:{alice_tag}:t1"
        asyncio.run(fresh_store.upsert_thread("alice", thread_id, "Alice trip"))

        resp = client.patch(f"/threads/{thread_id}", json={"pinned": True})
        assert resp.status_code == 403
