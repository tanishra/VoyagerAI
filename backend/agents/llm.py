"""LLM model factory — config-driven provider selection via LiteLLM.

All model instantiation goes through this module so provider switching
(Gemini, OpenAI, Anthropic, etc.) is a pure env-var change.
"""

from __future__ import annotations

import json
import logging

import litellm
from langchain_core.language_models import BaseChatModel
from langchain_litellm import ChatLiteLLM

from config.settings import settings

logger = logging.getLogger("travel_agent.llm")


def _model_litellm_params(model_str: str) -> dict:
    """Raw LiteLLM completion params required by certain model families.

    OpenAI "luna" reasoning models (e.g. gpt-6-luna) reject function tools
    on /v1/chat/completions unless reasoning_effort='none' — LiteLLM routes
    through Chat Completions, so force it off for those models. Trade-off:
    hidden reasoning is disabled; latency and cost drop accordingly.
    """
    try:
        info = litellm.get_model_info(model_str)
    except Exception:  # noqa: BLE001 — unknown model, leave params empty
        return {}
    if info.get("supports_reasoning") and info.get("supports_none_reasoning_effort"):
        return {
            "reasoning_effort": "none",
            "allowed_openai_params": ["reasoning_effort"],
        }
    return {}


def _model_kwargs(model_str: str, fallback: str | None) -> dict:
    """ChatLiteLLM model_kwargs — litellm params (incl. fallbacks) must
    live here; ChatLiteLLM drops unknown top-level init kwargs."""
    params = dict(_model_litellm_params(model_str))
    if fallback:
        extra = _model_litellm_params(fallback) or {"reasoning_effort": None}
        # Dict entry lets the fallback override shared params — a plain
        # reasoning_effort=None is stripped by LiteLLM so a 'none' set for
        # the primary is not forwarded to a non-reasoning fallback.
        params["fallbacks"] = [{"model": fallback, **extra}]
    return params


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
        model_kwargs=_model_kwargs(
            settings.LLM_ORCHESTRATOR_MODEL,
            settings.LLM_ORCHESTRATOR_FALLBACK,
        ),
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
        model_kwargs=_model_kwargs(model_str, settings.LLM_SUBAGENT_FALLBACK),
    )


def get_formatter_model(schema: type) -> BaseChatModel:
    """Model with structured output binding for itinerary JSON recovery."""
    model = ChatLiteLLM(
        model=settings.LLM_ORCHESTRATOR_MODEL,
        temperature=0.1,
        streaming=True,
        model_kwargs=_model_kwargs(
            settings.LLM_ORCHESTRATOR_MODEL,
            settings.LLM_ORCHESTRATOR_FALLBACK,
        ),
    )
    return model.with_structured_output(schema)
