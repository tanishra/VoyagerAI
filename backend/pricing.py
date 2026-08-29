"""API pricing table and cost calculation.

Maps LiteLLM model strings to per-1K-token costs (input and output).
Used by the cost tracking system to calculate dollar costs per LLM call.
Unknown models fall back to DEFAULT_PRICING.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("travel_agent.pricing")

PRICING_TABLE: dict[str, dict[str, float]] = {
    # Gemini
    "gemini/gemini-3.7-flash": {"input_per_1k": 0.0003, "output_per_1k": 0.0006},
    "gemini/gemini-3.5-flash-lite": {"input_per_1k": 0.000075, "output_per_1k": 0.0003},
    "gemini/gemini-2.5-pro": {"input_per_1k": 0.00125, "output_per_1k": 0.005},
    "gemini/gemini-2.5-flash": {"input_per_1k": 0.00015, "output_per_1k": 0.0006},
    "gemini/gemini-2.0-flash": {"input_per_1k": 0.0001, "output_per_1k": 0.0004},
    "gemini/gemini-1.5-pro": {"input_per_1k": 0.00125, "output_per_1k": 0.005},
    "gemini/gemini-1.5-flash": {"input_per_1k": 0.000075, "output_per_1k": 0.0003},
    # OpenAI
    "openai/gpt-4o": {"input_per_1k": 0.0025, "output_per_1k": 0.01},
    "openai/gpt-4o-mini": {"input_per_1k": 0.00015, "output_per_1k": 0.0006},
    "openai/gpt-4-turbo": {"input_per_1k": 0.01, "output_per_1k": 0.03},
    "openai/gpt-3.5-turbo": {"input_per_1k": 0.0005, "output_per_1k": 0.0015},
    # Anthropic
    "anthropic/claude-3-5-sonnet": {"input_per_1k": 0.003, "output_per_1k": 0.015},
    "anthropic/claude-3-5-haiku": {"input_per_1k": 0.0008, "output_per_1k": 0.004},
    "anthropic/claude-3-opus": {"input_per_1k": 0.015, "output_per_1k": 0.075},
}

DEFAULT_PRICING: dict[str, float] = {"input_per_1k": 0.0003, "output_per_1k": 0.0006}


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate the estimated USD cost for an LLM call.

    Args:
        model: LiteLLM model string (e.g. "gemini/gemini-3.7-flash").
        input_tokens: Number of input/prompt tokens consumed.
        output_tokens: Number of output/completion tokens generated.

    Returns:
        Estimated cost in USD (float).
    """
    pricing = PRICING_TABLE.get(model, DEFAULT_PRICING)
    cost = (input_tokens / 1000 * pricing["input_per_1k"]) + (
        output_tokens / 1000 * pricing["output_per_1k"]
    )
    return round(cost, 6)


def get_pricing(model: str) -> dict[str, float]:
    """Return the pricing entry for a model, or the default if unknown."""
    return PRICING_TABLE.get(model, DEFAULT_PRICING)
