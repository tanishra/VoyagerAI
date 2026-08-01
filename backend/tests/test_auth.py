"""Tests for authentication and authorization.

All tests require GEMINI_API_KEY to be set (needed at app import time).
These tests do NOT call Gemini — they only verify auth boundaries.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


class TestAuth:
    """Test that API key authentication is enforced correctly."""

    @pytest.fixture(autouse=True)
    def _enable_production_auth(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Override auth module variables so auth is enforced for every test."""
        import auth
        monkeypatch.setattr(auth, "AUTH_MODE", "production")
        monkeypatch.setattr(auth, "API_AUTH_KEY", "test_secret_key")

    def test_health_no_auth_required(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_chat_stream_401_without_api_key(self, client: TestClient) -> None:
        resp = client.post("/chat/stream", json={"message": "hello"})
        assert resp.status_code == 401
        assert "API key" in resp.json()["detail"]

    def test_chat_stream_401_with_wrong_api_key(self, client: TestClient) -> None:
        resp = client.post(
            "/chat/stream", json={"message": "hello"}, headers={"X-API-Key": "wrong_key"}
        )
        assert resp.status_code == 401
