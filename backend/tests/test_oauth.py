"""Tests for OAuth authentication flow and session management.

Uses AUTH_DEV_BYPASS=1 so no Google credentials are needed.
The dev bypass returns a mock user with user_id="dev@localhost".
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr("config.settings.AUTH_DEV_BYPASS", True)
    import main
    with TestClient(main.app) as c:
        yield c


@pytest.fixture
def authed_client(monkeypatch):
    """Client with a valid dev-bypass session cookie."""
    monkeypatch.setattr("config.settings.AUTH_DEV_BYPASS", True)
    import main
    with TestClient(main.app) as c:
        c.get("/auth/login", follow_redirects=False)
        yield c


class TestDevBypass:
    def test_dev_bypass_login_sets_cookie(self, client):
        resp = client.get("/auth/login", follow_redirects=False)
        assert resp.status_code in (302, 307)
        assert "voyager_session" in resp.cookies

    def test_dev_bypass_me_returns_mock_user(self, authed_client):
        resp = authed_client.get("/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == "dev@localhost"
        assert data["display_name"] == "Dev User"


class TestUnauthenticated:
    @pytest.fixture
    def strict_client(self, monkeypatch):
        monkeypatch.setattr("config.settings.AUTH_DEV_BYPASS", False)
        import main
        with TestClient(main.app) as c:
            yield c

    def test_me_without_session_returns_401(self, strict_client):
        resp = strict_client.get("/auth/me")
        assert resp.status_code == 401

    def test_chat_stream_requires_auth(self, strict_client):
        resp = strict_client.post("/chat/stream", json={"message": "test"})
        assert resp.status_code == 401

    def test_list_threads_requires_auth(self, strict_client):
        resp = strict_client.get("/threads")
        assert resp.status_code == 401

    def test_preferences_requires_auth(self, strict_client):
        resp = strict_client.get("/preferences")
        assert resp.status_code == 401


class TestLogout:
    def test_logout_clears_session(self, authed_client):
        resp = authed_client.post("/auth/logout")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestThreadOwnership:
    def test_thread_ownership_enforced(self, authed_client):
        # Dev user hash is sha256("dev@localhost")[:12] — not "aaaaaabbbccc"
        resp = authed_client.get("/threads/chat:aaaaaabbbccc:fake/history")
        assert resp.status_code == 403
