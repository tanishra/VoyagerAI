"""Prompt injection sanitization — layered defense against known attack patterns.

Layer 1 (this file): fast regex-based detection and sanitization.
- Control tokens (, [INST], etc.) → confidence=low, sanitize inline
- Phrase patterns (instruction override, role-play, extraction) → confidence=high, route to guard model
- Unicode control characters → always stripped

Layer 2 (guard.py): LLM-based classifier for borderline/high-confidence matches.
Layer 3 (security_store.py): strike tracking and cooldown enforcement.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Literal

logger = logging.getLogger("travel_agent")

# ---------------------------------------------------------------------------
# Confidence levels
# ---------------------------------------------------------------------------

Confidence = Literal["none", "low", "high"]

# ---------------------------------------------------------------------------
# Control tokens (existing — unchanged behavior, confidence=low)
# ---------------------------------------------------------------------------

_CONTROL_TOKENS = [
    "<|im_start|>",
    "<|im_end|>",
    "<|im|>",
    "<|system|>",
    "<|user|>",
    "<|assistant|>",
    "<|model|>",
    "[INST]",
    "[/INST]",
    "<<SYS>>",
    "<</SYS>>",
]

CONTROL_TOKEN_PATTERNS: list[re.Pattern] = [
    re.compile(re.escape(t), re.IGNORECASE) for t in _CONTROL_TOKENS
]

CONTROL_TOKEN_PATTERNS.extend([
    re.compile(r"##?\s*(System|User|Assistant|Instruction)(\s|:|\n)", re.IGNORECASE),
])

# ---------------------------------------------------------------------------
# Phrase-based injection patterns (new — confidence=high)
# ---------------------------------------------------------------------------

_PHRASE_PATTERNS: dict[str, list[re.Pattern]] = {
    "instruction_override": [
        re.compile(r"ignore\s+(?:all\s+)?(?:previous|above|prior\s+)?(instructions?|rules?|prompts?)", re.IGNORECASE),
        re.compile(r"ignore\s+(all\s+)?(previous|above|prior)\s+(instructions?|rules?|prompts?)", re.IGNORECASE),
        re.compile(r"disregard\s+(your|the|all)\s+(system|rules?|instructions?|guidelines)", re.IGNORECASE),
        re.compile(r"override\s+(your|the)\s+(programming|instructions?|rules?|system)", re.IGNORECASE),
        re.compile(r"new\s+instructions?\s*:", re.IGNORECASE),
        re.compile(r"forget\s+(everything|all\s+your|your\s+(previous|prior))\s+(?:and\s+all\s+your\s+(?:previous|prior)\s+)?(instructions?|rules?|prompts?)", re.IGNORECASE),
        re.compile(r"do\s+not\s+follow\s+(your|the|any)\s+(rules?|instructions?|guidelines)", re.IGNORECASE),
        re.compile(r"you\s+(no\s+longer|don'?t\s+(need\s+to|have\s+to))\s+(follow|obey|adhere\s+to)\s+(your|the|any)\s+(rules?|instructions?|guidelines)", re.IGNORECASE),
    ],
    "role_play_jailbreak": [
        re.compile(r"you\s+are\s+now\s+(DAN|a\s+(?:free|unrestricted|liberated)\s+(?:AI|model|assistant))", re.IGNORECASE),
        re.compile(r"pretend\s+you\s+(are|have)\s+(no|none)\s+(restrictions?|rules?|guidelines|limits?)", re.IGNORECASE),
        re.compile(r"act\s+as\s+if\s+you\s+(have\s+no|are\s+without)\s+(restrictions?|rules?|limits?)", re.IGNORECASE),
        re.compile(r"(enter|activate|enable|switch\s+to)\s+(developer|debug|jailbreak|god|root|admin)\s+mode", re.IGNORECASE),
        re.compile(r"pretend\s+to\s+be\s+(an?\s+)?(?:unrestricted|unfiltered|uncensored|free)\s+(AI|model|assistant|LLM)", re.IGNORECASE),
        re.compile(r"simulate\s+(a\s+)?(?:model|AI|assistant)\s+(with|without|that\s+has\s+no)\s+(restrictions?|filters?|guidelines|safety)", re.IGNORECASE),
    ],
    "extraction_attempt": [
        re.compile(r"(repeat|print|show|reveal|display|output)\s+(the\s+)?(text|everything|all)\s+(above|before\s+this|that\s+comes\s+before)", re.IGNORECASE),
        re.compile(r"what\s+(is|are)\s+your\s+(system\s+)?(prompt|instructions?|rules?|programming|guidelines)", re.IGNORECASE),
        re.compile(r"(show|reveal|print|share|give|tell\s+me)\s+(me\s+)?your\s+(system\s+)?(prompt|instructions?|rules?|programming|guidelines|config)", re.IGNORECASE),
        re.compile(r"repeat\s+(everything|all\s+the\s+text)\s+(above|before)\s+(this|your\s+response)", re.IGNORECASE),
        re.compile(r"(copy|paste|reproduce)\s+(your|the)\s+(system\s+)?(prompt|instructions?|rules?|initial\s+message)", re.IGNORECASE),
    ],
    "encoding_trick": [
        re.compile(r"(decode|execute|run|interpret)\s+(this|the\s+following)\s+(base64|encoded|b64|hex)\s*[:\s]", re.IGNORECASE),
        re.compile(r"[A-Za-z0-9+/]{60,}={0,2}\s*\n\s*(?:decode|run|execute|interpret)\s+this", re.IGNORECASE),
    ],
}

_ALL_PHRASE_PATTERNS: list[tuple[str, re.Pattern]] = [
    (cat, pat) for cat, pats in _PHRASE_PATTERNS.items() for pat in pats
]

# ---------------------------------------------------------------------------
# Unicode control characters (existing — unchanged)
# ---------------------------------------------------------------------------

_UNICODE_CONTROL_CHARS = (
    "\u0000-\u0008"    # null, etc
    "\u000b"           # vertical tab
    "\u000c"           # form feed
    "\u000e-\u001f"    # shift out through unit separator
    "\u200b-\u200f"    # zero-width space through right-to-left mark
    "\u2028-\u202f"    # line/paragraph separator through narrow no-break space
    "\u2060-\u206f"    # word joiner through nominal digits
    "\ufeff"           # BOM
    "\ufff0-\uffff"    # specials
)

UNICODE_CONTROL_RE = re.compile(f"[{_UNICODE_CONTROL_CHARS}]")


# ---------------------------------------------------------------------------
# SanitizeResult — richer return type
# ---------------------------------------------------------------------------

@dataclass
class SanitizeResult:
    """Result of sanitizing user input.

    Attributes:
        text: cleaned text (safe to pass to LLM regardless of confidence)
        confidence: "none" (no match), "low" (control-token only, handled),
                    "high" (phrase-pattern match, should route to guard model)
        matched_categories: list of categories that matched (e.g. ["instruction_override"])
    """

    text: str | None
    confidence: Confidence = "none"
    matched_categories: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Main sanitization functions
# ---------------------------------------------------------------------------

def sanitize_prompt_input(
    text: str | None,
    field_name: str = "unknown",
) -> str | None:
    """Remove known prompt-injection markers and unicode control characters.

    Backward-compatible wrapper that returns just the cleaned text.
    Logs a WARNING for each field where content was stripped.
    """
    return sanitize_prompt_input_detailed(text, field_name).text


def sanitize_prompt_input_detailed(
    text: str | None,
    field_name: str = "unknown",
) -> SanitizeResult:
    """Sanitize user input and return a detailed result with confidence level.

    - Control tokens → confidence=low (sanitize inline, no guard model needed)
    - Phrase patterns → confidence=high (caller should route to guard model)
    - Unicode control chars → always stripped silently
    """
    if text is None:
        return SanitizeResult(text=None)
    if not isinstance(text, str):
        return SanitizeResult(text=text)

    matched_categories: list[str] = []
    confidence: Confidence = "none"

    # --- Layer 1a: Control tokens (confidence=low) ---
    for pattern in CONTROL_TOKEN_PATTERNS:
        replaced = pattern.sub("[blocked]", text)
        if replaced != text:
            logger.warning(
                "Prompt injection token stripped from field '%s'",
                field_name,
            )
            text = replaced
            if confidence == "none":
                confidence = "low"

    # --- Layer 1b: Phrase patterns (confidence=high) ---
    for category, pattern in _ALL_PHRASE_PATTERNS:
        if pattern.search(text):
            if category not in matched_categories:
                matched_categories.append(category)
            logger.warning(
                "Prompt injection phrase matched in field '%s': category=%s",
                field_name,
                category,
            )

    if matched_categories:
        confidence = "high"

    # --- Layer 1c: Unicode control characters (always stripped) ---
    stripped_count = len(UNICODE_CONTROL_RE.findall(text))
    if stripped_count:
        logger.warning(
            "Stripped %d unicode control character(s) from field '%s'",
            stripped_count,
            field_name,
        )
        text = UNICODE_CONTROL_RE.sub("", text)

    return SanitizeResult(
        text=text,
        confidence=confidence,
        matched_categories=matched_categories,
    )


def scan_text_for_injection(text: str | None) -> SanitizeResult:
    """Scan text for injection patterns without modifying it.

    Used for tool outputs (search results, PDF text) where we want to
    detect injection attempts but not sanitize the content itself —
    the caller wraps it in an untrusted-content frame instead.
    """
    if text is None or not isinstance(text, str):
        return SanitizeResult(text=text)

    matched_categories: list[str] = []

    for pattern in CONTROL_TOKEN_PATTERNS:
        if pattern.search(text):
            if "control_token" not in matched_categories:
                matched_categories.append("control_token")

    for category, pattern in _ALL_PHRASE_PATTERNS:
        if pattern.search(text):
            if category not in matched_categories:
                matched_categories.append(category)

    confidence: Confidence = "high" if matched_categories else "none"
    if "control_token" in matched_categories and len(matched_categories) == 1:
        confidence = "low"

    return SanitizeResult(
        text=text,
        confidence=confidence,
        matched_categories=matched_categories,
    )
