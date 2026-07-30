"""Prompt injection sanitization — strip control tokens from user-supplied text."""

from __future__ import annotations

import logging
import re

logger = logging.getLogger("travel_agent")

_CONTROL_TOKENS = [
    "<|im_start|>",
    "<|im_end|>",
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


def sanitize_prompt_input(
    text: str | None,
    field_name: str = "unknown",
) -> str | None:
    """Remove known prompt-injection markers and unicode control characters.

    Returns the cleaned string (or ``None`` if ``text`` was ``None``).
    Logs a WARNING for each field where content was stripped.
    """
    if text is None:
        return None
    if not isinstance(text, str):
        return text

    for pattern in CONTROL_TOKEN_PATTERNS:
        replaced = pattern.sub("[blocked]", text)
        if replaced != text:
            logger.warning(
                "Prompt injection token stripped from field '%s'",
                field_name,
            )
            text = replaced

    stripped_count = len(UNICODE_CONTROL_RE.findall(text))
    if stripped_count:
        logger.warning(
            "Stripped %d unicode control character(s) from field '%s'",
            stripped_count,
            field_name,
        )
        text = UNICODE_CONTROL_RE.sub("", text)

    return text
