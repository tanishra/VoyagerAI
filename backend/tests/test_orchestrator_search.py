"""Tests for the orchestrator's quick_web_lookup tool.

Covers:
- Concise result formatting (title + URL + summary, max 3 results)
- Rate limiting (3 calls/turn, 4th blocked, reset between turns)
- Retry logic with exponential backoff
- Timeout handling
- Edge cases: empty query, malformed response, empty results, no API key
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.tools.internet import (
    _format_concise_results,
    _quick_search,
    get_orchestrator_tools,
    quick_web_lookup,
    reset_orchestrator_search_count,
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
def _reset_rate_limit():
    """Reset rate limiter and clear research cache before each test."""
    import asyncio as _asyncio
    loop = _asyncio.new_event_loop()
    loop.run_until_complete(research_cache.invalidate_all())
    reset_orchestrator_search_count()
    yield
    loop.run_until_complete(research_cache.invalidate_all())
    reset_orchestrator_search_count()
    loop.close()


# ---------------------------------------------------------------------------
# Core functionality
# ---------------------------------------------------------------------------

class TestConciseFormatting:
    def test_format_concise_results_basic(self):
        results = _make_tavily_response([
            _make_result("Tokyo Weather", "https://example.com/weather", "Spring is mild with temperatures around 15-20C."),
            _make_result("Visa Info", "https://example.com/visa", "Tourist visa required for most nationalities."),
        ])
        out = _format_concise_results(results)
        assert "Title: Tokyo Weather" in out
        assert "URL: https://example.com/weather" in out
        assert "Summary: Spring is mild" in out
        assert "---" in out
        assert "Score:" not in out

    def test_format_concise_results_max_3(self):
        results = _make_tavily_response([
            _make_result(f"Result {i}", f"https://example.com/{i}", f"Content {i}") for i in range(7)
        ])
        out = _format_concise_results(results)
        assert out.count("Title:") == 3
        assert "Result 0" in out
        assert "Result 2" in out
        assert "Result 3" not in out

    def test_format_concise_results_truncates_summary(self):
        long_content = "A" * 1000
        results = _make_tavily_response([_make_result("Test", "https://example.com", long_content)])
        out = _format_concise_results(results)
        summary_line = [line for line in out.split("\n") if line.startswith("Summary:")][0]
        assert len(summary_line) <= len("Summary: ") + 200

    def test_format_concise_results_empty(self):
        results = _make_tavily_response([])
        assert _format_concise_results(results) == "No results found."

    def test_format_concise_results_missing_keys(self):
        results = _make_tavily_response([{"foo": "bar"}])
        out = _format_concise_results(results)
        assert "Title: Untitled" in out
        assert "URL:" in out
        assert "Summary:" in out


class TestQuickSearch:
    @pytest.mark.asyncio
    async def test_quick_search_no_api_key(self):
        with patch("agents.tools.internet._get_tavily", return_value=None):
            result = await _quick_search("test query")
            assert "unavailable" in result.lower()
            assert "TAVILY_API_KEY" in result

    @pytest.mark.asyncio
    async def test_quick_search_success(self):
        mock_tavily = MagicMock()
        mock_tavily.search.return_value = _make_tavily_response([
            _make_result("Visa Info", "https://example.com/visa", "Tourist visa required."),
        ])
        with patch("agents.tools.internet._get_tavily", return_value=mock_tavily):
            result = await _quick_search("Japan visa requirements")
            assert "Title: Visa Info" in result
            assert "URL: https://example.com/visa" in result
            mock_tavily.search.assert_called_once_with(
                query="Japan visa requirements",
                max_results=3,
                topic="general",
                include_raw_content=False,
            )

    @pytest.mark.asyncio
    async def test_quick_search_retry_on_transient_error(self):
        mock_tavily = MagicMock()
        mock_tavily.search.side_effect = [
            ConnectionError("Network error"),
            _make_tavily_response([_make_result("Success", "https://example.com", "Found it.")]),
        ]
        with patch("agents.tools.internet._get_tavily", return_value=mock_tavily), \
             patch("agents.tools.internet._RETRY_DELAYS", [0.01, 0.01]):
            result = await _quick_search("test")
            assert "Title: Success" in result
            assert mock_tavily.search.call_count == 2

    @pytest.mark.asyncio
    async def test_quick_search_retry_exhausted(self):
        mock_tavily = MagicMock()
        mock_tavily.search.side_effect = ConnectionError("Persistent error")
        with patch("agents.tools.internet._get_tavily", return_value=mock_tavily), \
             patch("agents.tools.internet._RETRY_DELAYS", [0.01, 0.01]):
            result = await _quick_search("test")
            assert "failed" in result.lower()
            assert "researcher subagent" in result.lower()
            assert mock_tavily.search.call_count == 3

    @pytest.mark.asyncio
    async def test_quick_search_timeout(self):
        mock_tavily = MagicMock()

        def slow_search(**kwargs):
            import time
            time.sleep(20)
            return {}

        mock_tavily.search.side_effect = slow_search
        with patch("agents.tools.internet._get_tavily", return_value=mock_tavily), \
             patch("agents.tools.internet._SEARCH_TIMEOUT", 0.1), \
             patch("agents.tools.internet._RETRY_DELAYS", [0.01, 0.01]):
            result = await _quick_search("test")
            assert "failed" in result.lower()

    @pytest.mark.asyncio
    async def test_quick_search_empty_results(self):
        mock_tavily = MagicMock()
        mock_tavily.search.return_value = _make_tavily_response([])
        with patch("agents.tools.internet._get_tavily", return_value=mock_tavily):
            result = await _quick_search("obscure query")
            assert result == "No results found."


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

class TestRateLimit:
    @pytest.mark.asyncio
    async def test_rate_limit_allows_3_calls(self):
        mock_tavily = MagicMock()
        mock_tavily.search.return_value = _make_tavily_response([
            _make_result("R", "https://example.com", "C"),
        ])
        with patch("agents.tools.internet._get_tavily", return_value=mock_tavily):
            for i in range(3):
                result = await quick_web_lookup.ainvoke({"query": f"query {i}"})
                assert "Title: R" in result

    @pytest.mark.asyncio
    async def test_rate_limit_blocks_4th_call(self):
        mock_tavily = MagicMock()
        mock_tavily.search.return_value = _make_tavily_response([
            _make_result("R", "https://example.com", "C"),
        ])
        with patch("agents.tools.internet._get_tavily", return_value=mock_tavily):
            for i in range(3):
                await quick_web_lookup.ainvoke({"query": f"query {i}"})
            result = await quick_web_lookup.ainvoke({"query": "4th query"})
            assert "limit reached" in result.lower()
            assert "researcher subagent" in result.lower()
            assert mock_tavily.search.call_count == 3

    @pytest.mark.asyncio
    async def test_rate_limit_resets_per_turn(self):
        mock_tavily = MagicMock()
        mock_tavily.search.return_value = _make_tavily_response([
            _make_result("R", "https://example.com", "C"),
        ])
        with patch("agents.tools.internet._get_tavily", return_value=mock_tavily):
            for i in range(3):
                await quick_web_lookup.ainvoke({"query": f"query {i}"})
            reset_orchestrator_search_count()
            result = await quick_web_lookup.ainvoke({"query": "new turn query"})
            assert "Title: R" in result


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_empty_query_returns_error(self):
        result = await quick_web_lookup.ainvoke({"query": ""})
        assert result == "Query must not be empty."

    @pytest.mark.asyncio
    async def test_whitespace_query_returns_error(self):
        result = await quick_web_lookup.ainvoke({"query": "   "})
        assert result == "Query must not be empty."


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------

class TestOrchestratorTools:
    def test_get_orchestrator_tools_returns_quick_lookup(self):
        tools = get_orchestrator_tools()
        assert len(tools) == 1
        assert tools[0].name == "quick_web_lookup"
