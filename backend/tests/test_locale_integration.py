"""Integration tests for locale handling in the chat_stream endpoint.

Verifies locale flows through the full request → agent → prompt chain:
- Locale in request body
- Locale from Accept-Language header
- Priority: body > header
- Fallback when no locale provided
- Unsupported locale passed through
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient


def _make_capturing_stream(captured: list):
    """Return an async generator that captures the locale kwarg."""

    async def _stream(*, message, thread_id, user_id, locale=None):
        captured.append(locale)
        yield {"event": "thread_id", "data": {"thread_id": thread_id}}
        yield {"event": "done", "data": None}

    return _stream


@pytest.fixture
def client(monkeypatch):
    """TestClient with auth bypass and mocked stream_chat_agent."""
    import main as main_module

    monkeypatch.setattr("config.settings.AUTH_DEV_BYPASS", True)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-for-locale-tests")

    async def _fake_stream(*, message, thread_id, user_id, locale=None):
        yield {"event": "thread_id", "data": {"thread_id": thread_id}}
        yield {"event": "done", "data": None}

    monkeypatch.setattr(main_module, "stream_chat_agent", _fake_stream)

    with TestClient(main_module.app) as c:
        yield c


def _consume(response):
    """Consume all SSE events from a streamed response."""
    for line in response.iter_lines():
        if line.startswith("data: "):
            json.loads(line[6:])


class TestLocaleIntegration:
    """Tests that locale is correctly extracted and passed to stream_chat_agent."""

    def test_locale_in_request_body(self, client, monkeypatch):
        """Locale in the request body is passed to stream_chat_agent."""
        import main as main_module

        captured: list = []
        monkeypatch.setattr(
            main_module, "stream_chat_agent", _make_capturing_stream(captured)
        )

        with client.stream(
            "POST",
            "/chat/stream",
            json={"message": "Plan a trip to Paris", "locale": "fr"},
        ) as r:
            assert r.status_code == 200
            _consume(r)

        assert captured == ["fr"]

    def test_locale_from_accept_language_header(self, client, monkeypatch):
        """Locale is extracted from Accept-Language header when not in body."""
        import main as main_module

        captured: list = []
        monkeypatch.setattr(
            main_module, "stream_chat_agent", _make_capturing_stream(captured)
        )

        with client.stream(
            "POST",
            "/chat/stream",
            json={"message": "Plan a trip to Tokyo"},
            headers={"Accept-Language": "es-ES,es;q=0.9"},
        ) as r:
            assert r.status_code == 200
            _consume(r)

        assert captured == ["es"]

    def test_locale_body_takes_priority_over_header(self, client, monkeypatch):
        """Locale in body takes priority over Accept-Language header."""
        import main as main_module

        captured: list = []
        monkeypatch.setattr(
            main_module, "stream_chat_agent", _make_capturing_stream(captured)
        )

        with client.stream(
            "POST",
            "/chat/stream",
            json={"message": "Plan a trip", "locale": "ja"},
            headers={"Accept-Language": "fr-FR"},
        ) as r:
            assert r.status_code == 200
            _consume(r)

        assert captured == ["ja"]

    def test_no_locale_defaults_to_none(self, client, monkeypatch):
        """When no locale is provided in body or header, locale is None."""
        import main as main_module

        captured: list = []
        monkeypatch.setattr(
            main_module, "stream_chat_agent", _make_capturing_stream(captured)
        )

        with client.stream(
            "POST",
            "/chat/stream",
            json={"message": "Plan a trip"},
        ) as r:
            assert r.status_code == 200
            _consume(r)

        assert captured == [None]

    def test_unsupported_locale_in_header_falls_back(self, client, monkeypatch):
        """Unsupported locale in Accept-Language falls back to None."""
        import main as main_module

        captured: list = []
        monkeypatch.setattr(
            main_module, "stream_chat_agent", _make_capturing_stream(captured)
        )

        with client.stream(
            "POST",
            "/chat/stream",
            json={"message": "Plan a trip"},
            headers={"Accept-Language": "zh-CN,zh;q=0.9"},
        ) as r:
            assert r.status_code == 200
            _consume(r)

        assert captured == [None]
