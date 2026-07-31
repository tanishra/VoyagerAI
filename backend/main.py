from __future__ import annotations

import asyncio
import json
import uuid

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sse_starlette.sse import EventSourceResponse
from starlette.middleware.base import BaseHTTPMiddleware

from agents import (
    get_redis_file_store,
    run_travel_agent,
    stream_chat_agent,
    stream_travel_agent,
)
from auth import verify_api_key
from cache import cache_client
from config import REQUEST_TIMEOUT_SECONDS, logger, settings
from models import ChatRequest, Itinerary, PlanRequest, PlanResponse, ReplanRequest
from sanitize import sanitize_prompt_input

ALLOWED_ORIGINS: list[str] = [
    orig.strip()
    for orig in settings.CORS_ORIGINS.split(",")
    if orig.strip()
]

if settings.AUTH_MODE == "production" and not ALLOWED_ORIGINS:
    raise RuntimeError(
        "CORS_ORIGINS must be set to an explicit allowlist when AUTH_MODE=production"
    )

app = FastAPI(
    title="Travel Planning AI Agent",
    version="2.2.0",
    description="Generates, validates, and enriches multi-day travel itineraries using DeepAgent.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TimeoutMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT_SECONDS):
                return await call_next(request)
        except asyncio.TimeoutError:
            return PlainTextResponse("Request timed out", status_code=503)


app.add_middleware(TimeoutMiddleware)

limiter = Limiter(key_func=get_remote_address, default_limits=["30/hour"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


def _resolve_user_id(request: Request) -> str:
    return request.headers.get("x-user-id") or request.query_params.get("user_id", "anonymous")


def _sse(event: str, data: object) -> dict:
    return {"event": event, "data": json.dumps({"event": event, "data": data})}


def _parse_chat_event(event: dict, active_tasks: dict[str, str]) -> list[dict]:
    """Map a stream event to SSE payloads.

    Handles synthetic envelopes (itinerary/done/error) plus raw langchain v2
    astream_events (on_chat_model_stream -> token, on_tool_start/on_tool_end
    for the task tool -> subagent status). `active_tasks` maps task tool
    run_id -> subagent_type so completion status names the right subagent.
    """
    event_type = event.get("event", "data")
    event_data = event.get("data")

    if event_type == "itinerary" and event_data is not None:
        return [_sse("itinerary", event_data)]
    if event_type == "done":
        return [_sse("done", None)]
    if event_type == "error":
        return [_sse("error", str(event_data))]

    if event_type == "on_chat_model_stream":
        chunk = event_data.get("chunk") if isinstance(event_data, dict) else None
        if chunk is None:
            return []
        content = getattr(chunk, "content", None)
        if isinstance(content, str):
            return [_sse("token", content)] if content else []
        if isinstance(content, list):
            payloads: list[dict] = []
            for block in content:
                if not isinstance(block, dict):
                    continue
                block_type = block.get("type", "")
                if block_type == "text-delta" and block.get("text"):
                    payloads.append(_sse("token", block["text"]))
                elif block_type == "tool_use" and block.get("name") != "task":
                    payloads.append(_sse("status", {"tool": block["name"], "status": "running"}))
            return payloads
        return []

    if event_type == "on_tool_start":
        name = event.get("name", "")
        tool_input = event_data.get("input") if isinstance(event_data, dict) else None
        if name == "task" and isinstance(tool_input, dict):
            subagent_type = tool_input.get("subagent_type")
            if subagent_type:
                run_id = event.get("run_id", "")
                if run_id:
                    active_tasks[run_id] = subagent_type
                return [_sse("status", {"tool": subagent_type, "status": "running"})]
        return []

    if event_type == "on_tool_end":
        run_id = event.get("run_id", "")
        if run_id in active_tasks:
            subagent_type = active_tasks.pop(run_id)
            return [_sse("status", {"tool": subagent_type, "status": "done"})]
        return []

    return []


@app.get("/health", summary="Health check", tags=["ops"])
async def health() -> dict[str, str]:
    redis_ok = await cache_client.ping()
    return {
        "status": "ok" if redis_ok else "degraded",
        "redis": "connected" if redis_ok else "unavailable",
        "agent": "deepagent",
    }


@app.get(
    "/preferences",
    summary="Get user preferences",
    tags=["preferences"],
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("30/minute")
async def get_preferences(request: Request) -> PlainTextResponse:
    user_id = _resolve_user_id(request)
    store = get_redis_file_store()
    item = store.get((user_id,), "/preferences.md")
    if item is None:
        return PlainTextResponse("", status_code=200)
    content = item.value.get("content", "")
    return PlainTextResponse(content, status_code=200)


@app.put(
    "/preferences",
    summary="Save user preferences",
    tags=["preferences"],
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("30/minute")
async def put_preferences(request: Request) -> dict[str, str]:
    user_id = _resolve_user_id(request)
    body = await request.body()
    content = body.decode("utf-8") if body else ""
    store = get_redis_file_store()
    store.put((user_id,), "/preferences.md", {"content": content, "encoding": "utf-8"})
    logger.info("Saved preferences for user=%s (%d bytes)", user_id, len(content))
    return {"status": "ok", "user_id": user_id}


@app.post(
    "/plan",
    response_model=PlanResponse,
    summary="Generate travel plan",
    tags=["planning"],
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("5/minute")
async def plan(plan_req: PlanRequest, request: Request) -> PlanResponse:
    logger.info(
        "POST /plan — destination=%s, days=%d, budget=%d, style=%s, group=%s",
        plan_req.destination,
        plan_req.days,
        plan_req.budget_usd,
        plan_req.travel_style.value,
        plan_req.group_type.value,
    )

    cached = await cache_client.get(plan_req)
    if cached is not None:
        logger.info("Cache HIT for %s", plan_req.destination)
        itinerary = Itinerary.model_validate(cached)
        return PlanResponse(success=True, itinerary=itinerary)

    _dest_safe = sanitize_prompt_input(plan_req.destination, "destination")
    _diet_safe = sanitize_prompt_input(plan_req.dietary, "dietary")
    _constr_safe = sanitize_prompt_input(plan_req.constraints, "constraints")

    user_message = (
        f"Plan a {plan_req.days}-day trip to {_dest_safe}. "
        f"Budget: ${plan_req.budget_usd} USD. "
        f"Style: {plan_req.travel_style.value}. "
        f"Group: {plan_req.group_type.value}. "
        f"Dietary: {_diet_safe or 'None'}. "
        f"Constraints: {_constr_safe or 'None'}."
    )

    try:
        user_id = _resolve_user_id(request)
        thread_id = f"plan:{user_id}:{plan_req.destination}:{plan_req.days}:{plan_req.budget_usd}"

        raw_itinerary = await run_travel_agent(
            user_message=user_message,
            thread_id=thread_id,
            user_id=user_id,
        )

        itinerary = Itinerary.model_validate(raw_itinerary)
        await cache_client.set(plan_req, itinerary.model_dump())

        return PlanResponse(success=True, itinerary=itinerary)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 (intentional fallback handler)
        logger.error("Unexpected error in /plan: %s", exc)
        return PlanResponse(success=False, error=f"Planning failed: {exc}")


@app.post(
    "/plan/stream",
    summary="Stream travel plan generation",
    tags=["planning"],
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("5/minute")
async def plan_stream(plan_req: PlanRequest, request: Request) -> EventSourceResponse:
    _dest_safe = sanitize_prompt_input(plan_req.destination, "destination")
    _diet_safe = sanitize_prompt_input(plan_req.dietary, "dietary")
    _constr_safe = sanitize_prompt_input(plan_req.constraints, "constraints")

    user_message = (
        f"Plan a {plan_req.days}-day trip to {_dest_safe}. "
        f"Budget: ${plan_req.budget_usd} USD. "
        f"Style: {plan_req.travel_style.value}. "
        f"Group: {plan_req.group_type.value}. "
        f"Dietary: {_diet_safe or 'None'}. "
        f"Constraints: {_constr_safe or 'None'}."
    )

    cached = await cache_client.get(plan_req)
    if cached is not None:
        logger.info("Stream cache HIT for %s", plan_req.destination)
        async def cached_generator():
            yield {
                "event": "final",
                "data": json.dumps({"event": "final", "data": cached}),
            }
        return EventSourceResponse(cached_generator())

    user_id = _resolve_user_id(request)
    request_id = uuid.uuid4().hex[:8]
    thread_id = f"plan:{plan_req.destination}:{plan_req.days}:{plan_req.budget_usd}:{request_id}"

    async def event_generator():
        itinerary_result = None
        async for event in stream_travel_agent(
            user_message=user_message,
            thread_id=thread_id,
            user_id=user_id,
        ):
            if event.get("event") == "final":
                itinerary_result = event.get("data")
            yield {
                "event": event.get("event", "data"),
                "data": json.dumps(event),
            }
        if itinerary_result:
            try:
                validated = Itinerary.model_validate(itinerary_result)
                await cache_client.set(plan_req, validated.model_dump())
            except Exception:  # noqa: BLE001 (intentional fallback handler)
                logger.warning("Failed to cache stream result", exc_info=True)

    return EventSourceResponse(event_generator())


@app.post(
    "/replan-day",
    response_model=PlanResponse,
    summary="Replan a specific day",
    tags=["planning"],
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("10/minute")
async def replan_day(replan_req: ReplanRequest, request: Request) -> PlanResponse:
    logger.info(
        "POST /replan-day — day=%d, reason=%s",
        replan_req.day_number,
        replan_req.reason[:80],
    )

    if replan_req.day_number > replan_req.itinerary.total_days or replan_req.day_number < 1:
        raise HTTPException(
            status_code=400,
            detail=f"Day {replan_req.day_number} is out of range. "
                   f"Itinerary has {replan_req.itinerary.total_days} days.",
        )

    itinerary_dict = replan_req.itinerary.model_dump()
    _reason_safe = sanitize_prompt_input(replan_req.reason, "reason")

    user_message = (
        f"Here is the current itinerary:\n"
        f"{json.dumps(itinerary_dict, indent=2)}\n\n"
        f"Please replan Day {replan_req.day_number}.\n"
        f"Reason: {_reason_safe}\n\n"
        f"Return the COMPLETE updated itinerary (all days) as JSON."
    )

    try:
        user_id = _resolve_user_id(request)
        thread_id = f"replan:{replan_req.day_number}:{hash(json.dumps(itinerary_dict, sort_keys=True))}"

        raw_itinerary = await run_travel_agent(
            user_message=user_message,
            thread_id=thread_id,
            user_id=user_id,
        )

        itinerary = Itinerary.model_validate(raw_itinerary)
        return PlanResponse(success=True, itinerary=itinerary)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 (intentional fallback handler)
        logger.error("Unexpected error in /replan-day: %s", exc)
        return PlanResponse(success=False, error=f"Replanning failed: {exc}")


@app.post(
    "/chat/stream",
    summary="Stream chat conversation with the travel agent",
    tags=["chat"],
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("20/minute")
async def chat_stream(chat_req: ChatRequest, request: Request) -> EventSourceResponse:
    _msg_safe = sanitize_prompt_input(chat_req.message, "message")

    user_id = _resolve_user_id(request)
    thread_id = chat_req.thread_id or f"chat:{user_id}:{uuid.uuid4().hex[:12]}"

    logger.info(
        "POST /chat/stream — thread_id=%s, message_len=%d, user=%s",
        thread_id,
        len(_msg_safe),
        user_id,
    )

    async def event_generator():
        yield _sse("thread_id", {"thread_id": thread_id})
        yield _sse("status", {"tool": "agent", "status": "thinking"})

        active_tasks: dict[str, str] = {}

        async for event in stream_chat_agent(
            message=_msg_safe,
            thread_id=thread_id,
            user_id=user_id,
        ):
            for payload in _parse_chat_event(event, active_tasks):
                yield payload

    return EventSourceResponse(event_generator())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
