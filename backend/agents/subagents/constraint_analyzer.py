"""Constraint analysis subagent: derives enforceable trip constraints from user context."""

from __future__ import annotations

from deepagents import SubAgent
from langchain_core.language_models import BaseChatModel

from agents.prompts import CONSTRAINT_ANALYZER_SYSTEM_PROMPT


def build_constraint_analyzer(model: BaseChatModel, tools: list | None = None) -> SubAgent:
    return SubAgent(
        name="constraint_analyzer",
        description=(
            "Analyzes user constraints: budget math, dietary needs, accessibility, group "
            "composition, and travel style. Reads saved preferences and returns structured constraints."
        ),
        system_prompt=CONSTRAINT_ANALYZER_SYSTEM_PROMPT,
        model=model,
        tools=tools or [],
    )
