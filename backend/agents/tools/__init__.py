from __future__ import annotations

from agents.tools.internet import get_internet_tools, reset_orchestrator_search_count
from agents.tools.visuals import get_visual_tools, is_visual_tool, set_current_thread_id

__all__ = [
    "get_internet_tools",
    "get_orchestrator_tools",
    "reset_orchestrator_search_count",
    "get_visual_tools",
    "is_visual_tool",
    "set_current_thread_id",
]


def get_orchestrator_tools() -> list:
    """Return all tools available directly to the orchestrator."""
    from agents.tools.internet import get_orchestrator_tools as _get_internet_orch_tools
    return _get_internet_orch_tools() + get_visual_tools()
