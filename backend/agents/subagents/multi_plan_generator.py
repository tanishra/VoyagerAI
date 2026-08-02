"""Multi-plan generator sub-agent: produces 3 budget-tiered itinerary variants."""

from __future__ import annotations

from deepagents import SubAgent
from langchain_google_genai import ChatGoogleGenerativeAI

from agents.prompts import MULTI_PLAN_GENERATOR_SYSTEM_PROMPT


def build_multi_plan_generator(
    model: ChatGoogleGenerativeAI, tools: list | None = None
) -> SubAgent:
    return SubAgent(
        name="multi_plan_generator",
        description=(
            "Generates 3 budget-tiered itinerary variants (budget, balanced, premium) "
            "from research, constraints, and risk data. Returns structured plans with "
            "cost breakdowns, tradeoffs, and a comparison matrix."
        ),
        system_prompt=MULTI_PLAN_GENERATOR_SYSTEM_PROMPT,
        model=model,
        tools=tools if tools is not None else [],
    )
