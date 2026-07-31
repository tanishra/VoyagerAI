from __future__ import annotations

import json
import logging
import re

from deepagents import FilesystemPermission, create_deep_agent
from deepagents.backends import CompositeBackend, FilesystemBackend, StoreBackend
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.redis import RedisSaver
from langgraph.store.memory import InMemoryStore
from langgraph.store.redis import RedisConnectionFactory, RedisStore

from agents.prompts import CHAT_AGENT_SYSTEM_PROMPT, TRAVEL_AGENT_SYSTEM_PROMPT
from agents.subagents import get_subagents
from config.settings import settings

logger = logging.getLogger("travel_agent.deep_agent")

_checkpointer = None
_store = None
_file_store = None


def create_redis_checkpointer() -> RedisSaver:
    global _checkpointer
    if _checkpointer is None:
        _checkpointer = RedisSaver(redis_url=settings.REDIS_URL)
        _checkpointer.setup()
    return _checkpointer


def create_redis_store() -> RedisStore:
    global _store
    if _store is None:
        conn = RedisConnectionFactory.get_redis_connection(settings.REDIS_URL)
        _store = RedisStore(
            conn=conn,
            index={"dims": 1536, "embed": "openai:text-embedding-3-small"},
        )
        _store.setup()
    return _store


def get_redis_file_store() -> InMemoryStore | RedisStore:
    global _file_store
    if _file_store is None:
        if settings.STORE_BACKEND == "redis":
            try:
                conn = RedisConnectionFactory.get_redis_connection(settings.REDIS_URL)
                _file_store = RedisStore(conn=conn)
                _file_store.setup()
            except Exception:  # noqa: BLE001 (intentional fallback handler)
                _file_store = InMemoryStore()
        else:
            _file_store = InMemoryStore()
    return _file_store


def create_travel_agent(checkpointer=None, store=None, user_id=None):
    if checkpointer is None:
        if settings.CHECKPOINTER_BACKEND == "redis":
            try:
                checkpointer = create_redis_checkpointer()
            except Exception:  # noqa: BLE001 (intentional fallback handler)
                checkpointer = MemorySaver()
        else:
            checkpointer = MemorySaver()

    if store is None:
        if settings.STORE_BACKEND == "redis":
            try:
                store = create_redis_store()
            except Exception:  # noqa: BLE001 (intentional fallback handler)
                store = InMemoryStore()
        else:
            store = InMemoryStore()

    model = ChatGoogleGenerativeAI(
        model="gemini-2.5-pro",
        google_api_key=settings.GEMINI_API_KEY,
        temperature=0.4,
    )

    subagents = get_subagents()

    uid = user_id or "anonymous"

    def _make_backend(rt):
        return CompositeBackend(
            default=FilesystemBackend(root_dir="/tmp/agent_fs"),
            routes={
                "/memories/": StoreBackend(
                    store=get_redis_file_store(),
                    namespace=lambda _rt: (uid,),
                ),
            },
        )

    agent = create_deep_agent(
        model=model,
        tools=[],
        subagents=subagents,
        system_prompt=TRAVEL_AGENT_SYSTEM_PROMPT,
        checkpointer=checkpointer,
        store=store,
        memory=["/memories/preferences.md"],
        permissions=[
            FilesystemPermission(
                operations=["read", "write"],
                paths=["/workspace/**", "/memories/**"],
            ),
        ],
        backend=_make_backend,
    )

    return agent


def _extract_itinerary(state: dict) -> dict:
    messages = state.get("messages", [])
    if not messages:
        raise ValueError("No messages in agent response")

    def _find_json_objects(text: str) -> list[dict]:
        results = []
        cleaned = text.strip()
        if cleaned.startswith("```"):
            first_nl = cleaned.index("\n") if "\n" in cleaned else len(cleaned)
            cleaned = cleaned[first_nl + 1:]
        cleaned = cleaned.removesuffix("```")
        cleaned = cleaned.strip()
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                results.append(parsed)
        except (json.JSONDecodeError, ValueError):
            pass
        return results

    def _score_itinerary(obj: dict) -> int:
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
    agent = create_travel_agent(user_id=user_id)
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
    agent = create_travel_agent(user_id=user_id)
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


def create_chat_agent(checkpointer=None, store=None, user_id=None):
    if checkpointer is None:
        if settings.CHECKPOINTER_BACKEND == "redis":
            try:
                checkpointer = create_redis_checkpointer()
            except Exception:  # noqa: BLE001 (intentional fallback handler)
                checkpointer = MemorySaver()
        else:
            checkpointer = MemorySaver()

    if store is None:
        if settings.STORE_BACKEND == "redis":
            try:
                store = create_redis_store()
            except Exception:  # noqa: BLE001 (intentional fallback handler)
                store = InMemoryStore()
        else:
            store = InMemoryStore()

    model = ChatGoogleGenerativeAI(
        model="gemini-2.5-pro",
        google_api_key=settings.GEMINI_API_KEY,
        temperature=0.4,
    )

    subagents = get_subagents()

    uid = user_id or "anonymous"

    def _make_backend(rt):
        return CompositeBackend(
            default=FilesystemBackend(root_dir="/tmp/agent_fs"),
            routes={
                "/memories/": StoreBackend(
                    store=get_redis_file_store(),
                    namespace=lambda _rt: (uid,),
                ),
            },
        )

    agent = create_deep_agent(
        model=model,
        tools=[],
        subagents=subagents,
        system_prompt=CHAT_AGENT_SYSTEM_PROMPT,
        checkpointer=checkpointer,
        store=store,
        memory=["/memories/preferences.md"],
        permissions=[
            FilesystemPermission(
                operations=["read", "write"],
                paths=["/workspace/**", "/memories/**"],
            ),
        ],
        backend=_make_backend,
    )

    return agent


_ITINERARY_TAG_RE = re.compile(r"<itinerary>\s*(.*?)\s*</itinerary>", re.DOTALL)


def _find_largest_json_object(text: str) -> dict | None:
    """Best-effort fallback: locate the largest balanced JSON object in text.

    Tries the longest brace-balanced spans first; only accepts objects that
    look like an itinerary (destination + days keys). Returns None if nothing
    parses.
    """
    spans: list[str] = []
    for m in re.finditer(r"\{", text):
        depth = 0
        for i in range(m.start(), len(text)):
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    spans.append(text[m.start():i + 1])
                    break
    for span in reversed(spans):  # longest first
        try:
            parsed = json.loads(span)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(parsed, dict) and "destination" in parsed and "days" in parsed:
            return parsed
    return None


def _extract_chat_itinerary(state: dict) -> dict | None:
    messages = state.get("messages", [])
    if not messages:
        return None

    for msg in reversed(messages):
        c = msg.content
        texts: list[str] = []
        if isinstance(c, str):
            texts.append(c)
        elif isinstance(c, list):
            texts.extend(
                p["text"] for p in c if isinstance(p, dict) and p.get("type") == "text"
            )
        for text in texts:
            match = _ITINERARY_TAG_RE.search(text)
            if match:
                try:
                    parsed = json.loads(match.group(1))
                    return parsed
                except (json.JSONDecodeError, ValueError):
                    logger.warning("Found <itinerary> tags but content is not valid JSON")
            fallback = _find_largest_json_object(text)
            if fallback is not None:
                return fallback

    return None


async def stream_chat_agent(
    message: str,
    thread_id: str,
    user_id: str | None = None,
):
    agent = create_chat_agent(user_id=user_id)
    config = {
        "configurable": {
            "thread_id": thread_id,
            "user_id": user_id or "anonymous",
        },
        "recursion_limit": 50,
    }

    async for event in agent.astream_events(
        {"messages": [{"role": "user", "content": message}]},
        config,
        version="v2",
    ):
        yield event

    state = await agent.aget_state(config)
    itinerary = _extract_chat_itinerary(state.values)
    if itinerary is None:
        await agent.ainvoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            "Your previous response did not include the itinerary JSON. "
                            "Please output the final itinerary JSON now, inside "
                            "<itinerary></itinerary> tags."
                        ),
                    }
                ]
            },
            config,
        )
        state = await agent.aget_state(config)
        itinerary = _extract_chat_itinerary(state.values)

    try:
        if itinerary is not None:
            yield {"event": "itinerary", "data": itinerary}
        yield {"event": "done", "data": None}
    except (ValueError, json.JSONDecodeError) as exc:
        yield {"event": "error", "data": str(exc)}
