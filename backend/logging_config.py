"""Structured logging configuration for VoyagerAI.

Supports two formats:
  - "json" (default): structured JSON logs for Datadog / CloudWatch / ELK
  - "text": human-readable plain text for local development

A request-context filter automatically attaches ``request_id`` to every log
record when the ``RequestContextMiddleware`` sets it on the current thread.
"""

from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar
from typing import Any

from pythonjsonlogger import jsonlogger

# Context variable for request-scoped data (works with asyncio)
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_user_id: ContextVar[str | None] = ContextVar("user_id", default=None)
_thread_id: ContextVar[str | None] = ContextVar("thread_id", default=None)


def set_request_context(
    *,
    request_id: str | None = None,
    user_id: str | None = None,
    thread_id: str | None = None,
) -> None:
    """Set request-scoped context values for structured logging."""
    if request_id is not None:
        _request_id.set(request_id)
    if user_id is not None:
        _user_id.set(user_id)
    if thread_id is not None:
        _thread_id.set(thread_id)


def get_request_id() -> str | None:
    return _request_id.get()


def generate_request_id() -> str:
    return uuid.uuid4().hex[:12]


class _ContextFilter(logging.Filter):
    """Inject request-scoped context into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id.get() or "-"
        record.user_id = _user_id.get() or "-"
        record.thread_id = _thread_id.get() or "-"
        return True


def configure_logging(
    *,
    fmt: str = "json",
    level: str = "INFO",
) -> None:
    """Configure root logging with JSON or text format.

    Args:
        fmt: "json" for structured JSON logs, "text" for plain text.
        level: Standard Python log level (DEBUG, INFO, WARNING, ERROR).
    """
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers (from basicConfig or previous calls)
    root.handlers.clear()

    handler = logging.StreamHandler()
    handler.addFilter(_ContextFilter())

    if fmt == "json":
        formatter: logging.Formatter = jsonlogger.JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s "
            "%(request_id)s %(user_id)s %(thread_id)s",
            rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | "
            "req=%(request_id)s user=%(user_id)s | %(message)s",
        )

    handler.setFormatter(formatter)
    root.addHandler(handler)


def get_log_context() -> dict[str, Any]:
    """Return current context values (useful for structured log extra fields)."""
    return {
        "request_id": _request_id.get(),
        "user_id": _user_id.get(),
        "thread_id": _thread_id.get(),
    }
