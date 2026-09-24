"""Tests for itinerary editing: endpoint validation, SSE streaming, cancel, and error handling."""

from __future__ import annotations

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def _create_dev_session():
    """Create a real dev session and return the session ID."""
    import asyncio
    from oauth import DEV_USER, create_session
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(create_session(DEV_USER))
    finally:
        loop.close()


@pytest.fixture
def client(monkeypatch):
    """TestClient with session injection and mocked thread_store."""
    import main as main_module

    mock_thread_store = MagicMock()
    mock_thread_store.list_threads = AsyncMock(return_value=[])
    mock_thread_store.count_threads = AsyncMock(return_value=0)
    mock_thread_store.update_status = AsyncMock()
    mock_thread_store.upsert_thread = AsyncMock()

    session_id = _create_dev_session()

    with (
        patch.object(main_module, "thread_store", mock_thread_store),
        TestClient(main_module.app) as c,
    ):
        c.cookies.set("voyager_session", session_id)
        c.cookies.set("voyager_csrf", "test-csrf-token")
        yield c


def _scoped_thread_id(raw: str = "test-thread") -> str:
    user_id = "dev@localhost"
    user_tag = hashlib.sha256(user_id.encode()).hexdigest()[:12]
    return f"chat:{user_tag}:{raw}"


SAMPLE_ITINERARY = {
    "destination": "Tokyo",
    "total_days": 2,
    "estimated_total_cost_usd": 100,
    "budget_status": "within",
    "visa_note": "No visa",
    "best_season_note": "Spring",
    "days": [
        {
            "day": 1,
            "theme": "Arrival",
            "morning": {"activity": "Check-in", "location": "Hotel", "cost_usd": 20, "duration": "1h"},
            "afternoon": {"activity": "Park", "location": "Park", "cost_usd": 10, "duration": "2h"},
            "evening": {"activity": "Dinner", "location": "Restaurant", "cost_usd": 30, "duration": "1h"},
            "transport": "Train",
            "accommodation": "Hotel",
            "daily_cost_usd": 60,
            "tips": ["Tip 1"],
        },
        {
            "day": 2,
            "theme": "Temples",
            "morning": {"activity": "Temple", "location": "Asakusa", "cost_usd": 0, "duration": "2h"},
            "afternoon": {"activity": "Shopping", "location": "Shibuya", "cost_usd": 20, "duration": "3h"},
            "evening": {"activity": "Bar", "location": "Shinjuku", "cost_usd": 20, "duration": "2h"},
            "transport": "Subway",
            "accommodation": "Hotel",
            "daily_cost_usd": 40,
            "tips": ["Tip 2"],
        },
    ],
    "warnings": [],
    "packing_essentials": [],
}


class TestEditItineraryEndpoint:
    def test_requires_itinerary(self, client):
        scoped = _scoped_thread_id("edit-itin-test")
        resp = client.post(
            f"/chat/{scoped}/edit-itinerary",
            json={},
        )
        assert resp.status_code == 400

    def test_rejects_non_dict_itinerary(self, client):
        scoped = _scoped_thread_id("edit-itin-test")
        resp = client.post(
            f"/chat/{scoped}/edit-itinerary",
            json={"itinerary": "not a dict"},
        )
        assert resp.status_code == 400

    def test_returns_sse_stream(self, client, monkeypatch):
        """Edit itinerary endpoint returns a valid SSE stream."""
        import main as main_module

        async def fake_edit_itinerary(*, thread_id, modified_itinerary, user_id, locale, timezone, cancel_event, currency=None):
            yield {"event": "on_chat_model_stream", "data": {"chunk": "Hi"}}
            yield {"event": "done", "data": None}

        monkeypatch.setattr(main_module, "edit_itinerary_agent", fake_edit_itinerary)

        scoped = _scoped_thread_id("edit-itin-stream")
        with client.stream(
            "POST", f"/chat/{scoped}/edit-itinerary",
            json={"itinerary": SAMPLE_ITINERARY},
        ) as r:
            assert r.status_code == 200
            lines = list(r.iter_lines())
            data_lines = [l for l in lines if l.startswith("data: ")]
            assert len(data_lines) >= 2

    def test_cancel_works(self, client, monkeypatch):
        """Cancel event is respected during itinerary edit."""
        import main as main_module

        async def fake_edit_itinerary(*, thread_id, modified_itinerary, user_id, locale, timezone, cancel_event, currency=None):
            yield {"event": "on_chat_model_stream", "data": {"chunk": "partial"}}
            if cancel_event:
                cancel_event.set()
            yield {"event": "cancelled", "data": None}

        monkeypatch.setattr(main_module, "edit_itinerary_agent", fake_edit_itinerary)

        scoped = _scoped_thread_id("edit-itin-cancel")
        with client.stream(
            "POST", f"/chat/{scoped}/edit-itinerary",
            json={"itinerary": SAMPLE_ITINERARY},
        ) as r:
            assert r.status_code == 200
            lines = list(r.iter_lines())
            events = [l for l in lines if l.startswith("event: ")]
            assert any("cancelled" in e for e in events)

    def test_error_yields_error_event(self, client, monkeypatch):
        """If edit_itinerary_agent raises, an error SSE event is emitted."""
        import main as main_module

        async def failing_edit_itinerary(*, thread_id, modified_itinerary, user_id, locale, timezone, cancel_event, currency=None):
            raise RuntimeError("boom")

        monkeypatch.setattr(main_module, "edit_itinerary_agent", failing_edit_itinerary)

        scoped = _scoped_thread_id("edit-itin-error")
        with client.stream(
            "POST", f"/chat/{scoped}/edit-itinerary",
            json={"itinerary": SAMPLE_ITINERARY},
        ) as r:
            assert r.status_code == 200
            lines = list(r.iter_lines())
            events = [l for l in lines if l.startswith("event: ")]
            assert any("error" in e for e in events)

    def test_passes_itinerary_to_agent(self, client, monkeypatch):
        """The modified itinerary is passed to edit_itinerary_agent."""
        import main as main_module

        captured = []

        async def fake_edit_itinerary(*, thread_id, modified_itinerary, user_id, locale, timezone, cancel_event, currency=None):
            captured.append(modified_itinerary)
            yield {"event": "done", "data": None}

        monkeypatch.setattr(main_module, "edit_itinerary_agent", fake_edit_itinerary)

        scoped = _scoped_thread_id("edit-itin-pass")
        with client.stream(
            "POST", f"/chat/{scoped}/edit-itinerary",
            json={"itinerary": SAMPLE_ITINERARY},
        ) as r:
            assert r.status_code == 200
            list(r.iter_lines())

        assert captured
        assert captured[0]["destination"] == "Tokyo"

    def test_scopes_thread_id_per_user(self, client, monkeypatch):
        """Cross-user thread_id gets re-scoped to the current user."""
        import main as main_module

        captured_thread_id = []

        async def fake_edit_itinerary(*, thread_id, modified_itinerary, user_id, locale, timezone, cancel_event, currency=None):
            captured_thread_id.append(thread_id)
            yield {"event": "done", "data": None}

        monkeypatch.setattr(main_module, "edit_itinerary_agent", fake_edit_itinerary)

        alice_tag = hashlib.sha256(b"alice").hexdigest()[:12]
        alice_thread = f"chat:{alice_tag}:some-thread"

        with client.stream(
            "POST", f"/chat/{alice_thread}/edit-itinerary",
            json={"itinerary": SAMPLE_ITINERARY},
        ) as r:
            assert r.status_code == 200
            list(r.iter_lines())

        dev_tag = hashlib.sha256(b"dev@localhost").hexdigest()[:12]
        assert captured_thread_id
        assert captured_thread_id[0].startswith(f"chat:{dev_tag}:")
