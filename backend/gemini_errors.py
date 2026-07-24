"""Gemini API error classification and retry helper.

Typical usage::

    info = classify_gemini_error(exc)
    if info.retryable:
        await asyncio.sleep(info.retry_delay)
        # retry...
    else:
        raise HTTPException(status_code=info.http_status, detail=info.user_message)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from google.genai import errors as gemini_errors

logger = logging.getLogger("travel_agent.gemini_errors")

RETRYABLE_CODES = {429, 500, 502, 503}
NON_RETRYABLE_AUTH_CODES = {401, 403}

BASE_RETRY_DELAY: float = 1.0
MAX_RETRIES: int = 2


@dataclass
class GeminiErrorInfo:
    category: str = "unknown"
    retryable: bool = False
    http_status: int = 502
    user_message: str = "Gemini API error."
    retry_delay: float = 0.0
    details: str = ""


def classify_gemini_error(exc: Exception) -> GeminiErrorInfo:
    if isinstance(exc, asyncio.TimeoutError):
        return GeminiErrorInfo(
            category="timeout",
            retryable=True,
            http_status=504,
            user_message="Gemini API timed out. Please try again.",
            retry_delay=BASE_RETRY_DELAY,
            details=str(exc),
        )

    if isinstance(exc, gemini_errors.ClientError):
        return _classify_client_error(exc)

    if isinstance(exc, gemini_errors.ServerError):
        return _classify_server_error(exc)

    return GeminiErrorInfo(
        category="unknown",
        retryable=False,
        http_status=502,
        user_message=f"Unexpected Gemini API error: {exc}",
        details=str(exc),
    )


def _classify_client_error(exc: gemini_errors.ClientError) -> GeminiErrorInfo:
    code = exc.code
    status_str = (exc.status or "").upper()
    msg = (exc.message or "").lower()

    if code in NON_RETRYABLE_AUTH_CODES or "auth" in msg or "key" in msg:
        return GeminiErrorInfo(
            category="auth_error",
            retryable=False,
            http_status=401,
            user_message="Invalid or missing Gemini API key. Check your credentials.",
            details=f"{exc.code} {exc.status}: {exc.message}",
        )

    if code == 429:
        if "quota" in msg or "quota" in status_str:
            return GeminiErrorInfo(
                category="quota_exceeded",
                retryable=True,
                http_status=429,
                user_message="Gemini API quota exceeded. Try again later.",
                retry_delay=BASE_RETRY_DELAY * 4,
                details=f"{exc.code} {exc.status}: {exc.message}",
            )
        return GeminiErrorInfo(
            category="rate_limit",
            retryable=True,
            http_status=429,
            user_message="Too many requests. Please slow down and try again.",
            retry_delay=BASE_RETRY_DELAY * 2,
            details=f"{exc.code} {exc.status}: {exc.message}",
        )

    if code == 400:
        safety_keywords = ["safety", "blocked", "harm", "content_filtered", "finish_reason"]
        if any(kw in msg for kw in safety_keywords):
            return GeminiErrorInfo(
                category="content_filtered",
                retryable=False,
                http_status=422,
                user_message="Gemini blocked the request due to safety filters. Try rephrasing your input.",
                details=f"{exc.code} {exc.status}: {exc.message}",
            )
        return GeminiErrorInfo(
            category="invalid_argument",
            retryable=False,
            http_status=400,
            user_message=f"Invalid request to Gemini API: {exc.message}",
            details=f"{exc.code} {exc.status}: {exc.message}",
        )

    if code in RETRYABLE_CODES:
        return GeminiErrorInfo(
            category="server_error",
            retryable=True,
            http_status=502,
            user_message="Gemini API temporarily unavailable. Retrying...",
            retry_delay=BASE_RETRY_DELAY,
            details=f"{exc.code} {exc.status}: {exc.message}",
        )

    return GeminiErrorInfo(
        category="unknown",
        retryable=False,
        http_status=502,
        user_message=f"Gemini API error ({code}): {exc.message}",
        details=f"{exc.code} {exc.status}: {exc.message}",
    )


def _classify_server_error(exc: gemini_errors.ServerError) -> GeminiErrorInfo:
    code = exc.code
    msg = (exc.message or "").lower()

    if "overloaded" in msg or code == 503:
        return GeminiErrorInfo(
            category="model_overloaded",
            retryable=True,
            http_status=503,
            user_message="Gemini model is overloaded. Please try again.",
            retry_delay=BASE_RETRY_DELAY * 2,
            details=f"{exc.code} {exc.status}: {exc.message}",
        )

    return GeminiErrorInfo(
        category="server_error",
        retryable=True,
        http_status=502,
        user_message="Gemini API server error. Retrying...",
        retry_delay=BASE_RETRY_DELAY,
        details=f"{exc.code} {exc.status}: {exc.message}",
    )


async def run_with_retry(
    operation_name: str,
    coro_factory,
    max_retries: int = MAX_RETRIES,
) -> any:
    last_error: Exception | None = None
    for attempt in range(1 + max_retries):
        try:
            return await coro_factory()
        except Exception as exc:
            last_error = exc
            info = classify_gemini_error(exc)
            if not info.retryable:
                logger.error("%s — non-retryable error: %s", operation_name, info.details)
                raise
            if attempt < max_retries:
                delay = info.retry_delay * (2**attempt)
                logger.warning(
                    "%s — attempt %d/%d failed (%s). Retrying in %.1fs...",
                    operation_name, attempt + 1, max_retries, info.category, delay,
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "%s — failed after %d attempts. Last error: %s",
                    operation_name, max_retries + 1, info.details,
                )
    raise last_error  # type: ignore[misc]
