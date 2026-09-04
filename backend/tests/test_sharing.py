"""Tests for share & export endpoints.

Uses in-memory ShareStore (no Redis required) and TestClient with mocked
agent state — same pattern as test_threads.py.
"""

from __future__ import annotations

import hashlib
import time
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from share_store import ShareStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fresh_share_store():
    """A ShareStore with no Redis connection — uses in-memory fallback."""
    store = ShareStore()
    store._redis = None
    return store


def _make_itinerary(destination="Paris, France"):
    return {
        "destination": destination,
        "total_days": 3,
        "estimated_total_cost_usd": 1200,
        "budget_status": "within",
        "visa_note": "Schengen visa required",
        "best_season_note": "April-June",
        "days": [
            {
                "day": 1,
                "theme": "Arrival & Eiffel Tower",
                "morning": {"activity": "Check-in", "location": "Hotel", "cost_usd": 0, "duration": "1h"},
                "afternoon": {"activity": "Eiffel Tower", "location": "Champ de Mars", "cost_usd": 30, "duration": "3h"},
                "evening": {"activity": "Seine cruise", "location": "Seine", "cost_usd": 20, "duration": "2h"},
                "transport": "Metro",
                "accommodation": "3-star hotel",
                "daily_cost_usd": 400,
                "tips": ["Book Eiffel Tower tickets online"],
            },
        ],
        "warnings": ["Pickpockets near tourist spots"],
        "packing_essentials": ["Comfortable shoes", "Rain jacket"],
    }


def _make_scoped_thread_id(user_id="dev@localhost"):
    tag = hashlib.sha256(user_id.encode()).hexdigest()[:12]
    return f"chat:{tag}:test-thread-123"


@pytest.fixture
def client(fresh_share_store, monkeypatch):
    """TestClient with share_store patched and dev bypass enabled."""
    import main as main_module

    monkeypatch.setattr("config.settings.AUTH_DEV_BYPASS", True)

    # Mock _get_latest_itinerary to return a fake itinerary
    fake_itinerary = _make_itinerary()
    mock_get_itinerary = AsyncMock(return_value=fake_itinerary)

    with (
        patch.object(main_module, "share_store", fresh_share_store),
        patch.object(main_module, "_get_latest_itinerary", mock_get_itinerary),
        TestClient(main_module.app) as c,
    ):
        yield c


@pytest.fixture
def client_no_itinerary(fresh_share_store, monkeypatch):
    """TestClient where _get_latest_itinerary returns None (no itinerary)."""
    import main as main_module

    monkeypatch.setattr("config.settings.AUTH_DEV_BYPASS", True)
    mock_get_itinerary = AsyncMock(return_value=None)

    with (
        patch.object(main_module, "share_store", fresh_share_store),
        patch.object(main_module, "_get_latest_itinerary", mock_get_itinerary),
        TestClient(main_module.app) as c,
    ):
        yield c

# ---------------------------------------------------------------------------
# ShareStore unit tests
# ---------------------------------------------------------------------------


class TestShareStore:
    @pytest.mark.asyncio
    async def test_create_and_get_share(self, fresh_share_store):
        store = fresh_share_store
        import json

        itinerary_json = json.dumps(_make_itinerary())
        token, expires_at = await store.create_share(
            "user1", "chat:abc123:thread1", itinerary_json, "Paris, France",
        )
        assert token
        assert expires_at > time.time()

        data = await store.get_share(token)
        assert data is not None
        assert data["destination"] == "Paris, France"
        assert "itinerary_json" in data

    @pytest.mark.asyncio
    async def test_get_expired_share(self, fresh_share_store):
        store = fresh_share_store
        import json

        itinerary_json = json.dumps(_make_itinerary())
        token, _ = await store.create_share(
            "user1", "chat:abc123:thread1", itinerary_json, "Paris",
        )
        # Fast-forward expiry
        store._mem["user1"][token]["expires_at"] = time.time() - 1
        data = await store.get_share(token)
        assert data is None

    @pytest.mark.asyncio
    async def test_revoke_share(self, fresh_share_store):
        store = fresh_share_store
        import json

        itinerary_json = json.dumps(_make_itinerary())
        token, _ = await store.create_share(
            "user1", "chat:abc123:thread1", itinerary_json, "Paris",
        )
        revoked = await store.revoke_share("user1", token)
        assert revoked is True
        data = await store.get_share(token)
        assert data is None

    @pytest.mark.asyncio
    async def test_revoke_nonexistent(self, fresh_share_store):
        store = fresh_share_store
        revoked = await store.revoke_share("user1", "nonexistent-token")
        assert revoked is False

    @pytest.mark.asyncio
    async def test_list_shares(self, fresh_share_store):
        store = fresh_share_store
        import json

        itinerary_json = json.dumps(_make_itinerary())
        await store.create_share("user1", "thread1", itinerary_json, "Paris")
        await store.create_share("user1", "thread2", itinerary_json, "Tokyo")
        shares = await store.list_shares("user1")
        assert len(shares) == 2
        destinations = {s.destination for s in shares}
        assert destinations == {"Paris", "Tokyo"}

    @pytest.mark.asyncio
    async def test_list_shares_empty(self, fresh_share_store):
        store = fresh_share_store
        shares = await store.list_shares("user1")
        assert shares == []

    @pytest.mark.asyncio
    async def test_revoke_other_user_share(self, fresh_share_store):
        store = fresh_share_store
        import json

        itinerary_json = json.dumps(_make_itinerary())
        token, _ = await store.create_share(
            "user1", "thread1", itinerary_json, "Paris",
        )
        # User2 cannot revoke user1's share
        revoked = await store.revoke_share("user2", token)
        assert revoked is False
        # Share still exists
        data = await store.get_share(token)
        assert data is not None


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------


class TestShareEndpoints:
    def test_create_share_link(self, client):
        thread_id = _make_scoped_thread_id()
        resp = client.post(f"/share/{thread_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "share_url" in data
        assert "expires_at" in data
        assert data["destination"] == "Paris, France"
        assert "/share/" in data["share_url"]

    def test_create_share_no_itinerary(self, client_no_itinerary):
        thread_id = _make_scoped_thread_id()
        resp = client_no_itinerary.post(f"/share/{thread_id}")
        assert resp.status_code == 404

    def test_get_shared_itinerary(self, client):
        thread_id = _make_scoped_thread_id()
        # Create a share
        resp = client.post(f"/share/{thread_id}")
        assert resp.status_code == 200
        share_url = resp.json()["share_url"]
        token = share_url.split("/share/")[-1]

        # Get the shared itinerary (public, no auth)
        resp = client.get(f"/share/{token}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["itinerary"]["destination"] == "Paris, France"
        assert data["destination"] == "Paris, France"

    def test_get_expired_share(self, client, fresh_share_store):
        thread_id = _make_scoped_thread_id()
        resp = client.post(f"/share/{thread_id}")
        token = resp.json()["share_url"].split("/share/")[-1]

        # Expire it
        fresh_share_store._mem["dev@localhost"][token]["expires_at"] = time.time() - 1
        resp = client.get(f"/share/{token}")
        assert resp.status_code == 404

    def test_revoke_share(self, client):
        thread_id = _make_scoped_thread_id()
        resp = client.post(f"/share/{thread_id}")
        token = resp.json()["share_url"].split("/share/")[-1]

        resp = client.delete(f"/share/{token}")
        assert resp.status_code == 200

        # Verify it's gone
        resp = client.get(f"/share/{token}")
        assert resp.status_code == 404

    def test_list_shares(self, client):
        thread_id = _make_scoped_thread_id()
        client.post(f"/share/{thread_id}")
        client.post(f"/share/{thread_id}")

        resp = client.get("/shares")
        assert resp.status_code == 200
        shares = resp.json()
        assert len(shares) == 2
        assert "share_url" in shares[0]
        assert "destination" in shares[0]


class TestExportEndpoints:
    def test_export_json(self, client):
        thread_id = _make_scoped_thread_id()
        resp = client.get(f"/export/{thread_id}?fmt=json")
        assert resp.status_code == 200
        data = resp.json()
        assert data["destination"] == "Paris, France"
        assert "days" in data

    def test_export_markdown(self, client):
        thread_id = _make_scoped_thread_id()
        resp = client.get(f"/export/{thread_id}?fmt=markdown")
        assert resp.status_code == 200
        text = resp.text
        assert "# Paris, France" in text
        assert "Day 1" in text

    def test_export_no_itinerary(self, client_no_itinerary):
        thread_id = _make_scoped_thread_id()
        resp = client_no_itinerary.get(f"/export/{thread_id}")
        assert resp.status_code == 404

    def test_export_ical(self, client):
        thread_id = _make_scoped_thread_id()
        resp = client.get(f"/export/{thread_id}?fmt=ical")
        assert resp.status_code == 200
        assert "text/calendar" in resp.headers.get("content-type", "")
        body = resp.text
        assert body.startswith("BEGIN:VCALENDAR")
        assert "BEGIN:VEVENT" in body
        assert "END:VCALENDAR" in body
        assert "Eiffel Tower" in body or "Morning Activity" in body or "Check-in" in body
