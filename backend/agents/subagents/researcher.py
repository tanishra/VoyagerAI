"""Researcher subagent: gathers destination intelligence via internet search."""

from __future__ import annotations

from deepagents import SubAgent
from langchain_google_genai import ChatGoogleGenerativeAI

from agents.prompts import RESEARCHER_SYSTEM_PROMPT
from agents.tools import get_internet_tools


def build_researcher(model: ChatGoogleGenerativeAI, tools: list | None = None) -> SubAgent:
    return SubAgent(
        name="researcher",
        description=(
            "Researches destination intelligence: events, weather, visa requirements, "
            "safety advisories, seasonal pricing, neighborhoods, and local customs. "
            "Uses internet_search and saves structured briefs."
        ),
        system_prompt=RESEARCHER_SYSTEM_PROMPT,
        model=model,
        tools=tools if tools is not None else get_internet_tools(),
    )
