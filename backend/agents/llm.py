"""LLM model factory — config-driven provider selection via LiteLLM.

All model instantiation goes through this module so provider switching
(Gemini, OpenAI, Anthropic, etc.) is a pure env-var change.
"""

from __future__ import annotations

import json
import logging

from langchain_core.language_models import BaseChatModel
from langchain_litellm import ChatLiteLLM

from config.settings import settings

logger = logging.getLogger("travel_agent.llm")


def _build_fallbacks(fallback: str | None) -> list[str] | None:
    if fallback:
        return [fallback]
    return None


def _parse_subagent_overrides() -> dict[str, str]:
    """Parse SUBAGENT_MODEL_OVERRIDES env var (JSON string) into a dict."""
    raw = settings.SUBAGENT_MODEL_OVERRIDES
    if not raw:
        return {}
    try:
        overrides = json.loads(raw)
        if isinstance(overrides, dict):
            return {k: v for k, v in overrides.items() if isinstance(k, str) and isinstance(v, str)}
    except (json.JSONDecodeError, TypeError):
        logger.warning("Invalid SUBAGENT_MODEL_OVERRIDES JSON: %s", raw)
    return {}


def get_orchestrator_model() -> ChatLiteLLM:
    """Stronger model for the main orchestrator agent."""
    return ChatLiteLLM(
        model=settings.LLM_ORCHESTRATOR_MODEL,
        temperature=settings.LLM_TEMPERATURE_ORCHESTRATOR,
        streaming=True,
        fallbacks=_build_fallbacks(settings.LLM_ORCHESTRATOR_FALLBACK),
    )


def get_subagent_model(subagent_name: str | None = None) -> ChatLiteLLM:
    """Faster/cheaper model for subagents.

    If subagent_name is provided, checks SUBAGENT_MODEL_OVERRIDES for a
    per-subagent model override. Falls back to the default subagent model.
    """
    model_str = settings.LLM_SUBAGENT_MODEL
    if subagent_name:
        overrides = _parse_subagent_overrides()
        model_str = overrides.get(subagent_name, model_str)
    return ChatLiteLLM(
        model=model_str,
        temperature=settings.LLM_TEMPERATURE_SUBAGENT,
        streaming=True,
        fallbacks=_build_fallbacks(settings.LLM_SUBAGENT_FALLBACK),
    )


def get_formatter_model(schema: type) -> BaseChatModel:
    """Model with structured output binding for itinerary JSON recovery."""
    model = ChatLiteLLM(
        model=settings.LLM_ORCHESTRATOR_MODEL,
        temperature=0.1,
        streaming=True,
        fallbacks=_build_fallbacks(settings.LLM_ORCHESTRATOR_FALLBACK),
    )
    return model.with_structured_output(schema)
