"""Tests for OAuth authentication flow and session management.

Uses direct session injection (create_session with DEV_USER) so no Google
credentials are needed. The mock user has user_id="dev@localhost".
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient


def _create_dev_session():
    """Create a real dev session and return the session ID."""
    from oauth import DEV_USER, create_session

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(create_session(DEV_USER))
    finally:
        loop.close()


@pytest.fixture
def client():
    import main

    with TestClient(main.app) as c:
        yield c


@pytest.fixture
def authed_client():
    """Client with a valid session cookie injected directly."""
    import main

    session_id = _create_dev_session()
    with TestClient(main.app) as c:
        c.cookies.set("voyager_session", session_id)
        c.cookies.set("voyager_csrf", "test-csrf-token")
        yield c


class TestSessionInjection:
    def test_me_returns_mock_user(self, authed_client):
        resp = authed_client.get("/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == "dev@localhost"
        assert data["display_name"] == "Dev User"


class TestUnauthenticated:
    def test_me_without_session_returns_401(self, client):
        resp = client.get("/auth/me")
        assert resp.status_code == 401

    def test_chat_stream_requires_auth(self, client):
        resp = client.post("/chat/stream", json={"message": "test"})
        assert resp.status_code == 401

    def test_list_threads_requires_auth(self, client):
        resp = client.get("/threads")
        assert resp.status_code == 401

    def test_preferences_requires_auth(self, client):
        resp = client.get("/preferences")
        assert resp.status_code == 401


class TestLogout:
    def test_logout_clears_session(self, authed_client):
        resp = authed_client.post(
            "/auth/logout",
            headers={"X-CSRF-Token": "test-csrf-token"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestThreadOwnership:
    def test_thread_ownership_enforced(self, authed_client):
        # Dev user hash is sha256("dev@localhost")[:12] — not "aaaaaabbbccc"
        resp = authed_client.get("/threads/chat:aaaaaabbbccc:fake/history")
        assert resp.status_code == 403


class TestSessionStoreUnavailable:
    """Improvement I2: store outage must yield 503, not 401 logout."""

    @pytest.mark.asyncio
    async def test_get_session_raises_when_all_stores_fail(self, monkeypatch):
        import oauth

        async def _failing_redis():
            r = type("R", (), {})()
            async def _get(k):
                from redis.exceptions import RedisError
                raise RedisError("down")
            r.get = _get
            async def _close():
                pass
            r.aclose = _close
            return r

        async def _failing_db():
            db = type("DB", (), {})()
            async def _execute(*a, **k):
                raise RuntimeError("db down")
            db.execute = _execute
            return db

        monkeypatch.setattr(oauth, "_get_redis", _failing_redis)
        monkeypatch.setattr(oauth, "get_sqlite_connection", _failing_db)
        monkeypatch.setattr(oauth, "_mem_sessions", {})

        with pytest.raises(oauth.SessionStoreUnavailable):
            await oauth.get_session("nonexistent")

    @pytest.mark.asyncio
    async def test_get_session_none_when_stores_healthy(self, monkeypatch):
        import oauth

        async def _no_redis():
            return None

        async def _no_db():
            return None

        monkeypatch.setattr(oauth, "_get_redis", _no_redis)
        monkeypatch.setattr(oauth, "get_sqlite_connection", _no_db)
        monkeypatch.setattr(oauth, "_mem_sessions", {})

        assert await oauth.get_session("nonexistent") is None

    def test_me_returns_503_on_store_outage(self, monkeypatch):
        import main
        import oauth

        async def _failing(session_id):
            raise oauth.SessionStoreUnavailable("all stores down")

        monkeypatch.setattr(oauth, "get_session", _failing)
        session_id = _create_dev_session()
        with TestClient(main.app) as c:
            c.cookies.set("voyager_session", session_id)
            resp = c.get("/auth/me")
        assert resp.status_code == 503
        assert resp.headers.get("Retry-After") == "2"
