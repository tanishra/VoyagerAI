"""Tests for locale-aware prompt injection in agents.prompts."""

import importlib.util
from pathlib import Path

# Load prompts.py directly from file to avoid agents/__init__.py
# triggering deep_agent -> deepagents import chain.
_spec = importlib.util.spec_from_file_location(
    "agents.prompts",
    Path(__file__).resolve().parent.parent / "agents" / "prompts.py",
)
assert _spec is not None and _spec.loader is not None
_prompts = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_prompts)
build_chat_agent_prompt = _prompts.build_chat_agent_prompt
LANGUAGE_INSTRUCTIONS = _prompts.LANGUAGE_INSTRUCTIONS
CHAT_AGENT_SYSTEM_PROMPT = _prompts.CHAT_AGENT_SYSTEM_PROMPT


class TestBuildChatAgentPrompt:
    def test_default_returns_base_prompt(self):
        prompt = build_chat_agent_prompt(None)
        assert prompt == CHAT_AGENT_SYSTEM_PROMPT

    def test_english_returns_base_prompt(self):
        prompt = build_chat_agent_prompt("en")
        assert prompt == CHAT_AGENT_SYSTEM_PROMPT

    def test_spanish_injects_language_block(self):
        prompt = build_chat_agent_prompt("es")
        assert prompt != CHAT_AGENT_SYSTEM_PROMPT
        assert "<language>" in prompt
        assert "Spanish" in prompt
        assert prompt.startswith(CHAT_AGENT_SYSTEM_PROMPT)

    def test_french_injects_language_block(self):
        prompt = build_chat_agent_prompt("fr")
        assert "<language>" in prompt
        assert "French" in prompt
        assert prompt.startswith(CHAT_AGENT_SYSTEM_PROMPT)

    def test_french_prose_assertion(self):
        """French locale prompt contains actionable French language instruction."""
        prompt = build_chat_agent_prompt("fr")
        lang_block = prompt.split("<language>")[1].split("</language>")[0]
        assert "French" in lang_block
        assert len(lang_block.strip()) > 10

    def test_german_injects_language_block(self):
        prompt = build_chat_agent_prompt("de")
        assert "<language>" in prompt
        assert "German" in prompt

    def test_hindi_injects_language_block(self):
        prompt = build_chat_agent_prompt("hi")
        assert "<language>" in prompt
        assert "Hindi" in prompt

    def test_japanese_injects_language_block(self):
        prompt = build_chat_agent_prompt("ja")
        assert "<language>" in prompt
        assert "Japanese" in prompt

    def test_unknown_locale_returns_base_prompt(self):
        prompt = build_chat_agent_prompt("xx")
        assert prompt == CHAT_AGENT_SYSTEM_PROMPT

    def test_all_supported_locales_have_instructions(self):
        for locale in ("en", "es", "fr", "de", "hi", "ja"):
            assert locale in LANGUAGE_INSTRUCTIONS
            assert len(LANGUAGE_INSTRUCTIONS[locale]) > 0


class TestTimezoneInjection:
    def test_timezone_injects_datetime_block(self):
        prompt = build_chat_agent_prompt("en", timezone="Asia/Kolkata")
        assert "<current_datetime>" in prompt
        assert "Asia/Kolkata" in prompt
        assert prompt.startswith(CHAT_AGENT_SYSTEM_PROMPT)

    def test_timezone_includes_day_of_week(self):
        prompt = build_chat_agent_prompt("en", timezone="Asia/Kolkata")
        dt_block = prompt.split("<current_datetime>")[1].split("</current_datetime>")[0]
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        assert any(day in dt_block for day in days)

    def test_timezone_includes_time(self):
        prompt = build_chat_agent_prompt("en", timezone="Asia/Kolkata")
        dt_block = prompt.split("<current_datetime>")[1].split("</current_datetime>")[0]
        assert "AM" in dt_block or "PM" in dt_block

    def test_timezone_includes_utc_offset(self):
        prompt = build_chat_agent_prompt("en", timezone="Asia/Kolkata")
        dt_block = prompt.split("<current_datetime>")[1].split("</current_datetime>")[0]
        assert "UTC+" in dt_block or "UTC-" in dt_block

    def test_invalid_timezone_falls_back_silently(self):
        prompt = build_chat_agent_prompt("en", timezone="Invalid/Zone")
        assert "<current_datetime>" not in prompt
        assert prompt == CHAT_AGENT_SYSTEM_PROMPT

    def test_none_timezone_no_injection(self):
        prompt = build_chat_agent_prompt("en", timezone=None)
        assert "<current_datetime>" not in prompt
        assert prompt == CHAT_AGENT_SYSTEM_PROMPT

    def test_timezone_with_locale(self):
        prompt = build_chat_agent_prompt("es", timezone="Europe/Paris")
        assert "<current_datetime>" in prompt
        assert "<language>" in prompt
        assert "Europe/Paris" in prompt
        assert "Spanish" in prompt

    def test_timezone_block_before_language_block(self):
        prompt = build_chat_agent_prompt("fr", timezone="Asia/Tokyo")
        dt_pos = prompt.find("<current_datetime>")
        lang_pos = prompt.find("<language>")
        assert dt_pos != -1
        assert lang_pos != -1
        assert dt_pos < lang_pos
