"""Tests for Gemini API error classification and retry helper."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from google.genai import errors as gemini_errors

from gemini_errors import GeminiErrorInfo, classify_gemini_error, run_with_retry


def _client_error(code: int, message: str, status: str = "") -> gemini_errors.ClientError:
    return gemini_errors.ClientError(
        code,
        {"error": {"code": code, "message": message, "status": status or ""}},
    )


def _server_error(code: int, message: str, status: str = "") -> gemini_errors.ServerError:
    return gemini_errors.ServerError(
        code,
        {"error": {"code": code, "message": message, "status": status or ""}},
    )


class TestClassifyRateLimit:
    def test_rate_limit_429(self):
        info = classify_gemini_error(_client_error(429, "Rate limit exceeded", "RESOURCE_EXHAUSTED"))
        assert info.category == "rate_limit"
        assert info.retryable is True
        assert info.http_status == 429
        assert info.retry_delay > 0

    def test_quota_exceeded(self):
        info = classify_gemini_error(_client_error(429, "Quota exceeded", "QUOTA_EXHAUSTED"))
        assert info.category == "quota_exceeded"
        assert info.retryable is True
        assert info.retry_delay >= 4.0


class TestClassifyAuthError:
    def test_auth_error_401(self):
        info = classify_gemini_error(_client_error(401, "API key invalid", "UNAUTHENTICATED"))
        assert info.category == "auth_error"
        assert info.retryable is False
        assert info.http_status == 401

    def test_auth_error_403(self):
        info = classify_gemini_error(_client_error(403, "Permission denied", "PERMISSION_DENIED"))
        assert info.category == "auth_error"
        assert info.retryable is False
        assert info.http_status == 401

    def test_auth_error_keyword(self):
        info = classify_gemini_error(_client_error(400, "API key not valid"))
        assert info.category == "auth_error"
        assert info.retryable is False


class TestClassifyContentFiltered:
    def test_safety_keyword(self):
        info = classify_gemini_error(_client_error(400, "finish_reason safety", "INVALID_ARGUMENT"))
        assert info.category == "content_filtered"
        assert info.retryable is False
        assert info.http_status == 422

    def test_blocked_keyword(self):
        info = classify_gemini_error(_client_error(400, "Content blocked by safety filters"))
        assert info.category == "content_filtered"
        assert info.retryable is False


class TestClassifyServerError:
    def test_model_overloaded(self):
        info = classify_gemini_error(_server_error(503, "Model overloaded", "UNAVAILABLE"))
        assert info.category == "model_overloaded"
        assert info.retryable is True
        assert info.http_status == 503

    def test_generic_server_error(self):
        info = classify_gemini_error(_server_error(500, "Internal error", "INTERNAL"))
        assert info.category == "server_error"
        assert info.retryable is True
        assert info.http_status == 502


class TestClassifyTimeout:
    def test_timeout(self):
        info = classify_gemini_error(asyncio.TimeoutError("Timed out"))
        assert info.category == "timeout"
        assert info.retryable is True
        assert info.http_status == 504


class TestClassifyUnknown:
    def test_unknown_exception(self):
        info = classify_gemini_error(RuntimeError("Something went wrong"))
        assert info.category == "unknown"
        assert info.retryable is False
        assert info.http_status == 502

    def test_unknown_client_error(self):
        info = classify_gemini_error(_client_error(418, "I'm a teapot"))
        assert info.category == "unknown"
        assert info.retryable is False
        assert info.http_status == 502


@pytest.mark.asyncio
class TestRunWithRetry:
    async def test_successful_call_returns_result(self):
        async def ok():
            return 42

        result = await run_with_retry("test", ok)
        assert result == 42

    async def test_retry_on_retryable_error_then_succeeds(self):
        call_count = 0

        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise _client_error(429, "rate limit")
            return "success"

        result = await run_with_retry("test", flaky, max_retries=2)
        assert result == "success"
        assert call_count == 2

    async def test_non_retryable_error_raises_immediately(self):
        async def fail():
            raise _client_error(401, "auth error")

        with pytest.raises(gemini_errors.ClientError):
            await run_with_retry("test", fail, max_retries=2)

    async def test_retry_exhaustion_raises_last_error(self):
        call_count = 0

        async def always_fail():
            nonlocal call_count
            call_count += 1
            raise _client_error(429, "rate limit")

        with pytest.raises(gemini_errors.ClientError):
            await run_with_retry("test", always_fail, max_retries=2)
        assert call_count == 3

    async def test_does_not_retry_on_runtime_error(self):
        call_count = 0

        async def fail():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("unexpected")

        with pytest.raises(RuntimeError):
            await run_with_retry("test", fail, max_retries=2)
        assert call_count == 1
