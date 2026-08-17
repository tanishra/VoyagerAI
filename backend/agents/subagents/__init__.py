from __future__ import annotations

import logging
from typing import Any

from deepagents import SubAgent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage

from agents.llm import get_subagent_model
from agents.subagents.constraint_analyzer import build_constraint_analyzer
from agents.subagents.cost_optimizer import build_cost_optimizer
from agents.subagents.enricher import build_enricher
from agents.subagents.multi_plan_generator import build_multi_plan_generator
from agents.subagents.quality_scorer import build_quality_scorer
from agents.subagents.researcher import build_researcher
from agents.subagents.risk_detector import build_risk_detector
from agents.subagents.validator import build_validator
from agents.tools import get_internet_tools

logger = logging.getLogger("travel_agent")


class _ResilientModel(BaseChatModel):
    """Wraps a chat model so exceptions return a fallback AIMessage.

    If the inner model raises during invoke/ainvoke, the caller gets a
    message telling the orchestrator that this sub-agent failed and to
    proceed with remaining results. Streaming methods delegate to the
    inner model (exceptions there are handled by the stream layer).
    """

    inner: BaseChatModel
    subagent_name: str

    def __init__(self, inner: BaseChatModel, subagent_name: str) -> None:
        super().__init__(inner=inner, subagent_name=subagent_name)

    @property
    def _llm_type(self) -> str:
        return f"resilient({self.inner._llm_type})"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        try:
            return self.inner._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
        except Exception as exc:
            logger.warning("Subagent '%s' model failed: %s", self.subagent_name, exc)
            return self._fallback_result(exc)

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        try:
            return await self.inner._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs)
        except Exception as exc:
            logger.warning("Subagent '%s' model failed: %s", self.subagent_name, exc)
            return self._fallback_result(exc)

    def _fallback_result(self, exc: Exception):
        from langchain_core.outputs import ChatGeneration, ChatResult
        msg = AIMessage(
            content=(
                f"[SUBAGENT FAILED] The {self.subagent_name} subagent encountered an error: {exc}. "
                "Proceed with remaining results and note this gap to the user."
            )
        )
        return ChatResult(generations=[ChatGeneration(message=msg)])

    def stream(self, input, config=None, **kwargs):
        return self.inner.stream(input, config=config, **kwargs)

    async def astream(self, input, config=None, **kwargs):
        async for chunk in self.inner.astream(input, config=config, **kwargs):
            yield chunk


def wrap_subagent_for_resilience(spec: SubAgent) -> SubAgent:
    """Wrap a SubAgent spec's model with _ResilientModel for graceful degradation."""
    return {
        **spec,
        "model": _ResilientModel(spec["model"], spec["name"]),
    }


def get_subagents() -> list:
    model = get_subagent_model()
    internet_tools = get_internet_tools()

    raw = [
        build_researcher(model, internet_tools),
        build_validator(model),
        build_enricher(model, internet_tools),
        build_cost_optimizer(model, internet_tools),
        build_risk_detector(model, internet_tools),
        build_constraint_analyzer(model),
        build_multi_plan_generator(model),
        build_quality_scorer(model),
    ]

    return [wrap_subagent_for_resilience(spec) for spec in raw]
