"""Tests for per-subagent model routing via SUBAGENT_MODEL_OVERRIDES."""

from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest

from agents.llm import get_subagent_model, _parse_subagent_overrides
from config.settings import settings


class TestModelRouting:
    def test_default_subagent_model(self):
        """Without overrides, get_subagent_model uses the default model."""
        with patch.object(settings, "LLM_SUBAGENT_MODEL", "gemini/gemini-3.5-flash-lite"), \
             patch.object(settings, "LLM_TEMPERATURE_SUBAGENT", 1.0), \
             patch.object(settings, "LLM_SUBAGENT_FALLBACK", None), \
             patch.object(settings, "SUBAGENT_MODEL_OVERRIDES", ""):

            model = get_subagent_model("researcher")
            assert model.model == "gemini/gemini-3.5-flash-lite"

    def test_subagent_model_override(self):
        """With overrides, get_subagent_model uses the overridden model."""
        with patch.object(settings, "LLM_SUBAGENT_MODEL", "gemini/gemini-3.5-flash-lite"), \
             patch.object(settings, "LLM_TEMPERATURE_SUBAGENT", 1.0), \
             patch.object(settings, "LLM_SUBAGENT_FALLBACK", None), \
             patch.object(settings, "SUBAGENT_MODEL_OVERRIDES", json.dumps({
                 "researcher": "gemini/gemini-2.5-pro",
             })):

            model = get_subagent_model("researcher")
            assert model.model == "gemini/gemini-2.5-pro"

    def test_subagent_model_partial_override(self):
        """Only overridden subagents get the new model; others use default."""
        with patch.object(settings, "LLM_SUBAGENT_MODEL", "gemini/gemini-3.5-flash-lite"), \
             patch.object(settings, "LLM_TEMPERATURE_SUBAGENT", 1.0), \
             patch.object(settings, "LLM_SUBAGENT_FALLBACK", None), \
             patch.object(settings, "SUBAGENT_MODEL_OVERRIDES", json.dumps({
                 "researcher": "gemini/gemini-2.5-pro",
             })):

            # Overridden
            model_researcher = get_subagent_model("researcher")
            assert model_researcher.model == "gemini/gemini-2.5-pro"

            # Not overridden — uses default
            model_validator = get_subagent_model("validator")
            assert model_validator.model == "gemini/gemini-3.5-flash-lite"

    def test_parse_overrides_empty(self):
        """Empty string returns empty dict."""
        with patch.object(settings, "SUBAGENT_MODEL_OVERRIDES", ""):
            assert _parse_subagent_overrides() == {}

    def test_parse_overrides_invalid_json(self):
        """Invalid JSON returns empty dict (no crash)."""
        with patch.object(settings, "SUBAGENT_MODEL_OVERRIDES", "not valid json"):
            assert _parse_subagent_overrides() == {}

    def test_no_subagent_name_uses_default(self):
        """Calling without subagent_name uses the default model."""
        with patch.object(settings, "LLM_SUBAGENT_MODEL", "gemini/gemini-3.5-flash-lite"), \
             patch.object(settings, "LLM_TEMPERATURE_SUBAGENT", 1.0), \
             patch.object(settings, "LLM_SUBAGENT_FALLBACK", None), \
             patch.object(settings, "SUBAGENT_MODEL_OVERRIDES", json.dumps({
                 "researcher": "gemini/gemini-2.5-pro",
             })):

            model = get_subagent_model()
            assert model.model == "gemini/gemini-3.5-flash-lite"
