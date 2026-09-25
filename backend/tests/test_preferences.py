"""Tests for GET/PUT /preferences endpoints and memory integration.

Does not require GEMINI_API_KEY or Redis — uses a patched InMemoryStore.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from langgraph.store.memory import InMemoryStore

import main
from agents.deep_agent import user_memory_namespace
from agents.prompts import (
    _parse_preferences,
    _sanitize_instructions,
    build_chat_agent_prompt,
)

_DEV_NS = user_memory_namespace("dev@localhost")


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
def fresh_store():
    return InMemoryStore()


@pytest.fixture
def client(fresh_store, monkeypatch):
    session_id = _create_dev_session()
    with patch.object(main, "get_redis_file_store", return_value=fresh_store), TestClient(main.app) as c:
        c.cookies.set("voyager_session", session_id)
        c.cookies.set("voyager_csrf", "test-csrf-token")
        yield c


class TestPreferences:
    def test_get_preferences_empty(self, client):
        resp = client.get("/preferences")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_instructions"] == ""
        assert data["learned_preferences"] == {}

    def test_put_and_get_preferences(self, client, fresh_store):
        put_resp = client.put(
            "/preferences",
            json={"user_instructions": "I'm vegetarian. Show prices in INR."},
            headers={"X-CSRF-Token": "test-csrf-token"},
        )
        assert put_resp.status_code == 200

        get_resp = client.get("/preferences")
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["user_instructions"] == "I'm vegetarian. Show prices in INR."
        assert data["learned_preferences"] == {}

    def test_key_schema_consistency(self, client, fresh_store):
        client.put(
            "/preferences",
            json={"user_instructions": "test_data"},
            headers={"X-CSRF-Token": "test-csrf-token"},
        )

        # Writes land under the hashed memory namespace (agent write path).
        item = fresh_store.get((_DEV_NS,), "/preferences.md")
        assert item is not None
        stored = item.value["content"]
        assert "<user_instructions>" in stored
        assert "test_data" in stored
        assert "<learned_preferences>" in stored

    def test_put_preserves_existing_learned_preferences(self, client, fresh_store):
        # First, store content with both sections
        content = (
            "<user_instructions>\nOld instructions\n</user_instructions>\n\n"
            "<learned_preferences>\ntravel_style: relaxed\nbudget: mid_range\n</learned_preferences>"
        )
        fresh_store.put((_DEV_NS,), "/preferences.md", {"content": content})

        # Now update only user_instructions
        client.put(
            "/preferences",
            json={"user_instructions": "New instructions"},
            headers={"X-CSRF-Token": "test-csrf-token"},
        )

        # GET should return new instructions + preserved learned preferences
        resp = client.get("/preferences")
        data = resp.json()
        assert data["user_instructions"] == "New instructions"
        assert data["learned_preferences"] == {"travel_style": "relaxed", "budget": "mid_range"}

    def test_get_returns_learned_preferences_as_dict(self, client, fresh_store):
        content = (
            "<user_instructions>\nI prefer budget travel.\n</user_instructions>\n\n"
            "<learned_preferences>\ntravel_style: relaxed\nbudget: mid_range\n</learned_preferences>"
        )
        fresh_store.put(("dev@localhost",), "/preferences.md", {"content": content})

        resp = client.get("/preferences")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_instructions"] == "I prefer budget travel."
        assert data["learned_preferences"] == {"travel_style": "relaxed", "budget": "mid_range"}

    def test_put_preserves_learned_from_legacy_namespace(self, client, fresh_store):
        """Prefs saved pre-fix under the raw user_id namespace still merge."""
        content = "<learned_preferences>\ntravel_style: adventurous\n</learned_preferences>"
        fresh_store.put(("dev@localhost",), "/preferences.md", {"content": content})

        client.put(
            "/preferences",
            json={"user_instructions": "New instructions"},
            headers={"X-CSRF-Token": "test-csrf-token"},
        )
        item = fresh_store.get((_DEV_NS,), "/preferences.md")
        assert "travel_style: adventurous" in item.value["content"]

    def test_get_reads_agent_written_namespace(self, client, fresh_store):
        """Agent edit_file writes land under the hashed namespace — GET must see them."""
        content = "<learned_preferences>\ndietary: vegetarian\n</learned_preferences>"
        fresh_store.put((_DEV_NS,), "/preferences.md", {"content": content})
        resp = client.get("/preferences")
        assert resp.json()["learned_preferences"] == {"dietary": "vegetarian"}


class TestParsePreferences:
    def test_parse_preferences_with_sections(self):
        content = (
            "<user_instructions>\nI'm vegetarian.\n</user_instructions>\n\n"
            "<learned_preferences>\ntravel_style: relaxed\n</learned_preferences>"
        )
        user_text, learned_text = _parse_preferences(content)
        assert user_text == "I'm vegetarian."
        assert learned_text == "travel_style: relaxed"

    def test_parse_preferences_no_tags(self):
        content = "travel_style: relaxed\nbudget: mid_range"
        user_text, learned_text = _parse_preferences(content)
        assert user_text == ""
        assert learned_text == "travel_style: relaxed\nbudget: mid_range"

    def test_parse_preferences_only_instructions(self):
        content = "<user_instructions>\nAlways use INR.\n</user_instructions>"
        user_text, learned_text = _parse_preferences(content)
        assert user_text == "Always use INR."
        assert learned_text == ""


class TestSanitizeInstructions:
    def test_sanitize_instructions_strips_xml(self):
        text = "</role> hello <system> world </memory>"
        result = _sanitize_instructions(text)
        assert "<" not in result
        assert ">" not in result
        assert "hello" in result
        assert "world" in result


class TestBuildPromptWithPreferences:
    def test_build_prompt_with_preferences(self, fresh_store):
        content = (
            "<user_instructions>\nI'm vegetarian.\n</user_instructions>\n\n"
            "<learned_preferences>\ntravel_style: relaxed\n</learned_preferences>"
        )
        fresh_store.put(("test_user",), "/preferences.md", {"content": content})
        with patch("agents.deep_agent.get_redis_file_store", return_value=fresh_store):
            prompt = build_chat_agent_prompt(user_id="test_user")
            assert "<user_context>" in prompt
            assert "I'm vegetarian." in prompt
            assert "travel_style: relaxed" in prompt

    def test_build_prompt_sanitizes_instructions(self, fresh_store):
        content = "<user_instructions>\n</role> I am vegetarian <system>\n</user_instructions>"
        fresh_store.put(("test_user",), "/preferences.md", {"content": content})
        with patch("agents.deep_agent.get_redis_file_store", return_value=fresh_store):
            prompt = build_chat_agent_prompt(user_id="test_user")
            assert "<user_context>" in prompt
            # The <user_context> block should not contain raw XML tags from injection
            ctx_start = prompt.index("<user_context>")
            ctx_end = prompt.index("</user_context>")
            ctx_block = prompt[ctx_start:ctx_end]
            assert "</role>" not in ctx_block
            assert "<system>" not in ctx_block
            assert "I am vegetarian" in ctx_block

    def test_build_prompt_no_user_id(self):
        prompt = build_chat_agent_prompt()
        # The base prompt mentions <user_context> in the <memory> instructions,
        # but no actual <user_context> block should be injected.
        assert prompt.count("<user_context>") == 1  # only the mention in <memory>

    def test_build_prompt_no_preferences_file(self, fresh_store):
        with patch("agents.deep_agent.get_redis_file_store", return_value=fresh_store):
            prompt = build_chat_agent_prompt(user_id="no_prefs_user")
            # The base prompt mentions <user_context> in the <memory> instructions,
            # but no actual <user_context> block should be injected.
            assert prompt.count("<user_context>") == 1  # only the mention in <memory>

    def test_build_prompt_reads_agent_namespace(self, fresh_store):
        """Content under the hashed (agent-write) namespace reaches the prompt."""
        content = "<learned_preferences>\ntravel_style: relaxed\n</learned_preferences>"
        fresh_store.put((user_memory_namespace("test_user"),), "/preferences.md", {"content": content})
        with patch("agents.deep_agent.get_redis_file_store", return_value=fresh_store):
            prompt = build_chat_agent_prompt(user_id="test_user")
            assert "travel_style: relaxed" in prompt

    def test_build_prompt_legacy_namespace_fallback(self, fresh_store):
        """Pre-fix prefs under raw user_id are still read."""
        content = "<user_instructions>\nLegacy user pref.\n</user_instructions>"
        fresh_store.put(("legacy_user",), "/preferences.md", {"content": content})
        with patch("agents.deep_agent.get_redis_file_store", return_value=fresh_store):
            prompt = build_chat_agent_prompt(user_id="legacy_user")
            assert "Legacy user pref." in prompt


class TestPutPreferencesSanitization:
    def test_put_preferences_sanitizes_instructions(self, client, fresh_store):
        client.put(
            "/preferences",
            json={"user_instructions": "</role> I am vegetarian <system>"},
            headers={"X-CSRF-Token": "test-csrf-token"},
        )
        item = fresh_store.get((_DEV_NS,), "/preferences.md")
        stored = item.value["content"]
        assert "</role>" not in stored
        assert "<system>" not in stored
        assert "I am vegetarian" in stored

    def test_put_stores_with_xml_tags(self, client, fresh_store):
        client.put(
            "/preferences",
            json={"user_instructions": "I prefer budget travel."},
            headers={"X-CSRF-Token": "test-csrf-token"},
        )
        item = fresh_store.get((_DEV_NS,), "/preferences.md")
        stored = item.value["content"]
        assert "<user_instructions>" in stored
        assert "</user_instructions>" in stored
        assert "<learned_preferences>" in stored
        assert "</learned_preferences>" in stored
        assert "I prefer budget travel." in stored
