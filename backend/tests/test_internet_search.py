"""Tests for the subagent internet_search tool — production-grade error handling,
retries, timeout, input validation, and Anthropic-compliant output formatting.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from agents.tools.internet import (
    _format_search_results,
    _make_cache_key,
    _search_with_retry,
    get_internet_tools,
    internet_search,
)
from research_cache import research_cache


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tavily_response(results: list[dict]) -> dict:
    return {"results": results}


def _make_result(title: str, url: str, content: str, score: float = 0.9) -> dict:
    return {"title": title, "url": url, "content": content, "score": score}


@pytest.fixture(autouse=True)
def _clear_research_cache():
    """Clear research cache before each test (sync wrapper)."""
    import asyncio
    loop = asyncio.new_event_loop()
    loop.run_until_complete(research_cache.invalidate_all())
    yield
    loop.run_until_complete(research_cache.invalidate_all())
    loop.close()


# ---------------------------------------------------------------------------
# Core functionality
# ---------------------------------------------------------------------------

class TestInternetSearchCore:
    @pytest.mark.asyncio
    async def test_internet_search_returns_formatted_results(self):
        mock_tavily = MagicMock()
        mock_tavily.search.return_value = _make_tavily_response([
            _make_result("Tokyo Hotels", "https://example.com/hotels", "Great hotels in Tokyo."),
        ])
        with patch("agents.tools.internet._get_tavily", return_value=mock_tavily):
            result = await internet_search.ainvoke({"query": "Tokyo hotels"})
            assert "Title: Tokyo Hotels" in result
            assert "URL: https://example.com/hotels" in result
            assert "Content: Great hotels in Tokyo." in result
            assert "Score:" not in result

    @pytest.mark.asyncio
    async def test_internet_search_caps_max_results_at_10(self):
        mock_tavily = MagicMock()
        mock_tavily.search.return_value = _make_tavily_response([])
        with patch("agents.tools.internet._get_tavily", return_value=mock_tavily):
            await internet_search.ainvoke({"query": "test", "max_results": 50})
            call_kwargs = mock_tavily.search.call_args.kwargs
            assert call_kwargs["max_results"] == 10

    @pytest.mark.asyncio
    async def test_internet_search_no_api_key(self):
        with patch("agents.tools.internet._get_tavily", return_value=None):
            result = await internet_search.ainvoke({"query": "test"})
            assert "unavailable" in result.lower()
            assert "TAVILY_API_KEY" in result


# ---------------------------------------------------------------------------
# Error handling & retries
# ---------------------------------------------------------------------------

class TestInternetSearchErrors:
    @pytest.mark.asyncio
    async def test_internet_search_retry_on_transient_error(self):
        mock_tavily = MagicMock()
        mock_tavily.search.side_effect = [
            ConnectionError("Network error"),
            _make_tavily_response([_make_result("OK", "https://example.com", "Found.")]),
        ]
        with patch("agents.tools.internet._get_tavily", return_value=mock_tavily), \
             patch("agents.tools.internet._RETRY_DELAYS", [0.01, 0.01]):
            result = await internet_search.ainvoke({"query": "test"})
            assert "Title: OK" in result
            assert mock_tavily.search.call_count == 2

    @pytest.mark.asyncio
    async def test_internet_search_retry_exhausted(self):
        mock_tavily = MagicMock()
        mock_tavily.search.side_effect = ConnectionError("Persistent error")
        with patch("agents.tools.internet._get_tavily", return_value=mock_tavily), \
             patch("agents.tools.internet._RETRY_DELAYS", [0.01, 0.01]):
            result = await internet_search.ainvoke({"query": "test"})
            assert "failed" in result.lower()
            assert "proceed with available information" in result.lower()
            assert mock_tavily.search.call_count == 3

    @pytest.mark.asyncio
    async def test_internet_search_timeout(self):
        mock_tavily = MagicMock()

        def slow_search(**kwargs):
            import time
            time.sleep(20)
            return {}

        mock_tavily.search.side_effect = slow_search
        with patch("agents.tools.internet._get_tavily", return_value=mock_tavily), \
             patch("agents.tools.internet._SEARCH_TIMEOUT", 0.1), \
             patch("agents.tools.internet._RETRY_DELAYS", [0.01, 0.01]):
            result = await internet_search.ainvoke({"query": "test"})
            assert "failed" in result.lower()

    @pytest.mark.asyncio
    async def test_internet_search_logs_errors(self):
        mock_tavily = MagicMock()
        mock_tavily.search.side_effect = ConnectionError("error")
        with patch("agents.tools.internet._get_tavily", return_value=mock_tavily), \
             patch("agents.tools.internet._RETRY_DELAYS", [0.01, 0.01]), \
             patch("agents.tools.internet.logger") as mock_logger:
            await internet_search.ainvoke({"query": "test"})
            assert mock_logger.warning.call_count >= 3


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestInternetSearchEdgeCases:
    @pytest.mark.asyncio
    async def test_internet_search_empty_query(self):
        result = await internet_search.ainvoke({"query": ""})
        assert result == "Query must not be empty."

    @pytest.mark.asyncio
    async def test_internet_search_whitespace_query(self):
        result = await internet_search.ainvoke({"query": "   "})
        assert result == "Query must not be empty."

    @pytest.mark.asyncio
    async def test_internet_search_malformed_response(self):
        mock_tavily = MagicMock()
        mock_tavily.search.return_value = _make_tavily_response([
            {"title": "Has Title", "url": "https://example.com"},
            {"url": "https://example.com/2", "content": "Has content"},
            {"foo": "bar"},
        ])
        with patch("agents.tools.internet._get_tavily", return_value=mock_tavily):
            result = await internet_search.ainvoke({"query": "test"})
            assert "Title: Has Title" in result
            assert "Title: Untitled" in result
            assert "URL: https://example.com/2" in result
            assert "Content:" in result


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

class TestFormatSearchResults:
    def test_format_search_results_missing_keys(self):
        results = _make_tavily_response([{"foo": "bar"}])
        out = _format_search_results(results)
        assert "Title: Untitled" in out
        assert "URL:" in out
        assert "Content:" in out

    def test_format_search_results_empty(self):
        results = _make_tavily_response([])
        assert _format_search_results(results) == "No results found."


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------

class TestInternetToolsRegistration:
    def test_get_internet_tools_returns_internet_search(self):
        tools = get_internet_tools()
        assert len(tools) == 1
        assert tools[0].name == "internet_search"


# ---------------------------------------------------------------------------
# Caching integration
# ---------------------------------------------------------------------------

class TestInternetSearchCaching:
    @pytest.mark.asyncio
    async def test_search_caches_result_on_success(self):
        mock_tavily = MagicMock()
        mock_tavily.search.return_value = _make_tavily_response([
            _make_result("Tokyo Hotels", "https://example.com/hotels", "Great hotels."),
        ])
        with patch("agents.tools.internet._get_tavily", return_value=mock_tavily), \
             patch("agents.tools.internet.settings") as mock_settings:
            mock_settings.RESEARCH_CACHE_ENABLED = True
            mock_settings.RESEARCH_CACHE_TTL_HOURS = 24
            result = await internet_search.ainvoke({"query": "Tokyo hotels"})
            assert "Title: Tokyo Hotels" in result
            cache_key = _make_cache_key("Tokyo hotels", "general", 5)
            cached = await research_cache.get(cache_key)
            assert cached is not None
            assert "Title: Tokyo Hotels" in cached

    @pytest.mark.asyncio
    async def test_search_returns_cached_on_hit(self):
        cache_key = _make_cache_key("Paris visa", "general", 5)
        await research_cache.set(cache_key, "Title: Cached Result\nURL: https://cached.com\nContent: Cached.")
        mock_tavily = MagicMock()
        with patch("agents.tools.internet._get_tavily", return_value=mock_tavily), \
             patch("agents.tools.internet.settings") as mock_settings:
            mock_settings.RESEARCH_CACHE_ENABLED = True
            mock_settings.RESEARCH_CACHE_TTL_HOURS = 24
            result = await internet_search.ainvoke({"query": "Paris visa"})
            assert "Cached Result" in result
            mock_tavily.search.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_does_not_cache_errors(self):
        mock_tavily = MagicMock()
        mock_tavily.search.side_effect = ConnectionError("Persistent error")
        with patch("agents.tools.internet._get_tavily", return_value=mock_tavily), \
             patch("agents.tools.internet._RETRY_DELAYS", [0.01, 0.01]), \
             patch("agents.tools.internet.settings") as mock_settings:
            mock_settings.RESEARCH_CACHE_ENABLED = True
            mock_settings.RESEARCH_CACHE_TTL_HOURS = 24
            result = await internet_search.ainvoke({"query": "error test"})
            assert "failed" in result.lower()
            cache_key = _make_cache_key("error test", "general", 5)
            cached = await research_cache.get(cache_key)
            assert cached is None

    @pytest.mark.asyncio
    async def test_different_topics_get_different_cache_entries(self):
        mock_tavily = MagicMock()
        mock_tavily.search.side_effect = [
            _make_tavily_response([_make_result("News Result", "https://news.com", "News.")]),
            _make_tavily_response([_make_result("General Result", "https://general.com", "General.")]),
        ]
        with patch("agents.tools.internet._get_tavily", return_value=mock_tavily), \
             patch("agents.tools.internet.settings") as mock_settings:
            mock_settings.RESEARCH_CACHE_ENABLED = True
            mock_settings.RESEARCH_CACHE_TTL_HOURS = 24
            result1 = await internet_search.ainvoke({"query": "Tokyo", "topic": "news"})
            result2 = await internet_search.ainvoke({"query": "Tokyo", "topic": "general"})
            assert "News Result" in result1
            assert "General Result" in result2
            assert mock_tavily.search.call_count == 2

    @pytest.mark.asyncio
    async def test_quick_web_lookup_caches_result(self):
        from agents.tools.internet import quick_web_lookup, reset_orchestrator_search_count
        reset_orchestrator_search_count()
        mock_tavily = MagicMock()
        mock_tavily.search.return_value = _make_tavily_response([
            _make_result("Quick Result", "https://quick.com", "Quick answer."),
        ])
        with patch("agents.tools.internet._get_tavily", return_value=mock_tavily), \
             patch("agents.tools.internet.settings") as mock_settings:
            mock_settings.RESEARCH_CACHE_ENABLED = True
            mock_settings.RESEARCH_CACHE_TTL_HOURS = 24
            result = await quick_web_lookup.ainvoke({"query": "weather Tokyo"})
            assert "Quick Result" in result
            cache_key = _make_cache_key("weather Tokyo", "general", 3)
            cached = await research_cache.get(cache_key)
            assert cached is not None
            assert "Quick Result" in cached

    @pytest.mark.asyncio
    async def test_quick_web_lookup_returns_cached_on_hit(self):
        from agents.tools.internet import quick_web_lookup, reset_orchestrator_search_count
        reset_orchestrator_search_count()
        cache_key = _make_cache_key("currency JPY", "general", 3)
        await research_cache.set(cache_key, "Title: Cached\nURL: https://cached.com\nSummary: 1 USD = 150 JPY")
        mock_tavily = MagicMock()
        with patch("agents.tools.internet._get_tavily", return_value=mock_tavily), \
             patch("agents.tools.internet.settings") as mock_settings:
            mock_settings.RESEARCH_CACHE_ENABLED = True
            mock_settings.RESEARCH_CACHE_TTL_HOURS = 24
            result = await quick_web_lookup.ainvoke({"query": "currency JPY"})
            assert "150 JPY" in result
            mock_tavily.search.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_disabled_setting(self):
        cache_key = _make_cache_key("disabled test", "general", 5)
        await research_cache.set(cache_key, "This should not be returned")
        mock_tavily = MagicMock()
        mock_tavily.search.return_value = _make_tavily_response([
            _make_result("Fresh Result", "https://fresh.com", "Fresh from Tavily."),
        ])
        with patch("agents.tools.internet._get_tavily", return_value=mock_tavily), \
             patch("agents.tools.internet.settings") as mock_settings:
            mock_settings.RESEARCH_CACHE_ENABLED = False
            mock_settings.RESEARCH_CACHE_TTL_HOURS = 24
            result = await internet_search.ainvoke({"query": "disabled test"})
            assert "Fresh Result" in result
            assert "This should not be returned" not in result
            mock_tavily.search.assert_called_once()
