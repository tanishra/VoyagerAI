from __future__ import annotations

from config.settings import settings
from langchain_google_genai import ChatGoogleGenerativeAI

from agents.subagents.constraint_analyzer import build_constraint_analyzer
from agents.subagents.cost_optimizer import build_cost_optimizer
from agents.subagents.enricher import build_enricher
from agents.subagents.multi_plan_generator import build_multi_plan_generator
from agents.subagents.researcher import build_researcher
from agents.subagents.risk_detector import build_risk_detector
from agents.subagents.validator import build_validator
from agents.tools import get_internet_tools


def _get_model() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model="gemini-3.5-flash",
        google_api_key=settings.GEMINI_API_KEY,
        temperature=0.3,
    )


def get_subagents() -> list:
    model = _get_model()
    internet_tools = get_internet_tools()

    return [
        build_researcher(model, internet_tools),
        build_validator(model),
        build_enricher(model, internet_tools),
        build_cost_optimizer(model, internet_tools),
        build_risk_detector(model, internet_tools),
        build_constraint_analyzer(model),
        build_multi_plan_generator(model),
    ]
