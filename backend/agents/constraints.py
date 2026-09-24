"""Structured trip constraints — the contract between orchestrator and pipeline.

The orchestrator calls `generate_trip_plans`/`refine_itinerary` with a
`TripConstraints` payload validated by Pydantic. Fields the model doesn't
know can't be silently dropped downstream — the tool call can't be formed.
"""

from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel, Field

SUPPORTED_CURRENCIES = ("USD", "INR", "EUR", "JPY", "GBP", "AUD")


class TripConstraints(BaseModel):
    """Everything the pipeline needs to generate plans — nothing more.

    The orchestrator fills this from conversation; every field is required
    (except the two list fields, which may be empty), so a half-known trip
    can't reach the generator.
    """

    destination: str = Field(min_length=1, description="City or region, e.g. 'Delhi, India'")
    total_days: int = Field(gt=0, le=30, description="Trip length in days")
    budget_amount: float = Field(gt=0, description="TOTAL trip budget (not per-day)")
    budget_currency: Literal["USD", "INR", "EUR", "JPY", "GBP", "AUD"]
    travel_style: Literal["relaxed", "balanced", "adventurous"]
    group_type: Literal["solo", "couple", "family", "friends"]
    dietary_restrictions: list[str] = Field(default_factory=list)
    accessibility_needs: list[str] = Field(default_factory=list)


_DAYS_BEFORE_RE = re.compile(r"(\d{1,2})\s*[-\u2013]?\s*day", re.IGNORECASE)
_DAYS_AFTER_RE = re.compile(r"\b(?:for|of|about|around)\s+(\d{1,2})\s+days\b", re.IGNORECASE)
_WEEK_RE = re.compile(r"\b(?:a|an|one|1)\s+week\b|\b(\d{1,2})\s+weeks?\b", re.IGNORECASE)


def extract_stated_days(text: str | None) -> int | None:
    """Best-effort extraction of a user-stated trip length in days.

    Companion to extract_stated_budget — the stated duration is as much a
    hard constraint as the money, and nothing else in the stack enforced it.
    Matches "5 days", "5-day trip", "for 5 days", "a week" (-> 7), "2 weeks"
    (-> 14). Returns None if nothing is confidently detected. Never raises.
    """
    if not text:
        return None
    try:
        m = _DAYS_BEFORE_RE.search(text) or _DAYS_AFTER_RE.search(text)
        if m:
            days = int(m.group(1))
            if 0 < days <= 30:
                return days
        m = _WEEK_RE.search(text)
        if m:
            weeks = int(m.group(1)) if m.group(1) else 1
            days = weeks * 7
            if 0 < days <= 30:
                return days
    except (ValueError, AttributeError):
        return None
    return None


_CLARIFY_ANSWERS_RE = re.compile(r"<clarify_answers>([\s\S]*?)</clarify_answers>")
_STRIP_CLARIFY_RE = re.compile(r"<clarify_answers>[\s\S]*?(?:</clarify_answers>|$)")
_NUMBER_RE = re.compile(r"[\d][\d,]*(?:\.\d+)?")


def extract_clarify_answers(text: str | None) -> dict:
    """Parse the machine-readable <clarify_answers>{...}</clarify_answers> block
    the chat UI appends to a clarification reply.

    Returns {field: value_or_list} — these are the authoritative answers to
    questions already asked, so the agent never needs to re-ask them.
    Never raises.
    """
    if not text:
        return {}
    m = _CLARIFY_ANSWERS_RE.search(text)
    if not m:
        return {}
    try:
        data = json.loads(m.group(1))
    except (ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def strip_clarify_answers(text: str | None) -> str:
    """Remove the <clarify_answers> block so amount/days regexes can't match
    numbers inside the JSON payload."""
    if not text:
        return text or ""
    return _STRIP_CLARIFY_RE.sub("", text)


def parse_budget_range(value) -> tuple[float | None, float | None]:
    """Extract (min, max) numbers from a budget answer like '₹25,000–₹60,000'.

    One number -> (None, n) treated as an upper bound ('Under ₹25,000').
    Two+     -> (first, last). Returns (None, None) when unparseable.
    """
    if value is None:
        return (None, None)
    text = value if isinstance(value, str) else ", ".join(str(v) for v in value)
    nums = []
    for m in _NUMBER_RE.finditer(text):
        try:
            nums.append(float(m.group(0).replace(",", "")))
        except ValueError:
            continue
    if not nums:
        return (None, None)
    if len(nums) == 1:
        return (None, nums[0])
    return (min(nums[0], nums[-1]), max(nums[0], nums[-1]))
