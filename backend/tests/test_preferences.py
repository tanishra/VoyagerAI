"""Tests for GET/PUT /preferences endpoints and memory integration.

Does not require GEMINI_API_KEY or Redis — uses a patched InMemoryStore.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from langgraph.store.memory import InMemoryStore

import main


@pytest.fixture
def fresh_store():
    return InMemoryStore()


@pytest.fixture
def client(fresh_store, monkeypatch):
    monkeypatch.setattr("config.settings.AUTH_DEV_BYPASS", True)
    with patch.object(main, "get_redis_file_store", return_value=fresh_store), TestClient(main.app) as c:
        # Establish dev-bypass session so get_current_user works
        c.get("/auth/login", follow_redirects=False)
        yield c


class TestPreferences:
    def test_get_preferences_empty(self, client):
        resp = client.get("/preferences")
        assert resp.status_code == 200
        assert resp.text == ""

    def test_put_and_get_preferences(self, client, fresh_store):
        content = "style: relaxed\nbudget: mid_range"
        put_resp = client.put(
            "/preferences",
            content=content,
        )
        assert put_resp.status_code == 200

        get_resp = client.get("/preferences")
        assert get_resp.status_code == 200
        assert get_resp.text == content

    def test_key_schema_consistency(self, client, fresh_store):
        client.put(
            "/preferences",
            content="test_data",
        )

        # Dev user_id is "dev@localhost"
        item = fresh_store.get(("dev@localhost",), "/preferences.md")
        assert item is not None
        assert item.value["content"] == "test_data"
