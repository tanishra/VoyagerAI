"""Tests for GET/PUT /preferences endpoints and memory integration.

Does not require GEMINI_API_KEY or Redis — uses a patched InMemoryStore.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from langgraph.store.memory import InMemoryStore


@pytest.fixture
def fresh_store():
    return InMemoryStore()


@pytest.fixture
def client(fresh_store):
    import main
    with patch.object(main, "get_redis_file_store", return_value=fresh_store), TestClient(main.app) as c:
        yield c


class TestPreferences:
    def test_get_preferences_empty(self, client):
        resp = client.get("/preferences", headers={"X-User-Id": "alice"})
        assert resp.status_code == 200
        assert resp.text == ""

    def test_put_and_get_preferences(self, client, fresh_store):
        content = "style: relaxed\nbudget: mid_range"
        put_resp = client.put(
            "/preferences",
            headers={"X-User-Id": "alice"},
            content=content,
        )
        assert put_resp.status_code == 200

        get_resp = client.get("/preferences", headers={"X-User-Id": "alice"})
        assert get_resp.status_code == 200
        assert get_resp.text == content

    def test_namespace_isolation(self, client, fresh_store):
        client.put(
            "/preferences",
            headers={"X-User-Id": "alice"},
            content="alice_data",
        )
        client.put(
            "/preferences",
            headers={"X-User-Id": "bob"},
            content="bob_data",
        )

        alice = client.get("/preferences", headers={"X-User-Id": "alice"})
        assert alice.text == "alice_data"

        bob = client.get("/preferences", headers={"X-User-Id": "bob"})
        assert bob.text == "bob_data"

    def test_fallback_to_query_param(self, client, fresh_store):
        client.put(
            "/preferences?user_id=charlie",
            content="charlie_data",
        )
        resp = client.get("/preferences?user_id=charlie")
        assert resp.text == "charlie_data"

    def test_key_schema_consistency(self, client, fresh_store):
        client.put(
            "/preferences",
            headers={"X-User-Id": "alice"},
            content="test_data",
        )

        item = fresh_store.get(("alice",), "/preferences.md")
        assert item is not None
        assert item.value["content"] == "test_data"
