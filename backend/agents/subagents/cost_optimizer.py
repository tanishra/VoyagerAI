"""Cost optimizer subagent: reduces over-budget itineraries while preserving quality."""

from __future__ import annotations

from deepagents import SubAgent
from langchain_google_genai import ChatGoogleGenerativeAI

from agents.prompts import COST_OPTIMIZER_SYSTEM_PROMPT
from agents.tools import get_internet_tools


def build_cost_optimizer(model: ChatGoogleGenerativeAI, tools: list | None = None) -> SubAgent:
    return SubAgent(
        name="cost_optimizer",
        description=(
            "Optimizes over-budget itineraries: suggests accommodation alternatives, "
            "activity swaps, transport changes, and budget rebalancing."
        ),
        system_prompt=COST_OPTIMIZER_SYSTEM_PROMPT,
        model=model,
        tools=tools if tools is not None else get_internet_tools(),
    )
