from __future__ import annotations

import asyncio
import hashlib
import json
import re
import uuid
from dataclasses import asdict

from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile, File as FastAPIFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sse_starlette.sse import EventSourceResponse
from starlette.middleware.base import BaseHTTPMiddleware

from agents import (
    create_chat_agent,
    get_redis_file_store,
    stream_chat_agent,
)
from agents.deep_agent import (
    _enrich_itinerary_with_coordinates,
    _extract_chat_itinerary,
    _extract_comparison_from_text,
    _extract_itinerary_from_text,
    _find_fork_checkpoint,
    create_checkpointer,
    edit_chat_agent,
    regenerate_chat_agent,
)
from auth import verify_api_key
from cache import cache_client
from cancel_registry import cancel_stream, register_cancel, unregister_cancel
from config import REQUEST_TIMEOUT_SECONDS, logger, settings
from models import ChatRequest, FeedbackRequest, ThreadUpdateRequest
from oauth import (
    DEV_USER,
    SESSION_COOKIE_NAME,
    SESSION_TTL,
    create_session,
    delete_session,
    get_current_user,
    oauth,
    verify_admin,
)
from locale_utils import extract_locale, get_error_message
from sanitize import sanitize_prompt_input
from share_store import share_store
from threads import generate_summary, thread_store
from cost_store import cost_store
from feedback_store import feedback_store
from file_store import file_store

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


def _scoped_chat_thread_id(client_thread_id: str | None, user_id: str) -> str:
    """Namespace chat thread ids per user so checkpoints can't be resumed cross-user.

    Client-supplied ids are treated as opaque and stored under a user-scoped key.
    Already-scoped ids (resume) pass through unchanged.
    """
    user_tag = hashlib.sha256(user_id.encode()).hexdigest()[:12]
    prefix = f"chat:{user_tag}:"
    if client_thread_id and client_thread_id.startswith(prefix):
        return client_thread_id
    return prefix + (client_thread_id or uuid.uuid4().hex[:12])


def _sse(event: str, data: object) -> dict:
    return {"event": event, "data": json.dumps({"event": event, "data": data})}


def _truncate_tool_data(data, max_chars: int = 1000) -> str:
    """Truncate tool input/output to keep SSE payloads and stored data small."""
    if data is None:
        return None
    if isinstance(data, (dict, list)):
        import json as _json
        s = _json.dumps(data, default=str)
    else:
        s = str(data)
    return s[:max_chars] + ("..." if len(s) > max_chars else "")


def _parse_chat_event(
    event: dict,
    active_tasks: dict[str, str],
    subagent_run_ids: set[str] | None = None,
) -> list[dict]:
    """Map a stream event to SSE payloads.

    Handles synthetic envelopes (itinerary/done/error) plus raw langchain v2
    astream_events (on_chat_model_stream -> token, on_tool_start/on_tool_end
    for the task tool -> subagent status). `active_tasks` maps task tool
    run_id -> subagent_type so completion status names the right subagent.

    `subagent_run_ids` accumulates every `task` tool run_id seen so far (never
    popped, unlike `active_tasks`). Subagents dispatched via the `task` tool
    run concurrently and stream their own `on_chat_model_stream` events, which
    bubble up into this same event stream. Without filtering, those nested
    LLM chunks interleave with the orchestrator's own output and get
    concatenated into the same "token" channel — producing garbled text on
    the frontend. Any chat-model-stream event whose `parent_ids` chain
    includes a known task run_id is nested inside a subagent and must be
    excluded from "token"/"thinking" — that content already surfaces via the
    subagent's tool_start/tool_end/status events instead.
    """
    if subagent_run_ids is None:
        subagent_run_ids = set()
    event_type = event.get("event", "data")
    event_data = event.get("data")

    if event_type == "itinerary" and event_data is not None:
        return [_sse("itinerary", event_data)]
    if event_type == "comparison" and event_data is not None:
        return [_sse("comparison", event_data)]
    if event_type == "done":
        return [_sse("done", None)]
    if event_type == "cancelled":
        return [_sse("cancelled", None)]
    if event_type == "error":
        return [_sse("error", str(event_data))]
    if event_type == "subagent_progress":
        return [_sse("subagent_progress", event_data)]

    if event_type == "on_chat_model_stream":
        parent_ids = event.get("parent_ids") or []
        if subagent_run_ids and subagent_run_ids.intersection(parent_ids):
            return []
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
                if block_type in ("text-delta", "text") and block.get("text"):
                    payloads.append(_sse("token", block["text"]))
                elif block_type in ("reasoning", "reasoning-delta"):
                    reasoning_text = block.get("reasoning", "") or block.get("text", "")
                    if reasoning_text:
                        payloads.append(_sse("thinking", reasoning_text))
                elif block_type == "tool_use" and block.get("name") != "task":
                    payloads.append(_sse("status", {"tool": block["name"], "status": "running"}))
            return payloads
        return []

    if event_type == "on_tool_start":
        name = event.get("name", "")
        tool_input = event_data.get("input") if isinstance(event_data, dict) else None
        run_id = event.get("run_id", "")
        parent_ids = event.get("parent_ids") or []
        parent_run_id = None
        for pid in parent_ids:
            if pid in subagent_run_ids or pid in active_tasks:
                parent_run_id = pid
                break
        payloads: list[dict] = []
        if name == "task" and isinstance(tool_input, dict):
            subagent_type = tool_input.get("subagent_type")
            if subagent_type:
                if run_id:
                    active_tasks[run_id] = subagent_type
                    subagent_run_ids.add(run_id)
                payloads.append(_sse("status", {"tool": subagent_type, "status": "running"}))
                payloads.append(_sse("tool_start", {
                    "name": subagent_type,
                    "input": _truncate_tool_data(tool_input),
                    "run_id": run_id,
                }))
        else:
            ts_payload = {
                "name": name,
                "input": _truncate_tool_data(tool_input) if tool_input else None,
                "run_id": run_id,
            }
            if parent_run_id:
                ts_payload["parent_run_id"] = parent_run_id
            payloads.append(_sse("tool_start", ts_payload))
        return payloads

    if event_type == "on_tool_end":
        run_id = event.get("run_id", "")
        name = event.get("name", "")
        output = event_data.get("output") if isinstance(event_data, dict) else event_data
        parent_ids = event.get("parent_ids") or []
        parent_run_id = None
        for pid in parent_ids:
            if pid in subagent_run_ids or pid in active_tasks:
                parent_run_id = pid
                break
        payloads: list[dict] = []
        if run_id in active_tasks:
            subagent_type = active_tasks.pop(run_id)
            payloads.append(_sse("status", {"tool": subagent_type, "status": "done"}))
            payloads.append(_sse("tool_end", {
                "name": subagent_type,
                "output": _truncate_tool_data(output),
                "run_id": run_id,
            }))
        else:
            te_payload = {
                "name": name,
                "output": _truncate_tool_data(output),
                "run_id": run_id,
            }
            if parent_run_id:
                te_payload["parent_run_id"] = parent_run_id
            payloads.append(_sse("tool_end", te_payload))
        return payloads

    if event_type == "on_tool_error":
        run_id = event.get("run_id", "")
        name = event.get("name", "")
        error_msg = event_data.get("error") if isinstance(event_data, dict) else str(event_data)
        parent_ids = event.get("parent_ids") or []
        parent_run_id = None
        for pid in parent_ids:
            if pid in subagent_run_ids or pid in active_tasks:
                parent_run_id = pid
                break
        payloads: list[dict] = []
        if run_id in active_tasks:
            subagent_type = active_tasks.pop(run_id)
            payloads.append(_sse("status", {"tool": subagent_type, "status": "error"}))
            payloads.append(_sse("tool_error", {
                "name": subagent_type,
                "error": str(error_msg)[:500],
                "run_id": run_id,
            }))
        else:
            te_payload = {
                "name": name,
                "error": str(error_msg)[:500],
                "run_id": run_id,
            }
            if parent_run_id:
                te_payload["parent_run_id"] = parent_run_id
            payloads.append(_sse("tool_error", te_payload))
        return payloads

    if event_type == "on_chat_model_end":
        output = event_data.get("output") if isinstance(event_data, dict) else None
        if output is not None:
            usage = getattr(output, "usage_metadata", None)
            resp_meta = getattr(output, "response_metadata", None) or {}
            model_name = resp_meta.get("model_name", "") or resp_meta.get("model", "")
            if usage and isinstance(usage, dict):
                return [_sse("usage", {
                    "input_tokens": usage.get("input_tokens", 0),
                    "output_tokens": usage.get("output_tokens", 0),
                    "model": model_name,
                })]
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


# --- Admin cost analytics endpoints ---

@app.get(
    "/admin/costs",
    summary="Get aggregate cost analytics",
    tags=["admin"],
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("10/minute")
async def get_cost_analytics(
    request: Request,
    period: str = "week",
    admin: dict = Depends(verify_admin),
) -> dict:
    """Get aggregate cost analytics for a time period.

    Args:
        period: "day", "week", or "month".
    """
    if period not in ("day", "week", "month"):
        period = "week"
    stats = await cost_store.get_aggregate_stats(period=period)
    return JSONResponse(content=stats)


@app.get(
    "/admin/costs/threads/{thread_id}",
    summary="Get per-subagent cost breakdown for a thread",
    tags=["admin"],
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("30/minute")
async def get_thread_cost_breakdown(
    thread_id: str,
    request: Request,
    admin: dict = Depends(verify_admin),
) -> dict:
    """Get per-subagent cost breakdown for a specific conversation."""
    session_cost = await cost_store.get_session_cost(thread_id)
    subagent_breakdown = await cost_store.get_subagent_breakdown(thread_id)
    return JSONResponse(content={
        "session": session_cost,
        "subagents": subagent_breakdown,
    })


@app.get(
    "/admin/costs/export",
    summary="Export all cost records as CSV",
    tags=["admin"],
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("5/minute")
async def export_costs_csv(
    request: Request,
    admin: dict = Depends(verify_admin),
) -> PlainTextResponse:
    """Export all cost records as CSV for spreadsheet analysis."""
    import csv
    import io

    stats = await cost_store.get_aggregate_stats(period="month")
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["metric", "value"])
    writer.writerow(["total_cost", stats["total_cost"]])
    writer.writerow(["total_conversations", stats["total_conversations"]])
    writer.writerow(["avg_cost_per_conversation", stats["avg_cost_per_conversation"]])
    writer.writerow(["total_input_tokens", stats["total_input_tokens"]])
    writer.writerow(["total_output_tokens", stats["total_output_tokens"]])
    writer.writerow([])
    writer.writerow(["subagent", "cost", "input_tokens", "output_tokens"])
    for s in stats["per_subagent"]:
        writer.writerow([s["name"], s["cost"], s["input_tokens"], s["output_tokens"]])
    writer.writerow([])
    writer.writerow(["user_id", "cost"])
    for u in stats["top_users"]:
        writer.writerow([u["user_id"], u["cost"]])
    writer.writerow([])
    writer.writerow(["thread_id", "user_id", "efficiency_ratio", "cost"])
    for s in stats["poor_efficiency_sessions"]:
        writer.writerow([s["thread_id"], s["user_id"], s["efficiency_ratio"], s["cost"]])

    return PlainTextResponse(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=costs.csv"},
    )


# --- Feedback endpoints ---

@app.post(
    "/feedback",
    summary="Submit feedback for a message",
    tags=["feedback"],
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("30/minute")
async def submit_feedback(
    request: Request,
    body: FeedbackRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    """Submit or update thumbs up/down feedback for a specific message.

    One rating per user per message — submitting again overwrites the previous rating.
    """
    user_id = user["user_id"]
    result = await feedback_store.submit_feedback(
        user_id=user_id,
        message_id=body.message_id,
        thread_id=body.thread_id,
        rating=body.rating,
        comment=body.comment,
    )
    logger.info(
        "Feedback submitted: user=%s message=%s rating=%s",
        user_id,
        body.message_id,
        body.rating,
    )
    return result


@app.get(
    "/admin/feedback",
    summary="Get aggregate feedback stats",
    tags=["admin"],
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("10/minute")
async def get_feedback_stats(
    request: Request,
    admin: dict = Depends(verify_admin),
) -> JSONResponse:
    """Get aggregate feedback statistics for admin observability."""
    stats = await feedback_store.get_aggregate_stats()
    return JSONResponse(content=stats)


def _sanitize_preferences_sections(content: str) -> str:
    """Sanitize the <user_instructions> section of preferences content.

    Strips XML-like tags from the user_instructions section only,
    leaving the rest of the file (including <learned_preferences>) untouched.
    """
    if not content:
        return content

    instr_match = re.search(r"<user_instructions>\s*(.*?)\s*</user_instructions>", content, re.DOTALL)
    if not instr_match:
        return content

    raw_instr = instr_match.group(1)
    sanitized = re.sub(r"</?[\w-]+>", "", raw_instr).strip()
    return content[:instr_match.start(1)] + sanitized + content[instr_match.end(1):]


@app.get(
    "/preferences",
    summary="Get user preferences",
    tags=["preferences"],
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("30/minute")
async def get_preferences(request: Request, user: dict = Depends(get_current_user)) -> PlainTextResponse:
    user_id = user["user_id"]
    locale = extract_locale(request)
    logger.info("GET /preferences user=%s locale=%s", user_id, locale)
    try:
        store = get_redis_file_store()
        item = store.get((user_id,), "/preferences.md")
    except Exception:  # noqa: BLE001 (intentional fallback handler)
        logger.warning("Preferences store unavailable — returning empty preferences")
        return PlainTextResponse("", status_code=503)
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
async def put_preferences(request: Request, user: dict = Depends(get_current_user)) -> dict[str, str]:
    user_id = user["user_id"]
    locale = extract_locale(request)
    logger.info("PUT /preferences user=%s locale=%s", user_id, locale)
    body = await request.body()
    content = body.decode("utf-8") if body else ""
    content = _sanitize_preferences_sections(content)
    try:
        store = get_redis_file_store()
        store.put((user_id,), "/preferences.md", {"content": content, "encoding": "utf-8"})
    except Exception:  # noqa: BLE001 (intentional fallback handler)
        logger.warning("Preferences store unavailable — preferences not saved")
        return {"status": "error", "user_id": user_id, "error": "Preferences store unavailable"}
    logger.info("Saved preferences for user=%s (%d bytes)", user_id, len(content))
    return {"status": "ok", "user_id": user_id}


MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}


@app.post(
    "/upload",
    summary="Upload a file (image or PDF) for chat attachments",
    tags=["upload"],
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("10/minute")
async def upload_file(
    request: Request,
    file: UploadFile = FastAPIFile(...),
    user: dict = Depends(get_current_user),
) -> dict:
    user_id = user["user_id"]

    # Validate content type
    ct = file.content_type or ""
    if ct not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail="Unsupported file type. Use JPG, PNG, WebP, or PDF.")

    # Validate extension as fallback
    filename = file.filename or "upload"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Unsupported file extension. Use .jpg, .png, .webp, or .pdf.")

    # Read file data and validate size
    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File is too large (max 10MB).")
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Empty file.")

    result = await file_store.upload(user_id, filename, ct, data)
    logger.info("POST /upload — user=%s, file=%s, type=%s, size=%d", user_id, filename, ct, len(data))
    return result


@app.post(
    "/chat/stream",
    summary="Stream chat conversation with the travel agent",
    tags=["chat"],
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("20/minute")
async def chat_stream(
    chat_req: ChatRequest,
    request: Request,
    user: dict = Depends(get_current_user),
) -> EventSourceResponse:
    _msg_safe = sanitize_prompt_input(chat_req.message, "message")

    user_id = user["user_id"]
    thread_id = _scoped_chat_thread_id(chat_req.thread_id, user_id)

    # Determine locale: explicit request field takes priority, then Accept-Language header
    locale = extract_locale(request, chat_req.locale)

    logger.info(
        "POST /chat/stream — thread_id=%s, message_len=%d, user=%s, client_msg_id=%s",
        thread_id,
        len(_msg_safe),
        user_id,
        chat_req.client_message_id,
    )

    async def event_generator():
        yield _sse("thread_id", {"thread_id": thread_id})
        yield _sse("status", {"tool": "agent", "status": "thinking"})

        cancel_event = register_cancel(thread_id)
        active_tasks: dict[str, str] = {}
        subagent_run_ids: set[str] = set()
        stream_failed = False
        stream_text = ""
        was_cancelled = False

        # Mark thread as busy at the start of the stream
        try:
            await thread_store.update_status(user_id, thread_id, "busy")
        except Exception:  # noqa: BLE001, S110
            pass

        try:
            async for event in stream_chat_agent(
                message=_msg_safe,
                thread_id=thread_id,
                user_id=user_id,
                locale=locale,
                cancel_event=cancel_event,
                attachments=[a.model_dump() for a in chat_req.attachments] if chat_req.attachments else None,
            ):
                if cancel_event.is_set():
                    was_cancelled = True
                    yield _sse("cancelled", None)
                    break
                for payload in _parse_chat_event(event, active_tasks, subagent_run_ids):
                    if payload.get("event") == "token":
                        raw = json.loads(payload["data"])
                        stream_text += raw.get("data", "")
                    yield payload
        except Exception as exc:  # noqa: BLE001 (intentional fallback handler)
            logger.error(
                "Chat stream failed for thread=%s: %s",
                thread_id,
                exc,
                exc_info=True,
            )
            stream_failed = True
            yield _sse("error", get_error_message("streaming_failed", locale, error=str(exc)))
        finally:
            unregister_cancel(thread_id)
            # Save/update thread metadata with AI summary and status — never blocks stream
            try:
                final_status = "error" if stream_failed else "idle"
                summary = await generate_summary(_msg_safe, stream_text, locale=locale)
                await thread_store.upsert_thread(
                    user_id, thread_id, summary, status=final_status,
                    search_text=f"{_msg_safe[:500]} {stream_text[:500]}",
                )
            except Exception:  # noqa: BLE001 (intentional fallback handler)
                logger.warning("Failed to save thread metadata", exc_info=True)
                try:
                    await thread_store.upsert_thread(
                        user_id, thread_id, _msg_safe[:100], status="error" if stream_failed else "idle",
                        search_text=f"{_msg_safe[:500]} {stream_text[:500]}",
                    )
                except Exception:  # noqa: BLE001, S110
                    pass

    return EventSourceResponse(event_generator())


@app.post(
    "/chat/cancel",
    summary="Cancel an active chat stream",
    tags=["chat"],
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("30/minute")
async def chat_cancel(
    request: Request,
    body: dict,
    user: dict = Depends(get_current_user),
) -> dict:
    thread_id = body.get("thread_id", "")
    if not thread_id:
        raise HTTPException(status_code=400, detail="thread_id required")
    user_id = user["user_id"]
    scoped_thread_id = _scoped_chat_thread_id(thread_id, user_id)
    cancelled = cancel_stream(scoped_thread_id)
    return {"cancelled": cancelled}


@app.post(
    "/chat/regenerate",
    summary="Regenerate the last assistant response",
    tags=["chat"],
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("30/minute")
async def chat_regenerate(
    request: Request,
    body: dict,
    user: dict = Depends(get_current_user),
):
    raw_thread_id = body.get("thread_id", "")
    if not raw_thread_id:
        raise HTTPException(status_code=400, detail="thread_id required")

    user_id = user["user_id"]
    thread_id = _scoped_chat_thread_id(raw_thread_id, user_id)
    locale = extract_locale(request, body.get("locale"))

    logger.info("POST /chat/regenerate — thread_id=%s, user=%s", thread_id, user_id)

    async def event_generator():
        yield _sse("thread_id", {"thread_id": thread_id})
        yield _sse("status", {"tool": "agent", "status": "thinking"})

        cancel_event = register_cancel(thread_id)
        active_tasks: dict[str, str] = {}
        subagent_run_ids: set[str] = set()
        stream_failed = False
        stream_text = ""

        try:
            await thread_store.update_status(user_id, thread_id, "busy")
        except Exception:  # noqa: BLE001, S110
            pass

        try:
            async for event in regenerate_chat_agent(
                thread_id=thread_id,
                user_id=user_id,
                locale=locale,
                cancel_event=cancel_event,
            ):
                if cancel_event.is_set():
                    yield _sse("cancelled", None)
                    break
                for payload in _parse_chat_event(event, active_tasks, subagent_run_ids):
                    if payload.get("event") == "token":
                        raw = json.loads(payload["data"])
                        stream_text += raw.get("data", "")
                    yield payload
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Chat regenerate failed for thread=%s: %s",
                thread_id,
                exc,
                exc_info=True,
            )
            stream_failed = True
            yield _sse("error", get_error_message("streaming_failed", locale, error=str(exc)))
        finally:
            unregister_cancel(thread_id)
            try:
                final_status = "error" if stream_failed else "idle"
                summary = await generate_summary("", stream_text, locale=locale)
                await thread_store.upsert_thread(
                    user_id, thread_id, summary, status=final_status,
                    search_text=stream_text[:1000],
                )
            except Exception:  # noqa: BLE001
                logger.warning("Failed to save thread metadata after regenerate", exc_info=True)

    return EventSourceResponse(event_generator())


@app.post(
    "/chat/edit",
    summary="Edit the last user message and regenerate the assistant response",
    tags=["chat"],
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("30/minute")
async def chat_edit(
    request: Request,
    body: dict,
    user: dict = Depends(get_current_user),
):
    raw_thread_id = body.get("thread_id", "")
    if not raw_thread_id:
        raise HTTPException(status_code=400, detail="thread_id required")

    new_message = body.get("message", "")
    if not new_message:
        raise HTTPException(status_code=400, detail="message required")

    user_id = user["user_id"]
    thread_id = _scoped_chat_thread_id(raw_thread_id, user_id)
    locale = extract_locale(request, body.get("locale"))

    logger.info("POST /chat/edit — thread_id=%s, user=%s", thread_id, user_id)

    async def event_generator():
        yield _sse("thread_id", {"thread_id": thread_id})
        yield _sse("status", {"tool": "agent", "status": "thinking"})

        cancel_event = register_cancel(thread_id)
        active_tasks: dict[str, str] = {}
        subagent_run_ids: set[str] = set()
        stream_failed = False
        stream_text = ""

        try:
            await thread_store.update_status(user_id, thread_id, "busy")
        except Exception:  # noqa: BLE001, S110
            pass

        try:
            async for event in edit_chat_agent(
                thread_id=thread_id,
                new_message=new_message,
                user_id=user_id,
                locale=locale,
                cancel_event=cancel_event,
            ):
                if cancel_event.is_set():
                    yield _sse("cancelled", None)
                    break
                for payload in _parse_chat_event(event, active_tasks, subagent_run_ids):
                    if payload.get("event") == "token":
                        raw = json.loads(payload["data"])
                        stream_text += raw.get("data", "")
                    yield payload
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Chat edit failed for thread=%s: %s",
                thread_id,
                exc,
                exc_info=True,
            )
            stream_failed = True
            yield _sse("error", get_error_message("streaming_failed", locale, error=str(exc)))
        finally:
            unregister_cancel(thread_id)
            try:
                final_status = "error" if stream_failed else "idle"
                summary = await generate_summary(new_message, stream_text, locale=locale)
                await thread_store.upsert_thread(
                    user_id, thread_id, summary, status=final_status,
                    search_text=f"{new_message[:500]} {stream_text[:500]}",
                )
            except Exception:  # noqa: BLE001
                logger.warning("Failed to save thread metadata after edit", exc_info=True)

    return EventSourceResponse(event_generator())


@app.get(
    "/threads",
    summary="List user's recent threads",
    tags=["threads"],
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("30/minute")
async def list_threads(
    request: Request,
    offset: int = 0,
    limit: int = 20,
    user: dict = Depends(get_current_user),
) -> dict:
    user_id = user["user_id"]
    locale = extract_locale(request)
    logger.info("GET /threads user=%s locale=%s offset=%d", user_id, locale, offset)
    threads = await thread_store.list_threads(user_id, limit=limit, offset=offset)
    total = await thread_store.count_threads(user_id)
    return JSONResponse(
        content={
            "threads": [asdict(t) for t in threads],
            "has_more": (offset + limit) < total,
        },
        headers={"Cache-Control": "public, max-age=300"},
    )


@app.get(
    "/threads/search",
    summary="Search across all user's thread messages",
    tags=["threads"],
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("30/minute")
async def search_threads(
    request: Request,
    q: str = "",
    offset: int = 0,
    limit: int = 20,
    user: dict = Depends(get_current_user),
) -> dict:
    """Full-text search across all user's thread message content."""
    if not q.strip():
        return JSONResponse(content={"results": [], "total": 0, "has_more": False})
    user_id = user["user_id"]
    logger.info("GET /threads/search q=%s user=%s offset=%d", q[:50], user_id, offset)
    results, total = await thread_store.search_threads(
        user_id, q.strip(), limit=limit, offset=offset
    )
    return JSONResponse(content={
        "results": results,
        "total": total,
        "has_more": (offset + limit) < total,
    })


@app.get(
    "/threads/{thread_id}/history",
    summary="Get thread message history",
    tags=["threads"],
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("30/minute")
async def get_thread_history(
    thread_id: str,
    request: Request,
    checkpoint_id: str | None = None,
    user: dict = Depends(get_current_user),
) -> list[dict]:
    user_id = user["user_id"]
    locale = extract_locale(request)
    logger.info("GET /threads/%s/history user=%s locale=%s checkpoint_id=%s", thread_id, user_id, locale, checkpoint_id)

    # Security: verify the thread belongs to this user
    user_tag = hashlib.sha256(user_id.encode()).hexdigest()[:12]
    if not thread_id.startswith(f"chat:{user_tag}:"):
        raise HTTPException(status_code=403, detail="Thread does not belong to this user")

    try:
        agent = await create_chat_agent(user_id=user_id)
        config = {
            "configurable": {"thread_id": thread_id, "user_id": user_id},
            "recursion_limit": 100,
        }
        if checkpoint_id:
            config["configurable"]["checkpoint_id"] = checkpoint_id
        state = await agent.aget_state(config)
    except Exception:  # noqa: BLE001 (intentional fallback handler)
        logger.warning("Failed to load thread history for %s", thread_id, exc_info=True)
        raise HTTPException(status_code=503, detail="Failed to load thread history")

    if state is None or not state.values or not state.values.get("messages"):
        raise HTTPException(status_code=404, detail="Thread not found or empty")

    messages = state.values.get("messages", [])
    result: list[dict] = []

    # Load persisted activity metadata for this thread
    activity_data = None
    try:
        from agents.activity_store import load_activity as _load_activity
        from agents.deep_agent import create_redis_store as _create_store
        from langgraph.store.memory import InMemoryStore as _InMemStore
        _store = _create_store() if settings.STORE_BACKEND == "redis" else _InMemStore()
        activity_data = await _load_activity(_store, thread_id)
    except Exception:
        pass

    for msg in messages:
        role = "user" if getattr(msg, "type", "") == "human" else "assistant"
        content = getattr(msg, "content", "")
        if not isinstance(content, str):
            content = str(content)
        if content.strip():
            entry: dict = {"role": role, "content": content}
            if role == "assistant":
                itinerary = _extract_itinerary_from_text(content)
                comparison = _extract_comparison_from_text(content)
                if itinerary:
                    itinerary = await _enrich_itinerary_with_coordinates(itinerary)
                    entry["itinerary"] = itinerary
                if comparison:
                    entry["comparison"] = comparison
            result.append(entry)

    # Attach activity metadata to the last assistant message
    if activity_data and result:
        for entry in reversed(result):
            if entry.get("role") == "assistant":
                entry["activity"] = activity_data
                break

    return JSONResponse(
        content=result,
        headers={"Cache-Control": "public, max-age=300"},
    )


@app.get(
    "/threads/{thread_id}/branches",
    summary="List branches for the last assistant response",
    tags=["threads"],
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("30/minute")
async def get_thread_branches(
    thread_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict:
    user_id = user["user_id"]
    logger.info("GET /threads/%s/branches user=%s", thread_id, user_id)

    # Security: verify the thread belongs to this user
    user_tag = hashlib.sha256(user_id.encode()).hexdigest()[:12]
    if not thread_id.startswith(f"chat:{user_tag}:"):
        raise HTTPException(status_code=403, detail="Thread does not belong to this user")

    try:
        agent = await create_chat_agent(user_id=user_id)
        config = {
            "configurable": {"thread_id": thread_id, "user_id": user_id},
            "recursion_limit": 100,
        }

        # Find the fork point (checkpoint before last assistant response)
        fork_config = await _find_fork_checkpoint(agent, config)
        if fork_config is None:
            return {"branches": []}

        fork_checkpoint_id = fork_config.get("configurable", {}).get("checkpoint_id", "")

        # Get current state's checkpoint_id
        current_state = await agent.aget_state(config)
        current_checkpoint_id = ""
        if current_state and current_state.config:
            current_checkpoint_id = current_state.config.get("configurable", {}).get("checkpoint_id", "")

        # Iterate state history to find all branches from the same fork point
        branches: list[dict] = []
        seen_checkpoint_ids: set[str] = set()

        async for snapshot in agent.aget_state_history(config):
            parent_config = snapshot.parent_config
            if parent_config is None:
                continue
            parent_checkpoint_id = parent_config.get("configurable", {}).get("checkpoint_id", "")

            # Only include checkpoints whose parent is the fork point
            if parent_checkpoint_id != fork_checkpoint_id:
                continue

            snap_checkpoint_id = snapshot.config.get("configurable", {}).get("checkpoint_id", "")
            if snap_checkpoint_id in seen_checkpoint_ids:
                continue
            seen_checkpoint_ids.add(snap_checkpoint_id)

            # Get the last message content for this branch (for display)
            messages = snapshot.values.get("messages", [])
            last_content = ""
            if messages:
                last_msg = messages[-1]
                last_content = getattr(last_msg, "content", "")
                if not isinstance(last_content, str):
                    last_content = str(last_content)

            branches.append({
                "checkpoint_id": snap_checkpoint_id,
                "is_current": snap_checkpoint_id == current_checkpoint_id,
                "preview": last_content[:200],
            })

    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to load branches for %s: %s", thread_id, exc, exc_info=True)
        raise HTTPException(status_code=503, detail="Failed to load branches")

    return {"branches": branches}


@app.delete(
    "/threads/{thread_id}",
    summary="Delete a thread",
    tags=["threads"],
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("30/minute")
async def delete_thread(
    thread_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict:
    user_id = user["user_id"]

    # Security: verify ownership via prefix check
    user_tag = hashlib.sha256(user_id.encode()).hexdigest()[:12]
    if not thread_id.startswith(f"chat:{user_tag}:"):
        raise HTTPException(status_code=403, detail="Thread does not belong to this user")

    deleted = await thread_store.delete_thread(user_id, thread_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Also clean up the underlying checkpointer state (message history, agent state)
    try:
        checkpointer = await create_checkpointer()
        config = {"configurable": {"thread_id": thread_id}}
        if hasattr(checkpointer, "adelete_thread"):
            await checkpointer.adelete_thread(config)
    except Exception:  # noqa: BLE001 (intentional fallback handler)
        logger.warning("Failed to delete checkpoint state for %s", thread_id, exc_info=True)

    logger.info("Deleted thread metadata + checkpoint for user=%s thread=%s", user_id, thread_id)
    return {"status": "ok", "thread_id": thread_id}


@app.patch(
    "/threads/{thread_id}",
    summary="Update thread metadata (e.g., pin/unpin)",
    tags=["threads"],
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("30/minute")
async def update_thread(
    thread_id: str,
    request: Request,
    body: ThreadUpdateRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    user_id = user["user_id"]

    # Security: verify ownership via prefix check
    user_tag = hashlib.sha256(user_id.encode()).hexdigest()[:12]
    if not thread_id.startswith(f"chat:{user_tag}:"):
        raise HTTPException(status_code=403, detail="Thread does not belong to this user")

    if body.pinned is not None:
        ok = await thread_store.update_pin_status(user_id, thread_id, body.pinned)
        if not ok:
            raise HTTPException(status_code=404, detail="Thread not found")
        logger.info("PATCH /threads/%s pinned=%s user=%s", thread_id, body.pinned, user_id)

    return JSONResponse(content={"status": "ok", "thread_id": thread_id})


@app.get("/auth/login", summary="Google OAuth login", tags=["auth"])
async def auth_login(request: Request) -> RedirectResponse:
    """Redirect to Google OAuth consent screen (or dev-bypass session)."""
    if settings.AUTH_DEV_BYPASS:
        session_id = await create_session(DEV_USER)
        resp = RedirectResponse(url="http://localhost:3000/auth/callback?success=1")
        resp.set_cookie(
            SESSION_COOKIE_NAME, session_id,
            max_age=SESSION_TTL, httponly=True, samesite="lax",
        )
        return resp
    redirect_uri = settings.OAUTH_REDIRECT_URI
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get("/auth/callback", summary="OAuth callback handler", tags=["auth"])
async def auth_callback(request: Request) -> RedirectResponse:
    """Handle Google OAuth callback — exchange code for user info, create session."""
    token = await oauth.google.authorize_access_token(request)
    user_info = token.get("userinfo") or {}
    email = user_info.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="No email in Google response")
    session_data = {
        "user_id": email,
        "display_name": user_info.get("name", email.split("@")[0]),
        "avatar_url": user_info.get("picture"),
        "email": email,
    }
    session_id = await create_session(session_data)
    resp = RedirectResponse(url="http://localhost:3000/auth/callback?success=1")
    resp.set_cookie(
        SESSION_COOKIE_NAME, session_id,
        max_age=SESSION_TTL, httponly=True, samesite="lax",
    )
    return resp


@app.post("/auth/logout", summary="Logout", tags=["auth"])
async def auth_logout(request: Request) -> JSONResponse:
    """Clear session cookie and delete session from Redis."""
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id:
        await delete_session(session_id)
    response = JSONResponse({"status": "ok"})
    response.delete_cookie(SESSION_COOKIE_NAME)
    return response


@app.get("/auth/me", summary="Get current user", tags=["auth"])
async def auth_me(user: dict = Depends(get_current_user)) -> dict:
    """Return current user info from session."""
    return user


# ─── Share & Export endpoints ───────────────────────────────────


def _itinerary_to_markdown(itinerary: dict) -> str:
    """Convert an itinerary dict to a readable Markdown document."""
    lines = [
        f"# {itinerary.get('destination', 'Trip Itinerary')}",
        "",
        f"**Duration:** {itinerary.get('total_days', '?')} days  ",
        f"**Estimated Cost:** ${itinerary.get('estimated_total_cost_usd', 'N/A')}  ",
        f"**Budget Status:** {itinerary.get('budget_status', 'N/A')}  ",
        f"**Visa Note:** {itinerary.get('visa_note', 'N/A')}  ",
        f"**Best Season:** {itinerary.get('best_season_note', 'N/A')}",
        "",
    ]
    for day in itinerary.get("days", []):
        lines.append(f"## Day {day.get('day', '?')} — {day.get('theme', '')}")
        lines.append("")
        for slot_name in ("morning", "afternoon", "evening"):
            slot = day.get(slot_name)
            if slot:
                lines.append(f"**{slot_name.title()}:** {slot.get('activity', '—')} at {slot.get('location', '—')} (${slot.get('cost_usd', 0)}, {slot.get('duration', '')})")
        lines.append(f"**Transport:** {day.get('transport', 'N/A')}")
        lines.append(f"**Accommodation:** {day.get('accommodation', 'N/A')}")
        lines.append(f"**Daily Cost:** ${day.get('daily_cost_usd', 'N/A')}")
        tips = day.get("tips", [])
        if tips:
            lines.append("**Tips:**")
            for tip in tips:
                lines.append(f"- {tip}")
        lines.append("")
    warnings = itinerary.get("warnings", [])
    if warnings:
        lines.append("## ⚠ Warnings")
        for w in warnings:
            lines.append(f"- {w}")
        lines.append("")
    packing = itinerary.get("packing_essentials", [])
    if packing:
        lines.append("## 🎒 Packing Essentials")
        for item in packing:
            lines.append(f"- {item}")
        lines.append("")
    return "\n".join(lines)


async def _get_latest_itinerary(thread_id: str, user_id: str) -> dict | None:
    """Extract the latest itinerary from a thread's checkpointer state."""
    user_tag = hashlib.sha256(user_id.encode()).hexdigest()[:12]
    if not thread_id.startswith(f"chat:{user_tag}:"):
        return None
    try:
        agent = await create_chat_agent(user_id=user_id)
        config = {
            "configurable": {"thread_id": thread_id, "user_id": user_id},
            "recursion_limit": 100,
        }
        state = await agent.aget_state(config)
    except Exception:  # noqa: BLE001
        logger.warning("Failed to load state for export/share thread=%s", thread_id, exc_info=True)
        return None
    if state is None or not state.values:
        return None
    return _extract_chat_itinerary(state.values)


@app.post(
    "/share/{thread_id}",
    summary="Create a shareable link for an itinerary",
    tags=["share"],
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("10/minute")
async def create_share_link(
    thread_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict:
    user_id = user["user_id"]
    itinerary = await _get_latest_itinerary(thread_id, user_id)
    if itinerary is None:
        raise HTTPException(status_code=404, detail="No itinerary found in this thread")
    itinerary = await _enrich_itinerary_with_coordinates(itinerary)
    destination = itinerary.get("destination", "Untitled Trip")
    itinerary_json = json.dumps(itinerary)
    token, expires_at = await share_store.create_share(
        user_id, thread_id, itinerary_json, destination,
    )
    locale = extract_locale(request) or "en"
    share_url = f"http://localhost:3000/{locale}/share/{token}"
    logger.info("Created share link for user=%s thread=%s token=%s", user_id, thread_id, token[:8])
    return {"share_url": share_url, "expires_at": expires_at, "destination": destination}


@app.get(
    "/share/{token}",
    summary="Get shared itinerary (public, no auth)",
    tags=["share"],
)
@limiter.limit("60/minute")
async def get_shared_itinerary(
    token: str,
    request: Request,
) -> dict:
    data = await share_store.get_share(token)
    if data is None:
        raise HTTPException(status_code=404, detail="Share link not found or expired")
    try:
        itinerary = json.loads(data["itinerary_json"])
    except (json.JSONDecodeError, KeyError):
        raise HTTPException(status_code=500, detail="Corrupted share data")
    return {
        "itinerary": itinerary,
        "destination": data["destination"],
        "created_at": data["created_at"],
        "expires_at": data["expires_at"],
    }


@app.delete(
    "/share/{token}",
    summary="Revoke a share link",
    tags=["share"],
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("20/minute")
async def revoke_share_link(
    token: str,
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict:
    user_id = user["user_id"]
    revoked = await share_store.revoke_share(user_id, token)
    if not revoked:
        raise HTTPException(status_code=404, detail="Share link not found")
    logger.info("Revoked share link for user=%s token=%s", user_id, token[:8])
    return {"status": "ok"}


@app.get(
    "/shares",
    summary="List user's active share links",
    tags=["share"],
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("30/minute")
async def list_shares(
    request: Request,
    user: dict = Depends(get_current_user),
) -> list[dict]:
    user_id = user["user_id"]
    shares = await share_store.list_shares(user_id)
    return [
        {
            "token": s.token,
            "thread_id": s.thread_id,
            "destination": s.destination,
            "created_at": s.created_at,
            "expires_at": s.expires_at,
            "share_url": f"http://localhost:3000/share/{s.token}",
        }
        for s in shares
    ]


@app.get(
    "/export/{thread_id}",
    summary="Export itinerary as JSON or Markdown",
    tags=["export"],
    dependencies=[Depends(verify_api_key)],
    response_model=None,
)
@limiter.limit("10/minute")
async def export_itinerary(
    thread_id: str,
    request: Request,
    fmt: str = "json",
    user: dict = Depends(get_current_user),
) -> JSONResponse | PlainTextResponse:
    user_id = user["user_id"]
    itinerary = await _get_latest_itinerary(thread_id, user_id)
    if itinerary is None:
        raise HTTPException(status_code=404, detail="No itinerary found in this thread")
    itinerary = await _enrich_itinerary_with_coordinates(itinerary)
    if fmt == "markdown":
        md = _itinerary_to_markdown(itinerary)
        return PlainTextResponse(
            md,
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="{itinerary.get("destination", "itinerary").replace(" ", "_")}.md"'},
        )
    return JSONResponse(
        itinerary,
        headers={"Content-Disposition": f'attachment; filename="{itinerary.get("destination", "itinerary").replace(" ", "_")}.json"'},
    )


@app.on_event("startup")
async def _start_thread_cleanup_task() -> None:
    """Launch a background task that periodically cleans up expired thread checkpoints."""

    async def _cleanup_loop() -> None:
        while True:
            await asyncio.sleep(3600)  # run every hour
            try:
                expired = await thread_store.cleanup_expired_threads()
                if expired:
                    logger.info("Cleaning up %d expired thread checkpoints", len(expired))
                    checkpointer = await create_checkpointer()
                    for tid in expired:
                        try:
                            config = {"configurable": {"thread_id": tid}}
                            if hasattr(checkpointer, "adelete_thread"):
                                await checkpointer.adelete_thread(config)
                        except Exception:  # noqa: BLE001, S110
                            pass
            except Exception:  # noqa: BLE001
                logger.warning("Thread cleanup task error", exc_info=True)

    asyncio.create_task(_cleanup_loop())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
