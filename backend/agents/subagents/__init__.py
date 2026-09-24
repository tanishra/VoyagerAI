from __future__ import annotations

import logging
from typing import Any

from deepagents import SubAgent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage

from agents.llm import get_subagent_model
from agents.subagents.researcher import build_researcher
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

    def bind_tools(self, tools, **kwargs):
        return self.inner.bind_tools(tools, **kwargs)


def wrap_subagent_for_resilience(spec: SubAgent) -> SubAgent:
    """Wrap a SubAgent spec's model with _ResilientModel for graceful degradation."""
    return {
        **spec,
        "model": _ResilientModel(spec["model"], spec["name"]),
    }


def get_subagents() -> list:
    """Subagents dispatchable by the orchestrator via the task tool.

    Only the researcher remains — plan generation, validation, and
    enrichment run inside the deterministic pipeline (agents/pipeline.py),
    not as orchestrator-dispatched subagents.
    """
    raw = [build_researcher(get_subagent_model("researcher"), get_internet_tools())]
    return [wrap_subagent_for_resilience(spec) for spec in raw]
