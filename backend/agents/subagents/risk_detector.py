"""Risk detection subagent: identifies travel risks before the itinerary is built."""

from __future__ import annotations

from deepagents import SubAgent
from langchain_google_genai import ChatGoogleGenerativeAI

from agents.prompts import RISK_DETECTOR_SYSTEM_PROMPT
from agents.tools import get_internet_tools


def build_risk_detector(model: ChatGoogleGenerativeAI, tools: list | None = None) -> SubAgent:
    return SubAgent(
        name="risk_detector",
        description=(
            "Detects travel risks: seasonal closures, weather hazards, transit gaps, "
            "safety advisories, and holiday impacts. Returns structured risks with mitigations."
        ),
        system_prompt=RISK_DETECTOR_SYSTEM_PROMPT,
        model=model,
        tools=tools if tools is not None else get_internet_tools(),
    )
