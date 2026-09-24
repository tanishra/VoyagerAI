"""Persist activity metadata (thinking, tool calls, usage) per thread, per message.

Stores activity data in the LangGraph BaseStore (Redis or in-memory) so it
survives page refresh and thread switching. Data is keyed by thread_id,
with a per-message-index map so every assistant message's activity
(including generated images/charts) persists across reloads.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("travel_agent.activity_store")

_ACTIVITY_NAMESPACE = ("activity",)


async def save_activity(
    store: Any, thread_id: str, activity: dict, message_index: int | None = None
) -> None:
    """Save activity metadata for an assistant message in a thread.

    If message_index is provided, stores in a per-message map keyed by
    thread_id. If message_index is None, falls back to the legacy
    "latest" key for backward compatibility.
    """
    try:
        if message_index is not None:
            key = thread_id
            existing = await store.aget(_ACTIVITY_NAMESPACE, key)
            all_activity: dict[str, dict] = {}
            if existing is not None and isinstance(existing.value, dict):
                all_activity = existing.value
            all_activity[str(message_index)] = {
                "thinking": activity.get("thinking", []),
                "tool_calls": activity.get("tool_calls", []),
                "usage": activity.get("usage", []),
                "total_input_tokens": activity.get("total_input_tokens", 0),
                "total_output_tokens": activity.get("total_output_tokens", 0),
                "images": activity.get("images", []),
                "charts": activity.get("charts", []),
            }
            await store.aput(_ACTIVITY_NAMESPACE, key, all_activity)
        else:
            key = f"{thread_id}:latest"
            await store.aput(
                _ACTIVITY_NAMESPACE,
                key,
                {
                    "thinking": activity.get("thinking", []),
                    "tool_calls": activity.get("tool_calls", []),
                    "usage": activity.get("usage", []),
                    "total_input_tokens": activity.get("total_input_tokens", 0),
                    "total_output_tokens": activity.get("total_output_tokens", 0),
                    "images": activity.get("images", []),
                    "charts": activity.get("charts", []),
                },
            )
    except Exception:
        logger.warning("Failed to save activity for thread %s", thread_id, exc_info=True)


async def load_all_activity(store: Any, thread_id: str) -> dict[str, dict] | None:
    """Load the full per-message activity map for a thread.

    Returns a dict mapping message_index (as string) -> activity dict,
    or None if no activity data exists.
    """
    try:
        key = thread_id
        item = await store.aget(_ACTIVITY_NAMESPACE, key)
        if item is not None and isinstance(item.value, dict):
            return item.value
        return None
    except Exception:
        logger.warning("Failed to load all activity for thread %s", thread_id, exc_info=True)
        return None


async def load_activity(
    store: Any, thread_id: str, message_index: int | None = None
) -> dict | None:
    """Load activity metadata for a specific message or the latest message.

    If message_index is provided, returns that message's activity from the
    per-message map. If None, falls back to the legacy "latest" key.
    """
    try:
        if message_index is not None:
            all_activity = await load_all_activity(store, thread_id)
            if all_activity is None:
                return None
            return all_activity.get(str(message_index))
        else:
            key = f"{thread_id}:latest"
            item = await store.aget(_ACTIVITY_NAMESPACE, key)
            if item is None:
                return None
            return item.value
    except Exception:
        logger.warning("Failed to load activity for thread %s", thread_id, exc_info=True)
        return None
