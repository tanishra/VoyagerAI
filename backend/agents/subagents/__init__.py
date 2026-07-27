from __future__ import annotations

from deepagents import SubAgent
from langchain_google_genai import ChatGoogleGenerativeAI

from config.settings import settings
from agents.prompts import (
    RESEARCHER_SYSTEM_PROMPT,
    VALIDATOR_SYSTEM_PROMPT,
    ENRICHER_SYSTEM_PROMPT,
    COST_OPTIMIZER_SYSTEM_PROMPT,
)
from agents.tools import get_internet_tools


def _get_model() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=settings.GEMINI_API_KEY,
        temperature=0.3,
    )


def get_subagents() -> list:
    model = _get_model()
    internet_tools = get_internet_tools()

    return [
        SubAgent(
            name="researcher",
            description=(
                "Researches destination intelligence: events, weather, visa requirements, "
                "safety advisories, seasonal pricing, neighborhoods, and local customs. "
                "Uses internet_search and saves structured briefs."
            ),
            system_prompt=RESEARCHER_SYSTEM_PROMPT,
            model=model,
            tools=internet_tools,
        ),
        SubAgent(
            name="validator",
            description=(
                "Validates itineraries against budget, constraints, and internal consistency. "
                "Returns pass/fail with specific issues and suggested fixes."
            ),
            system_prompt=VALIDATOR_SYSTEM_PROMPT,
            model=model,
            tools=[],
        ),
        SubAgent(
            name="enricher",
            description=(
                "Enriches individual days with practical tips: weather advice, local customs, "
                "safety tips, money-saving alternatives, and logistical warnings."
            ),
            system_prompt=ENRICHER_SYSTEM_PROMPT,
            model=model,
            tools=internet_tools,
        ),
        SubAgent(
            name="cost_optimizer",
            description=(
                "Optimizes over-budget itineraries: suggests accommodation alternatives, "
                "activity swaps, transport changes, and budget rebalancing."
            ),
            system_prompt=COST_OPTIMIZER_SYSTEM_PROMPT,
            model=model,
            tools=internet_tools,
        ),
    ]
