"""Quality scorer subagent: evaluates itinerary plans against 10 criteria."""

from __future__ import annotations

from deepagents import SubAgent
from langchain_core.language_models import BaseChatModel

from agents.prompts import QUALITY_SCORER_SYSTEM_PROMPT


def build_quality_scorer(model: BaseChatModel, tools: list | None = None) -> SubAgent:
    return SubAgent(
        name="quality_scorer",
        description=(
            "Scores a travel itinerary 0-100 against 10 quality criteria. "
            "Returns score, issues with severity and fixes, and optionally an "
            "improved plan. Used for self-critique before presenting plans to the user."
        ),
        system_prompt=QUALITY_SCORER_SYSTEM_PROMPT,
        model=model,
        tools=tools or [],
    )
