"""LangSmith tracing configuration."""

from __future__ import annotations

import os

from langsmith import Client

LANGSMITH_API_KEY: str | None = os.getenv("LANGSMITH_API_KEY")
LANGSMITH_PROJECT: str = os.getenv("LANGSMITH_PROJECT", "voyagerai")

client = Client(
    api_key=LANGSMITH_API_KEY,
) if LANGSMITH_API_KEY else None

__all__ = ["client", "LANGSMITH_PROJECT"]
