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


# Native digit scripts → ASCII so every downstream regex sees plain digits.
_DIGIT_TRANSLATE = str.maketrans({
    **{chr(0x0966 + i): str(i) for i in range(10)},   # Devanagari ०-९
    **{chr(0xFF10 + i): str(i) for i in range(10)},   # Full-width ０-９
    **{chr(0x0660 + i): str(i) for i in range(10)},   # Arabic-Indic ٠-٩
})


def normalize_digits(text: str) -> str:
    """Map Devanagari/full-width/Arabic-Indic digits to ASCII in-place."""
    return text.translate(_DIGIT_TRANSLATE)


_DAYS_BEFORE_RE = re.compile(r"(\d{1,2})\s*[-\u2013]?\s*day", re.IGNORECASE)
_DAYS_AFTER_RE = re.compile(r"\b(?:for|of|about|around)\s+(\d{1,2})\s+days\b", re.IGNORECASE)
_WEEK_RE = re.compile(r"\b(?:a|an|one|1)\s+week\b|\b(\d{1,2})\s+weeks?\b", re.IGNORECASE)

# Numeral words per locale (en/es/fr/de/hi/ja) — value -> alternation source.
_NUM_WORDS: dict[int, str] = {
    1: r"one|a|an|un|una|une|ein|eine|einem|einer|एक|一",
    2: r"two|dos|deux|zwei|दो|二",
    3: r"three|tres|trois|drei|तीन|三",
    4: r"four|cuatro|quatre|vier|चार|四",
    5: r"five|cinco|cinq|fünf|पांच|पाँच|五",
    6: r"six|seis|sechs|छह|छः|六",
    7: r"seven|siete|sept|sieben|सात|七",
    8: r"eight|ocho|huit|acht|आठ|八",
    9: r"nine|nueve|neuf|neun|नौ|九",
    10: r"ten|diez|dix|zehn|दस|十",
}

# Unit nouns per locale -> day multiplier. Longer/prefix-sharing alternatives
# FIRST (weekends? before weeks?) so "weekend" can't match the "week" prefix;
# multi-char CJK alternatives before single-char (日間 before 週).
_UNIT_WORDS: list[tuple[str, int]] = [
    (r"fortnights?", 14),
    (r"weekends?", 2),
    (r"日間|days?|días?|jours?|tage?|दिन", 1),
    (r"週間|weeks?|semanas?|semaines?|wochen?|woche|हफ्ता|हफ्ते|सप्ताह|週", 7),
    (r"ヶ月|か月|箇月|months?|mes(?:es)?|mois|monate?|monat|महीना|महीने|माह", 30),
]

# Bare slang that implies a number without one ("a fortnight away" still → 14;
# bare "weekend" is more often a date than a duration, so it stays out).
_BARE_SLANG_RE = re.compile(r"\bfortnights?\b", re.IGNORECASE)

_NUMERAL_ALT = r"\d{1,2}|" + "|".join(w for w in _NUM_WORDS.values())
_UNIT_ALT = "|".join(u for u, _ in _UNIT_WORDS)
_DURATION_RE = re.compile(
    rf"(?P<num>{_NUMERAL_ALT})\s*(?P<unit>{_UNIT_ALT})",
    re.IGNORECASE,
)
_NUM_LOOKUP = {
    word: value
    for value, alt in _NUM_WORDS.items()
    for word in alt.split("|")
}
_UNIT_RES = [(re.compile(rf"(?:{alt})\Z", re.IGNORECASE), mult) for alt, mult in _UNIT_WORDS]


def _multilingual_days(text: str) -> int | None:
    """Scan for '<numeral> <day/week/month noun>' in any supported language."""
    for m in _DURATION_RE.finditer(text):
        raw_num = m.group("num")
        n = int(raw_num) if raw_num.isdigit() else _NUM_LOOKUP.get(raw_num.lower())
        if n is None:
            continue
        mult = next(
            (mult for unit_re, mult in _UNIT_RES if unit_re.match(m.group("unit"))),
            1,
        )
        days = n * mult
        if 0 < days <= 30:
            return days
    if _BARE_SLANG_RE.search(text):
        return 14
    return None


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
        text = normalize_digits(text)
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
        return _multilingual_days(text)
    except (ValueError, AttributeError):
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
    text = normalize_digits(text)
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
