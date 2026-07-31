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

    def test_plan_401_without_api_key(
        self, client: TestClient, valid_plan_payload: dict
    ) -> None:
        resp = client.post("/plan", json=valid_plan_payload)
        assert resp.status_code == 401
        assert "API key" in resp.json()["detail"]

    def test_plan_401_with_wrong_api_key(
        self, client: TestClient, valid_plan_payload: dict
    ) -> None:
        resp = client.post(
            "/plan", json=valid_plan_payload, headers={"X-API-Key": "wrong_key"}
        )
        assert resp.status_code == 401

    def test_plan_200_with_valid_api_key(
        self, client: TestClient, valid_plan_payload: dict
    ) -> None:
        resp = client.post(
            "/plan", json=valid_plan_payload, headers={"X-API-Key": "test_secret_key"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    def test_replan_401_without_api_key(self, client: TestClient) -> None:
        resp = client.post("/replan-day", json={"bad": "data"})
        assert resp.status_code == 401

    def test_replan_401_with_wrong_api_key(self, client: TestClient) -> None:
        resp = client.post(
            "/replan-day", json={"bad": "data"}, headers={"X-API-Key": "wrong_key"}
        )
        assert resp.status_code == 401
