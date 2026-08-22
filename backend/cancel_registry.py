"""Module-level cancel registry for chat stream cancellation.

Maps thread_id → asyncio.Event so that a POST /chat/cancel request
can signal an active SSE stream to stop processing immediately.
"""

from __future__ import annotations

import asyncio

_cancel_events: dict[str, asyncio.Event] = {}


def register_cancel(thread_id: str) -> asyncio.Event:
    """Create and register a cancel event for *thread_id*.

    Returns the event so the streaming coroutine can poll ``is_set()``.
    If an event already exists for this thread_id it is replaced.
    """
    event = asyncio.Event()
    _cancel_events[thread_id] = event
    return event


def cancel_stream(thread_id: str) -> bool:
    """Signal the cancel event for *thread_id*.

    Returns ``True`` if an active stream was found and signalled,
    ``False`` if no stream is registered for this thread_id.
    """
    event = _cancel_events.get(thread_id)
    if event:
        event.set()
        return True
    return False


def unregister_cancel(thread_id: str) -> None:
    """Remove the cancel event for *thread_id* (cleanup after stream ends)."""
    _cancel_events.pop(thread_id, None)
