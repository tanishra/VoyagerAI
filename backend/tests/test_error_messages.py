"""User-facing error messages: no technical text leaks to clients."""

from __future__ import annotations

import pytest

from locale_utils import classify_exception, get_error_message


class TestClassifyException:
    def test_rate_limit_maps_to_provider_busy(self):
        exc = RuntimeError("litellm.RateLimitError: OpenAIException - You have no credits remaining")
        assert classify_exception(exc) == "provider_busy"

    def test_quota_and_billing_map_to_provider(self):
        assert classify_exception(Exception("quota exceeded")) == "provider_busy"
        assert classify_exception(Exception("billing issue detected")) == "provider_busy"

    def test_timeout_maps_to_connection(self):
        assert classify_exception(TimeoutError("request timed out")) == "connection_failed"

    def test_connection_refused_maps_to_connection(self):
        assert classify_exception(ConnectionError("connection refused")) == "connection_failed"

    def test_generic_maps_to_generic(self):
        assert classify_exception(ValueError("some internal bug")) == "generic_error"

    def test_exception_text_never_in_output(self):
        exc = RuntimeError("litellm.RateLimitError: no credits at https://platform.openai.com/billing")
        key = classify_exception(exc)
        msg = get_error_message(key, "en")
        assert "litellm" not in msg
        assert "credits" not in msg
        assert "platform.openai.com" not in msg


class TestLocalizedErrorMessages:
    @pytest.mark.parametrize("locale", ["en", "es", "fr", "de", "hi", "ja"])
    def test_all_keys_have_all_locales(self, locale):
        for key in ("streaming_failed", "provider_busy", "connection_failed", "generic_error", "tool_unavailable"):
            msg = get_error_message(key, locale)
            assert msg and msg != key

    def test_unsupported_locale_falls_back_to_en(self):
        assert get_error_message("provider_busy", "xx") == get_error_message("provider_busy", "en")

    def test_streaming_failed_has_no_error_placeholder(self):
        msg = get_error_message("streaming_failed", "en")
        assert "{error}" not in msg
