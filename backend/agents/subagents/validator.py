"""Validator subagent: checks itineraries against budget, constraints, and consistency."""

from __future__ import annotations

from deepagents import SubAgent
from langchain_core.language_models import BaseChatModel

from agents.prompts import VALIDATOR_SYSTEM_PROMPT


def build_validator(model: BaseChatModel, tools: list | None = None) -> SubAgent:
    return SubAgent(
        name="validator",
        description=(
            "Validates itineraries against budget, constraints, and internal consistency. "
            "Returns pass/fail with specific issues and suggested fixes."
        ),
        system_prompt=VALIDATOR_SYSTEM_PROMPT,
        model=model,
        tools=tools or [],
    )
