"""Enricher subagent: adds practical local tips to individual day plans."""

from __future__ import annotations

from deepagents import SubAgent
from langchain_core.language_models import BaseChatModel

from agents.prompts import ENRICHER_SYSTEM_PROMPT
from agents.tools import get_internet_tools


def build_enricher(model: BaseChatModel, tools: list | None = None) -> SubAgent:
    return SubAgent(
        name="enricher",
        description=(
            "Enriches individual days with practical tips: weather advice, local customs, "
            "safety tips, money-saving alternatives, and logistical warnings."
        ),
        system_prompt=ENRICHER_SYSTEM_PROMPT,
        model=model,
        tools=tools if tools is not None else get_internet_tools(),
    )
