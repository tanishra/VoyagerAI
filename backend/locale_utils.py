"""Shared locale extraction utilities."""

from __future__ import annotations

from starlette.requests import Request

SUPPORTED_LOCALES = ("en", "es", "fr", "de", "hi", "ja")


def extract_locale(request: Request, body_locale: str | None = None) -> str | None:
    """Extract locale from a body field or Accept-Language header.

    Priority: explicit body field > Accept-Language header > None.
    """
    locale = body_locale
    if not locale:
        accept_lang = request.headers.get("accept-language", "")
        for part in accept_lang.split(","):
            lang = part.strip().split(";")[0].strip().lower()
            for supported in SUPPORTED_LOCALES:
                if lang == supported or lang.startswith(supported + "-"):
                    locale = supported
                    break
            if locale:
                break
    return locale
