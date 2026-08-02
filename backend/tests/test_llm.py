"""Tests for the LLM model factory (agents/llm.py)."""

from __future__ import annotations

from agents.llm import get_orchestrator_model, get_subagent_model
from config.settings import settings


class TestOrchestratorModel:
    def test_returns_chatlitellm(self):
        model = get_orchestrator_model()
        assert model.model == settings.LLM_ORCHESTRATOR_MODEL

    def test_uses_orchestrator_temperature(self):
        model = get_orchestrator_model()
        assert model.temperature == settings.LLM_TEMPERATURE_ORCHESTRATOR


class TestSubagentModel:
    def test_returns_chatlitellm(self):
        model = get_subagent_model()
        assert model.model == settings.LLM_SUBAGENT_MODEL

    def test_uses_subagent_temperature(self):
        model = get_subagent_model()
        assert model.temperature == settings.LLM_TEMPERATURE_SUBAGENT

    def test_different_from_orchestrator(self):
        orch = get_orchestrator_model()
        sub = get_subagent_model()
        assert orch.model != sub.model
