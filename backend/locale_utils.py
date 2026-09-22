"""Shared locale extraction and i18n utilities."""

from __future__ import annotations

from starlette.requests import Request

SUPPORTED_LOCALES = ("en", "es", "fr", "de", "hi", "ja")

ERROR_MESSAGES: dict[str, dict[str, str]] = {
    "streaming_failed": {
        "en": "Something went wrong while generating your answer. Please try again.",
        "es": "Algo salió mal al generar tu respuesta. Inténtalo de nuevo.",
        "fr": "Une erreur s'est produite lors de la génération de la réponse. Veuillez réessayer.",
        "de": "Beim Generieren der Antwort ist ein Fehler aufgetreten. Bitte versuche es erneut.",
        "hi": "उत्तर जनरेट करते समय कुछ गड़बड़ हुई। कृपया पुनः प्रयास करें।",
        "ja": "回答の生成中に問題が発生しました。もう一度お試しください。",
    },
    "provider_busy": {
        "en": "The AI service is at capacity right now. Please try again in a moment.",
        "es": "El servicio de IA está saturado ahora mismo. Inténtalo de nuevo en un momento.",
        "fr": "Le service IA est saturé pour le moment. Veuillez réessayer dans un instant.",
        "de": "Der KI-Dienst ist derzeit ausgelastet. Bitte versuche es gleich erneut.",
        "hi": "AI सेवा अभी अत्यधिक व्यस्त है। कृपया कुछ देर बाद पुनः प्रयास करें।",
        "ja": "AIサービスが現在混雑しています。しばらくしてからもう一度お試しください。",
    },
    "connection_failed": {
        "en": "Connection problem. Please check your network and try again.",
        "es": "Problema de conexión. Comprueba tu red e inténtalo de nuevo.",
        "fr": "Problème de connexion. Veuillez vérifier votre réseau et réessayer.",
        "de": "Verbindungsproblem. Bitte prüfe dein Netzwerk und versuche es erneut.",
        "hi": "कनेक्शन समस्या। कृपया अपना नेटवर्क जांचें और पुनः प्रयास करें।",
        "ja": "接続に問題があります。ネットワークを確認してもう一度お試しください。",
    },
    "generic_error": {
        "en": "Something went wrong. Please try again.",
        "es": "Algo salió mal. Inténtalo de nuevo.",
        "fr": "Une erreur s'est produite. Veuillez réessayer.",
        "de": "Etwas ist schiefgelaufen. Bitte versuche es erneut.",
        "hi": "कुछ गड़बड़ हुई। कृपया पुनः प्रयास करें।",
        "ja": "問題が発生しました。もう一度お試しください。",
    },
    "tool_unavailable": {
        "en": "A tool became temporarily unavailable.",
        "es": "Una herramienta no está disponible temporalmente.",
        "fr": "Un outil est temporairement indisponible.",
        "de": "Ein Tool ist vorübergehend nicht verfügbar.",
        "hi": "एक टूल अस्थायी रूप से अनुपलब्ध है।",
        "ja": "ツールが一時的に利用できません。",
    },
    "stream_ended_prematurely": {
        "en": "Stream ended before the agent finished",
        "es": "El stream terminó antes de que el agente finalizara",
        "fr": "Le flux s'est terminé avant la fin de l'agent",
        "de": "Der Stream endete bevor der Agent fertig war",
        "hi": "एजेंट के समाप्त होने से पहले स्ट्रीम समाप्त हो गई",
        "ja": "エージェントが完了する前にストリームが終了しました",
    },
    "injection_blocked": {
        "en": "Your message was blocked because it appears to contain a prompt injection attempt. Please rephrase your request.",
        "es": "Tu mensaje fue bloqueado porque parece contener un intento de inyección de prompt. Por favor, reformula tu solicitud.",
        "fr": "Votre message a été bloqué car il semble contenir une tentative d'injection de prompt. Veuillez reformuler votre demande.",
        "de": "Ihre Nachricht wurde blockiert, da sie offenbar einen Prompt-Injection-Versuch enthält. Bitte formulieren Sie Ihre Anfrage um.",
        "hi": "आपका संदेश अवरुद्ध कर दिया गया है क्योंकि इसमें प्रॉम्प्ट इंजेक्शन प्रयास है। कृपया अपनी अनुरोध को फिर से तैयार करें।",
        "ja": "プロンプトインジェクションの試みが含まれているため、メッセージがブロックされました。リクエストを言い換えてください。",
    },
    "cooldown_active": {
        "en": "Your account is temporarily restricted due to repeated policy violations. Please try again later.",
        "es": "Su cuenta está temporalmente restringida debido a violaciones repetidas de la política. Por favor, inténtelo más tarde.",
        "fr": "Votre compte est temporairement restreint en raison de violations répétées de la politique. Veuillez réessayer plus tard.",
        "de": "Ihr Konto ist aufgrund wiederholter Richtlinienverstöße vorübergehend eingeschränkt. Bitte versuchen Sie es später erneut.",
        "hi": "बार-बार नीति उल्लंघन के कारण आपका खाता अस्थायी रूप से प्रतिबंधित है। कृपया बाद में पुनः प्रयास करें।",
        "ja": "ポリシー違反の繰り返しにより、アカウントは一時的に制限されています。後でもう一度お試しください。",
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


_PROVIDER_PATTERNS = (
    "ratelimit", "rate_limit", "rate limit", "insufficient", "credit",
    "quota", "billing", "authentication", "api key", "capacity", "overloaded",
)
_CONNECTION_PATTERNS = (
    "timeout", "timed out", "connection", "connect", "dns", "network",
    "econnrefused", "econnreset",
)


def classify_exception(exc: BaseException) -> str:
    """Map an exception to a user-facing ERROR_MESSAGES key.

    Never exposes exception text — only a bucket: provider limits/billing,
    connectivity, or a generic fallback.
    """
    text = f"{type(exc).__name__} {exc}".lower()
    if any(p in text for p in _PROVIDER_PATTERNS):
        return "provider_busy"
    if any(p in text for p in _CONNECTION_PATTERNS):
        return "connection_failed"
    return "generic_error"


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
