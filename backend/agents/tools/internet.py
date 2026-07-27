from __future__ import annotations

from langchain_core.tools import tool
from tavily import TavilyClient

from config.settings import settings

_tavily_client: TavilyClient | None = None


def _get_tavily() -> TavilyClient | None:
    global _tavily_client
    if _tavily_client is None and settings.TAVILY_API_KEY:
        _tavily_client = TavilyClient(api_key=settings.TAVILY_API_KEY)
    return _tavily_client


_UNAVAILABLE_MSG = "Internet search is unavailable: TAVILY_API_KEY not configured."


def _search(query: str, max_results: int = 5, topic: str = "general") -> str:
    """Internal search helper (not a tool)."""
    tavily = _get_tavily()
    if tavily is None:
        return _UNAVAILABLE_MSG
    results = tavily.search(
        query=query,
        max_results=max_results,
        topic=topic,
        include_raw_content=False,
    )
    return _format_search_results(results)


def _format_search_results(results: dict) -> str:
    formatted = []
    for r in results.get("results", []):
        formatted.append(
            f"Title: {r['title']}\n"
            f"URL: {r['url']}\n"
            f"Content: {r['content'][:500]}...\n"
            f"Score: {r.get('score', 'N/A')}\n"
        )
    return "\n---\n".join(formatted) if formatted else "No results found."


@tool
def internet_search(
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
        Formatted string with title, URL, content snippet, and score
    """
    return _search(query, max_results=max_results, topic=topic)


@tool
def search_events(destination: str, dates: str) -> str:
    """Search for events, festivals, closures during specific dates."""
    query = f"events festivals {destination} {dates} 2024 2025"
    return _search(query, max_results=8, topic="news")


@tool
def search_weather(destination: str, month: str) -> str:
    """Get typical weather patterns for destination in month."""
    query = f"weather {destination} {month} temperature rainfall packing"
    return _search(query, max_results=5, topic="general")


@tool
def search_visa(nationality: str, destination: str) -> str:
    """Get visa/entry requirements for nationality traveling to destination."""
    query = f"visa requirements {nationality} citizens {destination} 2024"
    return _search(query, max_results=5, topic="general")


@tool
def search_costs(destination: str, style: str) -> str:
    """Get current cost estimates for accommodation, food, transport."""
    query = f"travel costs {destination} {style} budget 2024 accommodation food transport"
    return _search(query, max_results=8, topic="general")


def get_internet_tools() -> list:
    return [
        internet_search,
        search_events,
        search_weather,
        search_visa,
        search_costs,
    ]
