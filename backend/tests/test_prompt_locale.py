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
