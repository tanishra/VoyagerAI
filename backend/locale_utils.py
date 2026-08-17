"""Shared locale extraction and i18n utilities."""

from __future__ import annotations

from starlette.requests import Request

SUPPORTED_LOCALES = ("en", "es", "fr", "de", "hi", "ja")

ERROR_MESSAGES: dict[str, dict[str, str]] = {
    "streaming_failed": {
        "en": "Streaming failed: {error}",
        "es": "Error de transmisión: {error}",
        "fr": "Échec du streaming: {error}",
        "de": "Streaming fehlgeschlagen: {error}",
        "hi": "स्ट्रीमिंग विफल: {error}",
        "ja": "ストリーミングに失敗しました: {error}",
    },
    "stream_ended_prematurely": {
        "en": "Stream ended before the agent finished",
        "es": "El stream terminó antes de que el agente finalizara",
        "fr": "Le flux s'est terminé avant la fin de l'agent",
        "de": "Der Stream endete bevor der Agent fertig war",
        "hi": "एजेंट के समाप्त होने से पहले स्ट्रीम समाप्त हो गई",
        "ja": "エージェントが完了する前にストリームが終了しました",
    },
}


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


def get_error_message(key: str, locale: str | None = None, **kwargs: object) -> str:
    """Return a locale-appropriate error message for the given key.

    Falls back to English if the locale is unsupported or the key is missing.
    """
    messages = ERROR_MESSAGES.get(key)
    if messages is None:
        return key
    lang = locale if locale in SUPPORTED_LOCALES else "en"
    template = messages.get(lang, messages.get("en", key))
    return template.format(**kwargs) if kwargs else template
