from __future__ import annotations

import json
import logging

from deepagents import create_deep_agent, FilesystemPermission
from deepagents.backends import FilesystemBackend
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.redis import RedisSaver
from langgraph.store.memory import InMemoryStore
from langgraph.store.redis import RedisStore

from config.settings import settings

from agents.prompts import TRAVEL_AGENT_SYSTEM_PROMPT
from agents.tools import get_internet_tools
from agents.subagents import get_subagents

logger = logging.getLogger("travel_agent.deep_agent")

_checkpointer = None
_store = None


def create_redis_checkpointer() -> RedisSaver:
    global _checkpointer
    if _checkpointer is None:
        _checkpointer = RedisSaver(redis_url=settings.REDIS_URL)
        _checkpointer.setup()
    return _checkpointer


def create_redis_store() -> RedisStore:
    global _store
    if _store is None:
        _store = RedisStore(
            redis_url=settings.REDIS_URL,
            index={"dims": 1536, "embed": "openai:text-embedding-3-small"},
        )
        _store.setup()
    return _store


def create_travel_agent(checkpointer=None, store=None):
    if checkpointer is None:
        if settings.CHECKPOINTER_BACKEND == "redis":
            try:
                checkpointer = create_redis_checkpointer()
            except Exception:
                checkpointer = MemorySaver()
        else:
            checkpointer = MemorySaver()

    if store is None:
        if settings.STORE_BACKEND == "redis":
            try:
                store = create_redis_store()
            except Exception:
                store = InMemoryStore()
        else:
            store = InMemoryStore()

    model = ChatGoogleGenerativeAI(
        model="gemini-2.5-pro",
        google_api_key=settings.GEMINI_API_KEY,
        temperature=0.4,
    )

    subagents = get_subagents()

    agent = create_deep_agent(
        model=model,
        tools=[],
        subagents=subagents,
        system_prompt=TRAVEL_AGENT_SYSTEM_PROMPT,
        checkpointer=checkpointer,
        store=store,
        permissions=[
            FilesystemPermission(
                operations=["read", "write"],
                paths=["/workspace/**"],
            ),
        ],
        backend=FilesystemBackend(root_dir="/tmp/agent_fs"),
    )

    return agent


def _extract_itinerary(state: dict, user_message: str = "") -> dict:
    """Extract the itinerary JSON from the agent response.

    Searches all messages and tool call arguments for JSON matching
    the itinerary schema.
    """
    messages = state.get("messages", [])
    if not messages:
        raise ValueError("No messages in agent response")

    itinerary_keys = {
        "destination", "total_days", "estimated_total_cost_usd",
        "budget_status", "visa_note", "best_season_note", "days",
    }

    def _find_json_objects(text: str) -> list[dict]:
        results = []
        cleaned = text.strip()
        if cleaned.startswith("```"):
            first_nl = cleaned.index("\n") if "\n" in cleaned else len(cleaned)
            cleaned = cleaned[first_nl + 1:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                results.append(parsed)
        except (json.JSONDecodeError, ValueError):
            pass
        return results

    def _score_itinerary(obj: dict) -> int:
        """Score how well a dict matches the itinerary schema."""
        if not isinstance(obj, dict):
            return 0
        score = 0
        if "destination" in obj:
            score += 3
        if "total_days" in obj:
            score += 3
        if "estimated_total_cost_usd" in obj:
            score += 2
        if "budget_status" in obj:
            score += 2
        if "days" in obj and isinstance(obj["days"], list):
            score += 5
            if obj["days"] and isinstance(obj["days"][0], dict):
                score += 3
        if "visa_note" in obj:
            score += 1
        if "best_season_note" in obj:
            score += 1
        return score

    candidates: list[tuple[int, dict]] = []

    for msg in messages:
        c = msg.content
        texts = []
        if isinstance(c, str):
            texts.append(c)
        elif isinstance(c, list):
            texts.extend(
                p["text"] for p in c if isinstance(p, dict) and p.get("type") == "text"
            )
        for text in texts:
            for obj in _find_json_objects(text):
                score = _score_itinerary(obj)
                if score > 0:
                    candidates.append((score, obj))

        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                for arg_value in tc.get("args", {}).values():
                    if isinstance(arg_value, str):
                        for obj in _find_json_objects(arg_value):
                            score = _score_itinerary(obj)
                            if score >= 5:
                                candidates.append((score, obj))

    if not candidates:
        raise ValueError("Could not extract itinerary JSON from agent response")

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


async def run_travel_agent(
    user_message: str,
    thread_id: str,
    user_id: str | None = None,
) -> dict:
    agent = create_travel_agent()
    config = {
        "configurable": {
            "thread_id": thread_id,
            "user_id": user_id or "anonymous",
        },
        "recursion_limit": 50,
    }
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": user_message}]},
        config,
    )
    return _extract_itinerary(result)


async def stream_travel_agent(
    user_message: str,
    thread_id: str,
    user_id: str | None = None,
):
    agent = create_travel_agent()
    config = {
        "configurable": {
            "thread_id": thread_id,
            "user_id": user_id or "anonymous",
        },
        "recursion_limit": 50,
    }
    async for event in agent.astream_events(
        {"messages": [{"role": "user", "content": user_message}]},
        config,
        version="v2",
    ):
        yield event

    state = await agent.aget_state(config)
    try:
        itinerary = _extract_itinerary(state.values)
        yield {"event": "final", "data": itinerary}
    except (ValueError, json.JSONDecodeError) as exc:
        yield {"event": "error", "data": str(exc)}
