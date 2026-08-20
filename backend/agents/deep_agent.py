from __future__ import annotations

import json
import logging
import os
import re

import aiosqlite
from deepagents import FilesystemPermission, create_deep_agent
from deepagents.backends import CompositeBackend, FilesystemBackend, StoreBackend
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.store.memory import InMemoryStore
from langgraph.store.redis import RedisConnectionFactory, RedisStore
from pydantic import BaseModel

from agents.activity_store import load_activity, save_activity
from agents.llm import get_formatter_model, get_orchestrator_model
from agents.prompts import build_chat_agent_prompt
from agents.subagents import get_subagents
from config.settings import settings
from geocode_service import geocode
from langchain.agents.middleware import ModelCallLimitMiddleware

logger = logging.getLogger("travel_agent.deep_agent")

_checkpointer = None
_sqlite_checkpointer = None
_store = None
_file_store = None


async def create_redis_checkpointer() -> AsyncRedisSaver:
    """Build a Redis-backed checkpointer, cached per process.

    NOTE: the sync ``langgraph.checkpoint.redis.RedisSaver`` leaves
    ``aget_tuple`` unimplemented, which crashes any async stream run; the
    ``AsyncRedisSaver`` from ``langgraph.checkpoint.redis.aio`` is the
    implementation that works with async graphs.
    """
    global _checkpointer
    if _checkpointer is None:
        saver = AsyncRedisSaver(redis_url=settings.REDIS_URL)
        await saver.setup()
        _checkpointer = saver
    return _checkpointer


async def create_sqlite_checkpointer() -> AsyncSqliteSaver:
    """Build a file-backed checkpointer (persists across restarts, no
    external service required)."""
    global _sqlite_checkpointer
    if _sqlite_checkpointer is None:
        path = settings.CHECKPOINTER_DB_PATH
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        conn = await aiosqlite.connect(path)
        saver = AsyncSqliteSaver(conn)
        await saver.setup()
        _sqlite_checkpointer = saver
    return _sqlite_checkpointer


async def create_checkpointer():
    """Build the checkpointer for the configured backend.

    Redis is primary; if it is unavailable (e.g. no RediSearch module),
    fall back to SQLite when configured, then in-memory as a last resort.
    """
    backend = settings.CHECKPOINTER_BACKEND
    if backend == "sqlite":
        return await create_sqlite_checkpointer()
    if backend == "memory":
        return MemorySaver()
    try:
        return await create_redis_checkpointer()
    except Exception:  # noqa: BLE001 (intentional fallback handler)
        logger.warning("Redis checkpointer unavailable, falling back to SQLite")
        try:
            return await create_sqlite_checkpointer()
        except Exception:  # noqa: BLE001 (intentional fallback handler)
            return MemorySaver()


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


def _truncate_for_activity(data, max_chars: int = 1000) -> str:
    """Truncate tool input/output for activity storage."""
    if data is None:
        return None
    if isinstance(data, (dict, list)):
        s = json.dumps(data, default=str)
    else:
        s = str(data)
    return s[:max_chars] + ("..." if len(s) > max_chars else "")


class _ModelStream:
    """Accumulate streamed model text per run from `astream_events` chunks.

    The agent node persists only the first stream chunk of each model call,
    so the checkpoint message is an unreliable stub for extraction; the full
    response text is only available in the stream events themselves.
    """

    def __init__(self, agent, config):
        self._agent = agent
        self._config = config
        self._texts: dict[str, str] = {}
        self._reasoning_texts: dict[str, str] = {}
        self._order: list[str] = []
        self.activity: dict = {
            "thinking": [],
            "tool_calls": [],
            "usage": [],
            "total_input_tokens": 0,
            "total_output_tokens": 0,
        }
        self._tool_call_index: dict[str, int] = {}

    async def events(self, inputs):
        async for event in self._agent.astream_events(
            inputs, self._config, version="v2"
        ):
            etype = event.get("event", "")
            run_id = event.get("run_id", "")
            edata = event.get("data", {})

            if etype == "on_chat_model_stream":
                chunk = edata.get("chunk")
                if chunk is not None:
                    c = chunk.content
                    if isinstance(c, str):
                        text = c
                        reasoning_text = ""
                    elif isinstance(c, list):
                        text = "".join(
                            p.get("text", "")
                            for p in c
                            if isinstance(p, dict)
                            and p.get("type") in ("text", "text-delta")
                        )
                        reasoning_text = "".join(
                            p.get("reasoning", "") or p.get("text", "")
                            for p in c
                            if isinstance(p, dict)
                            and p.get("type") in ("reasoning", "reasoning-delta")
                        )
                    else:
                        text = ""
                        reasoning_text = ""
                    if run_id is not None:
                        if run_id not in self._texts:
                            self._order.append(run_id)
                        self._texts[run_id] = self._texts.get(run_id, "") + text
                        if reasoning_text:
                            self._reasoning_texts[run_id] = (
                                self._reasoning_texts.get(run_id, "") + reasoning_text
                            )
                            self.activity["thinking"].append({"text": reasoning_text[:2000]})

            elif etype == "on_tool_start":
                name = event.get("name", "")
                tool_input = edata.get("input") if isinstance(edata, dict) else None
                display_name = name
                if name == "task" and isinstance(tool_input, dict):
                    display_name = tool_input.get("subagent_type", name)
                idx = len(self.activity["tool_calls"])
                self._tool_call_index[run_id] = idx
                self.activity["tool_calls"].append({
                    "run_id": run_id,
                    "name": display_name,
                    "input": _truncate_for_activity(tool_input),
                    "status": "running",
                })

            elif etype == "on_tool_end":
                output = edata.get("output") if isinstance(edata, dict) else edata
                idx = self._tool_call_index.get(run_id)
                if idx is not None and idx < len(self.activity["tool_calls"]):
                    self.activity["tool_calls"][idx]["status"] = "done"
                    self.activity["tool_calls"][idx]["output"] = _truncate_for_activity(output)

            elif etype == "on_tool_error":
                error_msg = edata.get("error") if isinstance(edata, dict) else str(edata)
                idx = self._tool_call_index.get(run_id)
                if idx is not None and idx < len(self.activity["tool_calls"]):
                    self.activity["tool_calls"][idx]["status"] = "error"
                    self.activity["tool_calls"][idx]["error"] = str(error_msg)[:500]

            elif etype == "on_chat_model_end":
                output = edata.get("output") if isinstance(edata, dict) else None
                if output is not None:
                    usage = getattr(output, "usage_metadata", None)
                    resp_meta = getattr(output, "response_metadata", None) or {}
                    model_name = resp_meta.get("model_name", "") or resp_meta.get("model", "")
                    if usage and isinstance(usage, dict):
                        inp = usage.get("input_tokens", 0)
                        outp = usage.get("output_tokens", 0)
                        self.activity["usage"].append({
                            "input_tokens": inp,
                            "output_tokens": outp,
                            "model": model_name,
                        })
                        self.activity["total_input_tokens"] += inp
                        self.activity["total_output_tokens"] += outp

            yield event

    def last_text(self) -> str:
        for run_id in reversed(self._order):
            if self._texts.get(run_id, "").strip():
                return self._texts[run_id]
        return ""

    def last_reasoning(self) -> str:
        for run_id in reversed(self._order):
            if self._reasoning_texts.get(run_id, "").strip():
                return self._reasoning_texts[run_id]
        return ""


async def create_chat_agent(checkpointer=None, store=None, user_id=None, locale=None):
    if checkpointer is None:
        checkpointer = await create_checkpointer()

    if store is None:
        if settings.STORE_BACKEND == "redis":
            try:
                store = create_redis_store()
            except Exception:  # noqa: BLE001 (intentional fallback handler)
                store = InMemoryStore()
        else:
            store = InMemoryStore()

    model = get_orchestrator_model()

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
        system_prompt=build_chat_agent_prompt(locale),
        checkpointer=checkpointer,
        store=store,
        permissions=[
            FilesystemPermission(
                operations=["read", "write"],
                paths=["/workspace/**", "/memories/**"],
            ),
        ],
        backend=_make_backend,
        middleware=[
            ModelCallLimitMiddleware(run_limit=40, exit_behavior="end"),
        ],
    )

    return agent


_ITINERARY_TAG_RE = re.compile(r"<itinerary>\s*(.*?)\s*</itinerary>", re.DOTALL)
_COMPARISON_TAG_RE = re.compile(r"<comparison>\s*(.*?)\s*</comparison>", re.DOTALL)


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


def _extract_itinerary_from_text(text: str) -> dict | None:
    if not text:
        return None
    match = _ITINERARY_TAG_RE.search(text)
    if match:
        try:
            return json.loads(match.group(1))
        except (json.JSONDecodeError, ValueError):
            logger.warning("Found <itinerary> tags but content is not valid JSON")
    return _find_largest_json_object(text)


def _find_largest_comparison_object(text: str) -> dict | None:
    """Best-effort fallback: locate the largest balanced JSON object that looks like a comparison (has 'plans' key)."""
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
    for span in reversed(spans):
        try:
            parsed = json.loads(span)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(parsed, dict) and "plans" in parsed and isinstance(parsed["plans"], list):
            return parsed
    return None


def _extract_comparison_from_text(text: str) -> dict | None:
    if not text:
        return None
    match = _COMPARISON_TAG_RE.search(text)
    if match:
        try:
            return json.loads(match.group(1))
        except (json.JSONDecodeError, ValueError):
            logger.warning("Found <comparison> tags but content is not valid JSON")
    return _find_largest_comparison_object(text)


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
                p["text"] for p in c if isinstance(p, dict) and p.get("type") in ("text", "text-delta")
            )
        for text in texts:
            itinerary = _extract_itinerary_from_text(text)
            if itinerary is not None:
                return itinerary

    return None


async def _enrich_itinerary_with_coordinates(itinerary: dict) -> dict:
    """Attach lat/lng coordinates to each activity in an itinerary dict.

    Geocodes morning/afternoon/evening locations via Nominatim (with Redis
    caching). Mutates a copy — never the original dict. If geocoding fails
    for a slot, that slot simply lacks lat/lng (frontend skips the marker).

    Never raises — on any exception returns the itinerary unchanged.
    """
    try:
        import copy

        enriched = copy.deepcopy(itinerary)
        destination = enriched.get("destination", "")
        days = enriched.get("days", [])

        for day in days:
            for slot_key in ("morning", "afternoon", "evening"):
                slot = day.get(slot_key)
                if not slot or not isinstance(slot, dict):
                    continue
                location = slot.get("location", "")
                if not location:
                    continue
                query = f"{location}, {destination}" if destination else location
                coords = await geocode(query)
                if coords is not None:
                    slot["lat"] = coords["lat"]
                    slot["lng"] = coords["lng"]

        return enriched
    except Exception:
        logger.warning("Itinerary coordinate enrichment failed", exc_info=True)
        return itinerary


def _last_assistant_text(state: dict) -> str:
    messages = state.get("messages", [])
    for msg in reversed(messages):
        c = msg.content
        if isinstance(c, str):
            return c
        if isinstance(c, list):
            texts = [
                p["text"]
                for p in c
                if isinstance(p, dict) and p.get("type") in ("text", "text-delta")
            ]
            if texts:
                return " ".join(texts)
    return ""


def _extraction_failure_hint(state: dict, stream_text: str | None = None) -> str:
    """Describe what the model emitted so the retry can correct course."""
    text = stream_text or _last_assistant_text(state)
    if not text:
        return "Your previous response contained no output at all."
    snippet = text[:300] if len(text) > 300 else text
    return (
        "Your previous response did not include a parseable itinerary JSON. "
        f"The text you produced ended with: {snippet!r} "
        "Output ONLY the complete itinerary JSON inside <itinerary></itinerary> "
        "tags — no prose, no markdown, no truncation."
    )


class _ItineraryDay(BaseModel):
    day: int
    theme: str | None = None
    morning: dict | None = None
    afternoon: dict | None = None
    evening: dict | None = None


class _ItineraryDraft(BaseModel):
    destination: str
    total_days: int | None = None
    estimated_total_cost_usd: float | None = None
    budget_status: str | None = None
    visa_note: str | None = None
    best_season_note: str | None = None
    days: list[_ItineraryDay]
    warnings: list[str] = []
    packing_essentials: list[str] = []


_formatter_model = None


async def _format_itinerary(draft_text: str, user_message: str) -> dict | None:
    """Structured recovery pass: force valid itinerary JSON from the draft.

    Uses with_structured_output so the model must emit schema-conforming JSON
    via function-call generation instead of free-form text.
    """
    global _formatter_model
    try:
        if _formatter_model is None:
            _formatter_model = get_formatter_model(_ItineraryDraft)
        result = await _formatter_model.ainvoke(
            [
                (
                    "system",
                    ("You are an itinerary JSON formatter. Extract or repair the "
                    "itinerary from the assistant draft. Return ONLY the itinerary "
                    "object with every requested field populated."),
                ),
                (
                    "user",
                    f"User request: {user_message}\n\nAssistant draft:\n{draft_text}",
                ),
            ]
        )
        if result is None:
            return None
        return result.model_dump()
    except Exception:
        logger.warning("structured itinerary formatter failed", exc_info=True)
        return None


async def stream_chat_agent(
    message: str,
    thread_id: str,
    user_id: str | None = None,
    locale: str | None = None,
):
    agent = await create_chat_agent(user_id=user_id, locale=locale)
    config = {
        "configurable": {
            "thread_id": thread_id,
            "user_id": user_id or "anonymous",
        },
        "recursion_limit": 100,
    }

    stream = _ModelStream(agent, config)
    async for event in stream.events(
        {"messages": [{"role": "user", "content": message}]}
    ):
        yield event

    # Persist activity metadata for this thread
    if stream.activity["thinking"] or stream.activity["tool_calls"] or stream.activity["usage"]:
        try:
            store = create_redis_store() if settings.STORE_BACKEND == "redis" else InMemoryStore()
        except Exception:
            store = InMemoryStore()
        await save_activity(store, thread_id, stream.activity)

    stream_text = stream.last_text()
    logger.info("stream finished: last_text len=%d, has_tags=%s", len(stream_text), bool(stream_text and (_ITINERARY_TAG_RE.search(stream_text) or _COMPARISON_TAG_RE.search(stream_text))))

    # Only attempt structured extraction if the agent's response contains
    # itinerary or comparison tags — conversational responses (clarifying
    # questions, suggestions, etc.) should pass through without extraction.
    has_tags = bool(stream_text and (
        _ITINERARY_TAG_RE.search(stream_text) or _COMPARISON_TAG_RE.search(stream_text)
    ))

    if not has_tags:
        # Conversational response — no extraction needed
        yield {"event": "done", "data": None}
        return

    # Check for comparison (3-plan) output first
    comparison = _extract_comparison_from_text(stream_text) if stream_text else None

    if comparison is None:
        # Fall back to single itinerary (refinement turns)
        itinerary = _extract_itinerary_from_text(stream_text) if stream_text else None
        if itinerary is None:
            state = await agent.aget_state(config)
            itinerary = _extract_chat_itinerary(state.values)

        if itinerary is None:
            retry = _ModelStream(agent, config)
            async for event in retry.events(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": _extraction_failure_hint(state.values, stream_text),
                        }
                    ]
                }
            ):
                yield event
            retry_text = retry.last_text()
            stream.activity["thinking"].extend(retry.activity["thinking"])
            stream.activity["tool_calls"].extend(retry.activity["tool_calls"])
            stream.activity["usage"].extend(retry.activity["usage"])
            stream.activity["total_input_tokens"] += retry.activity["total_input_tokens"]
            stream.activity["total_output_tokens"] += retry.activity["total_output_tokens"]
            itinerary = _extract_itinerary_from_text(retry_text) if retry_text else None
            if itinerary is None:
                state = await agent.aget_state(config)
                itinerary = _extract_chat_itinerary(state.values)
            if itinerary is None:
                stream_text = retry_text or stream_text

        if itinerary is None:
            draft = stream_text or _last_assistant_text(state.values)
            itinerary = await _format_itinerary(draft, message)
    else:
        itinerary = None

    try:
        if comparison is not None:
            yield {"event": "comparison", "data": comparison}
        elif itinerary is not None:
            itinerary = await _enrich_itinerary_with_coordinates(itinerary)
            yield {"event": "itinerary", "data": itinerary}
        yield {"event": "done", "data": None}
    except (ValueError, json.JSONDecodeError) as exc:
        yield {"event": "error", "data": str(exc)}

    # Re-save activity if retry added more data
    if stream.activity["thinking"] or stream.activity["tool_calls"] or stream.activity["usage"]:
        try:
            store = create_redis_store() if settings.STORE_BACKEND == "redis" else InMemoryStore()
        except Exception:
            store = InMemoryStore()
        await save_activity(store, thread_id, stream.activity)
