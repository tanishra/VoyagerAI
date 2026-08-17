"""Persist activity metadata (thinking, tool calls, usage) per thread.

Stores activity data in the LangGraph BaseStore (Redis or in-memory) so it
survives page refresh and thread switching. Data is keyed by thread_id +
message index.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger("travel_agent.activity_store")

_ACTIVITY_NAMESPACE = ("activity",)


async def save_activity(store: Any, thread_id: str, activity: dict) -> None:
    """Save activity metadata for the latest assistant message in a thread."""
    try:
        key = f"{thread_id}:latest"
        store.aput(
            _ACTIVITY_NAMESPACE,
            key,
            {
                "thinking": activity.get("thinking", []),
                "tool_calls": activity.get("tool_calls", []),
                "usage": activity.get("usage", []),
                "total_input_tokens": activity.get("total_input_tokens", 0),
                "total_output_tokens": activity.get("total_output_tokens", 0),
            },
        )
    except Exception:
        logger.warning("Failed to save activity for thread %s", thread_id, exc_info=True)


async def load_activity(store: Any, thread_id: str) -> dict | None:
    """Load activity metadata for the latest assistant message in a thread."""
    try:
        key = f"{thread_id}:latest"
        item = store.aget(_ACTIVITY_NAMESPACE, key)
        if item is None:
            return None
        return item.value
    except Exception:
        logger.warning("Failed to load activity for thread %s", thread_id, exc_info=True)
        return None
