from __future__ import annotations

import asyncio
import hashlib
import logging
import re

from langchain_core.tools import tool
from tavily import TavilyClient

from config.settings import settings
from research_cache import research_cache

logger = logging.getLogger("travel_agent.tools.internet")

_tavily_client: TavilyClient | None = None


def _get_tavily() -> TavilyClient | None:
    global _tavily_client
    if _tavily_client is None and settings.TAVILY_API_KEY:
        _tavily_client = TavilyClient(api_key=settings.TAVILY_API_KEY)
    return _tavily_client


_UNAVAILABLE_MSG = "Internet search is unavailable: TAVILY_API_KEY not configured."

_MAX_RETRIES = 2
_RETRY_DELAYS = [0.5, 1.5]
_SEARCH_TIMEOUT = 10
_MAX_RESULTS_CAP = 10


def _make_cache_key(query: str, topic: str, max_results: int) -> str:
    raw = f"{query.strip().lower()}|{topic}|{max_results}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _format_search_results(results: dict) -> str:
    formatted = []
    for r in results.get("results", []):
        title = r.get("title", "Untitled").strip()
        url = r.get("url", "").strip()
        content = r.get("content", "").strip()
        content = re.sub(r"\s+", " ", content)[:500]
        formatted.append(f"Title: {title}\nURL: {url}\nContent: {content}...")
    return "\n---\n".join(formatted) if formatted else "No results found."


async def _search_with_retry(query: str, max_results: int = 5, topic: str = "general") -> str:
    """Internal async search helper with retry, timeout, formatted output, and caching."""
    capped_results = min(max_results, _MAX_RESULTS_CAP)

    if settings.RESEARCH_CACHE_ENABLED:
        cache_key = _make_cache_key(query, topic, capped_results)
        cached = await research_cache.get(cache_key)
        if cached is not None:
            logger.debug("Research cache HIT for query: %s", query[:100])
            return cached

    tavily = _get_tavily()
    if tavily is None:
        return _UNAVAILABLE_MSG

    last_error: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            results = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: tavily.search(
                        query=query,
                        max_results=capped_results,
                        topic=topic,
                        include_raw_content=False,
                    )
                ),
                timeout=_SEARCH_TIMEOUT,
            )
            formatted = _format_search_results(results)
            if settings.RESEARCH_CACHE_ENABLED:
                cache_key = _make_cache_key(query, topic, capped_results)
                await research_cache.set(
                    cache_key, formatted, ttl=settings.RESEARCH_CACHE_TTL_HOURS * 3600
                )
            return formatted

        except asyncio.TimeoutError:
            logger.warning(
                "Tavily search timed out (attempt %d/%d) for query: %s",
                attempt + 1, _MAX_RETRIES + 1, query[:100],
            )
            last_error = TimeoutError("Search timed out")

        except Exception as exc:
            logger.warning(
                "Tavily search failed (attempt %d/%d): %s",
                attempt + 1, _MAX_RETRIES + 1, exc,
            )
            last_error = exc

        if attempt < _MAX_RETRIES:
            await asyncio.sleep(_RETRY_DELAYS[attempt])

    return (
        f"Internet search failed after {_MAX_RETRIES + 1} attempts: {last_error}. "
        "Please try again or proceed with available information."
    )


@tool
async def internet_search(
    query: str,
    max_results: int = 5,
    topic: str = "general",
) -> str:
    """Search the internet for real-time travel information.

    Use this for:
    - Current events, festivals, closures (topic="news")
    - Weather patterns, seasonal info (topic="general")
    - Visa requirements, entry rules (topic="general")
    - Pricing trends, costs (topic="general")
    - Safety advisories (topic="news")

    Args:
        query: Search query string
        max_results: Number of results to return (1-10)
        topic: "general" | "news" | "finance"

    Returns:
        Formatted string with title, URL, and content snippet per result
    """
    if not query or not query.strip():
        return "Query must not be empty."

    return await _search_with_retry(query.strip(), max_results=max_results, topic=topic)


def get_internet_tools() -> list:
    return [internet_search]


# ---------------------------------------------------------------------------
# Orchestrator quick lookup tool — lightweight, rate-limited, concise output
# ---------------------------------------------------------------------------

_RATE_LIMIT = 3
_SUMMARY_MAX_CHARS = 200

_orchestrator_search_count: int = 0
_orchestrator_search_lock: asyncio.Lock | None = None


def _get_search_lock() -> asyncio.Lock:
    global _orchestrator_search_lock
    if _orchestrator_search_lock is None:
        _orchestrator_search_lock = asyncio.Lock()
    return _orchestrator_search_lock


def reset_orchestrator_search_count() -> None:
    """Reset the per-turn search counter. Called at the start of each stream_chat_agent invocation."""
    global _orchestrator_search_count
    _orchestrator_search_count = 0


def _format_concise_results(results: dict) -> str:
    """Format search results as concise title + URL + short summary (~50 tokens each)."""
    formatted = []
    for r in results.get("results", [])[:3]:
        title = r.get("title", "Untitled").strip()
        url = r.get("url", "").strip()
        content = r.get("content", "").strip()
        content = re.sub(r"\s+", " ", content)[:_SUMMARY_MAX_CHARS]
        formatted.append(f"Title: {title}\nURL: {url}\nSummary: {content}")
    return "\n---\n".join(formatted) if formatted else "No results found."


async def _quick_search(query: str, topic: str = "general") -> str:
    """Internal async search helper with retry, timeout, concise formatting, and caching."""
    if settings.RESEARCH_CACHE_ENABLED:
        cache_key = _make_cache_key(query, topic, 3)
        cached = await research_cache.get(cache_key)
        if cached is not None:
            logger.debug("Research cache HIT for quick lookup: %s", query[:100])
            return cached

    tavily = _get_tavily()
    if tavily is None:
        return _UNAVAILABLE_MSG

    last_error: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            results = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: tavily.search(
                        query=query,
                        max_results=3,
                        topic=topic,
                        include_raw_content=False,
                    )
                ),
                timeout=_SEARCH_TIMEOUT,
            )
            formatted = _format_concise_results(results)
            if settings.RESEARCH_CACHE_ENABLED:
                cache_key = _make_cache_key(query, topic, 3)
                await research_cache.set(
                    cache_key, formatted, ttl=settings.RESEARCH_CACHE_TTL_HOURS * 3600
                )
            return formatted

        except asyncio.TimeoutError:
            logger.warning(
                "Tavily search timed out (attempt %d/%d) for query: %s",
                attempt + 1, _MAX_RETRIES + 1, query[:100],
            )
            last_error = TimeoutError("Search timed out")

        except Exception as exc:
            logger.warning(
                "Tavily search failed (attempt %d/%d): %s",
                attempt + 1, _MAX_RETRIES + 1, exc,
            )
            last_error = exc

        if attempt < _MAX_RETRIES:
            await asyncio.sleep(_RETRY_DELAYS[attempt])

    return (
        f"Web lookup failed after {_MAX_RETRIES + 1} attempts: {last_error}. "
        "Try rephrasing your question, or dispatch the researcher subagent for comprehensive research."
    )


@tool
async def quick_web_lookup(
    query: str,
    topic: str = "general",
) -> str:
    """Quick web lookup for fast factual answers during conversation.

    Use this tool when a user asks a specific question that needs current information:
    - "What's the weather in Tokyo in March?"
    - "Do I need a visa for Japan?"
    - "What's the currency exchange rate for INR to JPY?"

    This tool returns concise results (title + URL + short summary, max 3 results).
    It is rate-limited to 3 calls per conversation turn.

    For comprehensive destination research (hotels, events, neighborhoods, multiple topics),
    dispatch the researcher subagent instead — it has unlimited searches and returns structured briefs.

    Args:
        query: Search query string (must not be empty)
        topic: "general" for evergreen info, "news" for current events

    Returns:
        Concise formatted string with title, URL, and 1-2 sentence summary per result
    """
    if not query or not query.strip():
        return "Query must not be empty."

    global _orchestrator_search_count

    async with _get_search_lock():
        _orchestrator_search_count += 1
        current_count = _orchestrator_search_count

    if current_count > _RATE_LIMIT:
        return (
            "Quick lookup limit reached (3/turn). "
            "For more research, dispatch the researcher subagent with a task tool call."
        )

    return await _quick_search(query.strip(), topic=topic)


def get_orchestrator_tools() -> list:
    """Return tools available directly to the orchestrator (not via subagents)."""
    return [quick_web_lookup]
