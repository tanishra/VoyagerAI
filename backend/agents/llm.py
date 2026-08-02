"""LLM model factory — config-driven provider selection via LiteLLM.

All model instantiation goes through this module so provider switching
(Gemini, OpenAI, Anthropic, etc.) is a pure env-var change.
"""

from __future__ import annotations

from config.settings import settings
from langchain_core.language_models import BaseChatModel
from langchain_litellm import ChatLiteLLM


def _build_fallbacks(fallback: str | None) -> list[str] | None:
    if fallback:
        return [fallback]
    return None


def get_orchestrator_model() -> ChatLiteLLM:
    """Stronger model for the main orchestrator agent."""
    return ChatLiteLLM(
        model=settings.LLM_ORCHESTRATOR_MODEL,
        temperature=settings.LLM_TEMPERATURE_ORCHESTRATOR,
        fallbacks=_build_fallbacks(settings.LLM_ORCHESTRATOR_FALLBACK),
    )


def get_subagent_model() -> ChatLiteLLM:
    """Faster/cheaper model for subagents."""
    return ChatLiteLLM(
        model=settings.LLM_SUBAGENT_MODEL,
        temperature=settings.LLM_TEMPERATURE_SUBAGENT,
        fallbacks=_build_fallbacks(settings.LLM_SUBAGENT_FALLBACK),
    )


def get_formatter_model(schema: type) -> BaseChatModel:
    """Model with structured output binding for itinerary JSON recovery."""
    model = ChatLiteLLM(
        model=settings.LLM_ORCHESTRATOR_MODEL,
        temperature=0.1,
        fallbacks=_build_fallbacks(settings.LLM_ORCHESTRATOR_FALLBACK),
    )
    return model.with_structured_output(schema)
