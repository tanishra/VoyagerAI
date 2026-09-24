from __future__ import annotations

from agents.tools.internet import get_internet_tools, reset_orchestrator_search_count
from agents.tools.visuals import get_current_thread_id, get_visual_tools, is_visual_tool, set_current_thread_id

__all__ = [
    "get_internet_tools",
    "get_orchestrator_tools",
    "reset_orchestrator_search_count",
    "get_visual_tools",
    "get_current_thread_id",
    "is_visual_tool",
    "set_current_thread_id",
]


def get_orchestrator_tools() -> list:
    """Return all tools available directly to the orchestrator."""
    from agents.tools.internet import get_orchestrator_tools as _get_internet_orch_tools

    tools = _get_internet_orch_tools() + get_visual_tools()

    # The orchestrator delegates plan generation to the deterministic
    # pipeline instead of emitting plan JSON in its text.
    from agents.tools.pipeline_tools import get_pipeline_tools

    tools += get_pipeline_tools()

    return tools
