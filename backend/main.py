from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import re
import secrets
import uuid
from dataclasses import asdict

from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile, File as FastAPIFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from pydantic import ValidationError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sse_starlette.sse import EventSourceResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

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
    _strip_structured_tags,
    create_checkpointer,
    edit_chat_agent,
    edit_itinerary_agent,
    regenerate_chat_agent,
)
from agents.prompts import (
    _dict_to_learned_preferences_text,
    _parse_learned_preferences_to_dict,
    _parse_preferences,
    _sanitize_instructions,
    extract_stated_currency,
)
from auth import verify_api_key
from cache import cache_client
from cancel_registry import cancel_stream, register_cancel, unregister_cancel
from config import REQUEST_TIMEOUT_SECONDS, logger, settings
from logging_config import generate_request_id, set_request_context
from models import (
    AuthLogoutResponse,
    AuthMeResponse,
    CacheInvalidateResponse,
    ChatCancelResponse,
    ChatRequest,
    CooldownListResponse,
    CooldownRemoveResponse,
    CostAnalyticsResponse,
    FeedbackRequest,
    FeedbackStatsResponse,
    FeedbackSubmitResponse,
    HealthResponse,
    PreferencesSaveResponse,
    SecurityFlagsResponse,
    ShareCreateResponse,
    ShareGetResponse,
    ShareListItem,
    ShareRevokeResponse,
    ThreadBranchesResponse,
    ThreadCostBreakdownResponse,
    ThreadDeleteResponse,
    ThreadListResponse,
    ThreadMessage,
    ThreadSearchResponse,
    ThreadUpdateRequest,
    ThreadUpdateResponse,
    UploadResponse,
)
from oauth import (
    DEV_USER,
    SESSION_COOKIE_NAME,
    SESSION_TTL,
    create_session,
    delete_session,
    get_current_user,
    is_admin_email,
    oauth,
    verify_admin,
)
from locale_utils import classify_exception, extract_locale, get_error_message
from sanitize import sanitize_prompt_input, sanitize_prompt_input_detailed
from share_store import share_store
from agents.tools.pipeline_tools import is_pipeline_tool
from agents.tools.visuals import generate_destination_image
from threads import generate_summary, thread_store
from cost_store import cost_store
from feedback_store import feedback_store
from research_cache import research_cache
from ical_generator import generate_ics
from file_store import file_store
from guard import classify_injection_risk
from security_store import security_store
from observability_store import observability_store

ALLOWED_ORIGINS: list[str] = [
    orig.strip()
    for orig in settings.CORS_ORIGINS.split(",")
    if orig.strip()
]

if settings.AUTH_MODE == "production" and not ALLOWED_ORIGINS:
    raise RuntimeError(
        "CORS_ORIGINS must be set to an explicit allowlist when AUTH_MODE=production"
    )


def _frontend_base_url() -> str:
    """Public-facing frontend URL for links we hand to users (share links,
    OAuth redirects). Prefers the first https CORS origin; falls back to the
    first non-wildcard origin, then localhost for dev."""
    frontend_url = "http://localhost:3000"
    if ALLOWED_ORIGINS:
        https_origins = [o for o in ALLOWED_ORIGINS if o.startswith("https://")]
        if https_origins:
            frontend_url = https_origins[0]
        elif ALLOWED_ORIGINS[0] != "*":
            frontend_url = ALLOWED_ORIGINS[0]
    return frontend_url.rstrip("/")

# --- Production startup guards ---
if settings.AUTH_MODE == "production":
    if not settings.SESSION_SECRET_KEY or settings.SESSION_SECRET_KEY == "dev-only-insecure-key-change-in-production":
        raise RuntimeError(
            "SESSION_SECRET_KEY must be set to a strong random string in production mode. "
            'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(32))"'
        )
    if not settings.API_AUTH_KEY:
        raise RuntimeError(
            "API_AUTH_KEY must be set in production mode."
        )
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise RuntimeError(
            "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set in production mode."
        )

app = FastAPI(
    title="VoyagerAI — Travel Planning AI Agent",
    version="2.2.0",
    description=(
        "Generates, validates, and enriches multi-day travel itineraries using DeepAgent.\n\n"
        "## Authentication\n"
        "Most endpoints require an `X-API-Key` header (production mode) and a valid session cookie.\n"
        "Admin endpoints additionally require the user to be in the `ADMIN_EMAILS` allowlist.\n\n"
        "## Rate Limiting\n"
        "All endpoints are rate-limited via slowapi. Default limit: 30 requests/hour.\n"
        "Individual endpoints may have tighter limits (shown in each endpoint's documentation).\n\n"
        "## SSE Streaming\n"
        "Chat endpoints (`/chat/stream`, `/chat/regenerate`, `/chat/edit`) return Server-Sent Events.\n"
        "See the Markdown docs in `backend/docs/chat.md` for the full event type reference."
    ),
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

_use_secure_cookies = settings.AUTH_MODE == "production" or any(orig.startswith("https://") for orig in ALLOWED_ORIGINS)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET_KEY,
    same_site="none" if _use_secure_cookies else "lax",
    https_only=_use_secure_cookies,
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

# --- Per-user rate limiting (Phase 7.2) ---
from rate_limiter import RateLimitMiddleware  # noqa: E402

app.add_middleware(RateLimitMiddleware)

# --- Request context middleware for structured logging (Phase 7.4) ---

@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    """Generate request ID and set logging context for every request."""
    request_id = request.headers.get("X-Request-ID") or generate_request_id()
    set_request_context(request_id=request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

# --- CSRF Protection (double-submit cookie pattern) ---
CSRF_COOKIE_NAME = "voyager_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"
_CSRF_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_CSRF_EXEMPT_PATHS = {"/chat/stream", "/chat/regenerate", "/chat/edit", "/auth/callback"}


@app.middleware("http")
async def csrf_middleware(request: Request, call_next):
    """Verify CSRF token on mutation requests (double-submit cookie pattern).

    Reads the CSRF token from the cookie and compares it to the X-CSRF-Token header.
    SSE endpoints are exempt (they can't set custom headers easily in all browsers).
    """
    if request.method in _CSRF_METHODS and request.url.path not in _CSRF_EXEMPT_PATHS and not request.url.path.endswith("/edit-itinerary"):
        cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
        header_token = request.headers.get(CSRF_HEADER_NAME)
        if not cookie_token or not header_token or not hmac.compare_digest(cookie_token, header_token):
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF token missing or invalid"},
            )
    response = await call_next(request)
    if not request.cookies.get(CSRF_COOKIE_NAME):
        response.set_cookie(
            CSRF_COOKIE_NAME,
            secrets.token_urlsafe(32),
            httponly=False,
            samesite="none" if _use_secure_cookies else "lax",
            secure=_use_secure_cookies,
            max_age=7 * 24 * 3600,
        )
    return response

# CORSMiddleware must be added LAST so it becomes the outermost middleware layer.
# Starlette's add_middleware() prepends to the stack (last added = outermost),
# guaranteeing CORS headers are applied to every response, including errors,
# 401s, 429s, and 503s raised by any of the middlewares registered above.
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Docs endpoints: open in dev, admin-protected in production ---
_docs_deps: list = [] if settings.AUTH_MODE == "development" else [
    Depends(verify_api_key), Depends(verify_admin),
]


@app.get("/docs", include_in_schema=False, dependencies=_docs_deps)
async def custom_swagger_ui_html() -> HTMLResponse:
    """Swagger UI for interactive API exploration."""
    return get_swagger_ui_html(openapi_url="/openapi.json", title="VoyagerAI API Docs")


@app.get("/redoc", include_in_schema=False, dependencies=_docs_deps)
async def custom_redoc_html() -> HTMLResponse:
    """ReDoc UI for readable API documentation."""
    return get_redoc_html(openapi_url="/openapi.json", title="VoyagerAI API Docs")


@app.get("/openapi.json", include_in_schema=False, dependencies=_docs_deps)
async def get_openapi_schema() -> dict:
    """OpenAPI 3.1 schema for the VoyagerAI backend API."""
    return app.openapi()


def _scoped_chat_thread_id(
    client_thread_id: str | None,
    user_id: str,
    client_message_id: str | None = None,
) -> str:
    """Namespace chat thread ids per user so checkpoints can't be resumed cross-user.

    Client-supplied ids are treated as opaque and stored under a user-scoped key.
    Already-scoped ids (resume) pass through unchanged. When no thread id is
    supplied, a stable id derived from client_message_id keeps stream retries
    on the same checkpoint instead of minting an orphan thread per retry.
    """
    user_tag = hashlib.sha256(user_id.encode()).hexdigest()[:12]
    prefix = f"chat:{user_tag}:"
    if client_thread_id and client_thread_id.startswith(prefix):
        return client_thread_id
    if client_thread_id:
        return prefix + client_thread_id
    if client_message_id:
        safe = "".join(c for c in client_message_id if c.isalnum() or c in "-_")[:64]
        if safe:
            return prefix + safe
    return prefix + uuid.uuid4().hex[:12]


def _sse(event: str, data: object) -> dict:
    return {"event": event, "data": json.dumps({"event": event, "data": data})}


async def _read_thread_values(thread_id: str, checkpoint_id: str | None = None) -> dict | None:
    """Read a thread's checkpoint channel_values without building the agent."""
    from agents.deep_agent import create_checkpointer
    saver = await create_checkpointer()
    config: dict = {"configurable": {"thread_id": thread_id}}
    if checkpoint_id:
        config["configurable"]["checkpoint_id"] = checkpoint_id
    tup = await saver.aget_tuple(config)
    if tup is None:
        return None
    return tup.checkpoint.get("channel_values", {})


def _history_message_text(content) -> str:
    """Render message content for history — joins text blocks and marks
    attachments instead of dumping the Python repr of the block list."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content)
    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        btype = block.get("type", "")
        if btype in ("text", "text-delta"):
            text = block.get("text", "")
            # PDF bodies are huge extracted text — keep only the marker line
            if text.startswith("--- Attached PDF:"):
                parts.append(text.split("\n", 1)[0] + " ---")
            else:
                parts.append(text)
        elif btype == "image_url":
            parts.append("[Image attached]")
    return "\n".join(p for p in parts if p.strip())


class _ObsQueue:
    """Ordered, referenced observability writes for one SSE stream.

    Producers enqueue store callables; a single consumer task awaits them
    FIFO — start_session precedes events, finalize_session lands last.
    Fire-and-forget create_task calls could be GC'd mid-write and ran
    unordered. Never raises into the stream.
    """

    _SENTINEL = object()

    def __init__(self) -> None:
        self._q: asyncio.Queue = asyncio.Queue()
        self._task: asyncio.Task | None = None

    def send(self, fn, *args, **kwargs) -> None:
        try:
            if self._task is None:
                self._task = asyncio.create_task(self._drain())
            self._q.put_nowait((fn, args, kwargs))
        except Exception:  # noqa: BLE001, S110
            pass

    async def _drain(self) -> None:
        while True:
            item = await self._q.get()
            if item is self._SENTINEL:
                return
            fn, args, kwargs = item
            try:
                await fn(*args, **kwargs)
            except Exception:  # noqa: BLE001
                logger.debug("observability write failed", exc_info=True)

    async def close(self, timeout: float = 5.0) -> None:
        if self._task is None:
            return
        self._q.put_nowait(self._SENTINEL)
        try:
            await asyncio.wait_for(asyncio.shield(self._task), timeout=timeout)
        except Exception:  # noqa: BLE001
            self._task.cancel()


def _send_obs_event(obs: "_ObsQueue", thread_id: str, payload: dict) -> None:
    """Enqueue an observability record_event for one SSE payload."""
    try:
        evt_data = json.loads(payload["data"]) if payload.get("data") else {}
        if not isinstance(evt_data, dict):
            evt_data = {}
        obs.send(
            observability_store.record_event,
            thread_id=thread_id,
            event_type=payload["event"],
            name=evt_data.get("name", ""),
            run_id=evt_data.get("run_id", ""),
            parent_run_id=evt_data.get("parent_run_id", ""),
            input_data=evt_data.get("input"),
            output=evt_data.get("output", ""),
            error=evt_data.get("error", ""),
            tokens_in=evt_data.get("input_tokens", 0),
            tokens_out=evt_data.get("output_tokens", 0),
            model=evt_data.get("model", ""),
        )
    except Exception:  # noqa: BLE001, S110
        pass


def _validate_body_fields(body: dict, limits: dict[str, int]) -> None:
    """Validate that string fields in body dict don't exceed max length."""
    for field, max_len in limits.items():
        val = body.get(field, "")
        if isinstance(val, str) and len(val) > max_len:
            raise HTTPException(
                status_code=422,
                detail=f"Field '{field}' exceeds maximum length of {max_len} characters.",
            )


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
    if event_type == "image" and event_data is not None:
        return [_sse("image", event_data)]
    if event_type == "chart" and event_data is not None:
        return [_sse("chart", event_data)]
    if event_type == "done":
        return [_sse("done", event_data)]
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
        elif is_pipeline_tool(name):
            # Pipeline tools run inner model/tool calls that bubble up under
            # this run_id — register it so those chunks stay out of "token".
            subagent_type = name
        else:
            subagent_type = None
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
                "error": "tool_unavailable",
                "run_id": run_id,
            }))
        else:
            te_payload = {
                "name": name,
                "error": "tool_unavailable",
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


@app.get(
    "/health",
    summary="Health check",
    tags=["ops"],
    response_model=HealthResponse,
    responses={
        200: {
            "description": "Service health status",
            "content": {"application/json": {"example": {
                "status": "ok", "redis": "connected", "agent": "deepagent",
            }}},
        },
        503: {"description": "Redis unavailable — service degraded"},
    },
)
async def health() -> HealthResponse:
    """Check if the backend and Redis are healthy.

    Returns the overall service status and Redis connection state.
    No authentication required — used by load balancers and monitoring.

    **Response fields:**
    - `status`: "ok" if Redis is connected, "degraded" otherwise
    - `redis`: "connected" or "unavailable"
    - `agent`: Always "deepagent" (identifies the agent framework)
    """
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
    response_model=CostAnalyticsResponse,
    responses={
        200: {
            "description": "Aggregate cost analytics for the requested period",
            "content": {"application/json": {"example": {
                "total_cost": 12.34,
                "total_conversations": 42,
                "avg_cost_per_conversation": 0.29,
                "total_input_tokens": 150000,
                "total_output_tokens": 80000,
                "per_day": [{"date": "2026-09-08", "cost": 2.5}],
                "per_subagent": [{"name": "research", "cost": 5.0, "input_tokens": 20000, "output_tokens": 10000}],
                "top_users": [{"user_id": "user@example.com", "cost": 3.5}],
                "poor_efficiency_sessions": [],
            }}},
        },
        401: {"description": "Missing or invalid API key"},
        403: {"description": "User is not in ADMIN_EMAILS allowlist"},
    },
)
@limiter.limit("10/minute")
async def get_cost_analytics(
    request: Request,
    period: str = "week",
    admin: dict = Depends(verify_admin),
) -> CostAnalyticsResponse:
    """Get aggregate cost analytics for a time period.

    Returns total cost, conversation count, token usage, per-day and per-subagent
    breakdowns, top users by spend, and sessions with poor efficiency ratios.

    **Query parameters:**
    - `period`: Time window — "day", "week" (default), or "month"

    **Requires:** Admin privileges (user must be in `ADMIN_EMAILS`).
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
    response_model=ThreadCostBreakdownResponse,
    responses={
        200: {
            "description": "Per-session and per-subagent cost breakdown",
            "content": {"application/json": {"example": {
                "session": {"thread_id": "chat:abc123:def456", "total_cost_usd": 0.15, "total_input_tokens": 5000, "total_output_tokens": 2000},
                "subagents": {"research": {"cost": 0.08, "input_tokens": 3000, "output_tokens": 1000}},
            }}},
        },
        401: {"description": "Missing or invalid API key"},
        403: {"description": "User is not in ADMIN_EMAILS allowlist"},
    },
)
@limiter.limit("30/minute")
async def get_thread_cost_breakdown(
    thread_id: str,
    request: Request,
    admin: dict = Depends(verify_admin),
) -> ThreadCostBreakdownResponse:
    """Get per-subagent cost breakdown for a specific conversation.

    **Path parameters:**
    - `thread_id`: The thread ID to inspect

    **Requires:** Admin privileges.
    """
    session_cost = await cost_store.get_session_cost(thread_id)
    subagent_breakdown = await cost_store.get_subagent_breakdown(thread_id)
    return JSONResponse(content={
        "session": session_cost,
        "subagents": subagent_breakdown,
    })


@app.get(
    "/admin/costs/user/{user_id}",
    summary="Get per-user daily cost summary (Phase 7.2)",
    tags=["admin"],
    dependencies=[Depends(verify_api_key)],
    response_model=None,
    responses={
        200: {
            "description": "Per-user cost summary",
            "content": {"application/json": {"example": {
                "user_id": "alice@example.com",
                "daily_spent": 2.34,
                "daily_cap": 5.0,
                "remaining": 2.66,
            }}},
        },
        401: {"description": "Missing or invalid API key"},
        403: {"description": "User is not in ADMIN_EMAILS allowlist"},
    },
)
@limiter.limit("10/minute")
async def get_user_cost_summary(
    user_id: str,
    request: Request,
    admin: dict = Depends(verify_admin),
) -> JSONResponse:
    """Get a per-user daily cost summary including remaining budget.

    **Path parameters:**
    - `user_id`: The user ID to inspect

    **Requires:** Admin privileges.
    """
    spent = await cost_store.get_user_daily_spend(user_id)
    cap = settings.DAILY_COST_CAP_USD
    return JSONResponse(content={
        "user_id": user_id,
        "daily_spent": round(spent, 6),
        "daily_cap": cap,
        "remaining": round(cap - spent, 6),
    })


@app.get(
    "/admin/costs/platform",
    summary="Get platform-wide hourly cost summary (Phase 7.2)",
    tags=["admin"],
    dependencies=[Depends(verify_api_key)],
    response_model=None,
    responses={
        200: {
            "description": "Platform cost summary",
            "content": {"application/json": {"example": {
                "hourly_spent": 12.34,
                "hourly_cap": 50.0,
                "circuit_breaker_enabled": True,
                "circuit_breaker_tripped": False,
            }}},
        },
        401: {"description": "Missing or invalid API key"},
        403: {"description": "User is not in ADMIN_EMAILS allowlist"},
    },
)
@limiter.limit("10/minute")
async def get_platform_cost_summary(
    request: Request,
    admin: dict = Depends(verify_admin),
) -> JSONResponse:
    """Get platform-wide hourly cost summary and circuit breaker status.

    **Requires:** Admin privileges.
    """
    spent = await cost_store.get_hourly_platform_spend()
    cap = settings.HOURLY_PLATFORM_CAP_USD
    tripped = settings.CIRCUIT_BREAKER_ENABLED and spent >= cap
    return JSONResponse(content={
        "hourly_spent": round(spent, 6),
        "hourly_cap": cap,
        "circuit_breaker_enabled": settings.CIRCUIT_BREAKER_ENABLED,
        "circuit_breaker_tripped": tripped,
    })


@app.get(
    "/admin/costs/live",
    summary="Get live cost breakdown for last N hours (Phase 7.4)",
    tags=["admin"],
    dependencies=[Depends(verify_api_key)],
    response_model=None,
    responses={
        200: {
            "description": "Live cost breakdown",
            "content": {"application/json": {"example": {
                "hours": 24,
                "total_spend": 3.45,
                "per_hour": [
                    {"hour": "2024-01-15T14:00", "cost": 0.12, "requests": 3, "tokens_in": 1200, "tokens_out": 800}
                ],
                "alert": {"level": "ok", "daily_spend": 3.45, "daily_cap": 50.0, "percentage": 6.9, "message": "Spend within normal range"}
            }}},
        },
        401: {"description": "Missing or invalid API key"},
        403: {"description": "User is not in ADMIN_EMAILS allowlist"},
    },
)
@limiter.limit("10/minute")
async def get_live_costs(
    request: Request,
    hours: int = 24,
    admin: dict = Depends(verify_admin),
) -> JSONResponse:
    """Get live per-hour cost breakdown for the last N hours.

    **Query parameters:**
    - `hours`: Number of hours to look back (default: 24, max: 168)

    **Requires:** Admin privileges.
    """
    hours = min(max(hours, 1), 168)
    live_data = await cost_store.get_live_costs(hours=hours)
    alert = await cost_store.check_platform_alerts()
    return JSONResponse(content={
        "hours": hours,
        "total_spend": round(sum(h["cost"] for h in live_data), 6),
        "per_hour": live_data,
        "alert": alert,
    })


@app.get(
    "/admin/costs/export",
    summary="Export all cost records as CSV",
    tags=["admin"],
    dependencies=[Depends(verify_api_key)],
    response_model=None,
    responses={
        200: {
            "description": "CSV file with cost analytics",
            "content": {"text/csv": {"example": "metric,value\ntotal_cost,12.34\ntotal_conversations,42\n"}},
        },
        401: {"description": "Missing or invalid API key"},
        403: {"description": "User is not in ADMIN_EMAILS allowlist"},
    },
)
@limiter.limit("5/minute")
async def export_costs_csv(
    request: Request,
    admin: dict = Depends(verify_admin),
) -> PlainTextResponse:
    """Export all cost records as CSV for spreadsheet analysis.

    Returns a CSV file with sections for aggregate metrics, per-subagent costs,
    top users, and poor-efficiency sessions.

    **Response:** `text/csv` with `Content-Disposition: attachment; filename=costs.csv`

    **Requires:** Admin privileges.
    """
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
    response_model=FeedbackSubmitResponse,
    responses={
        200: {
            "description": "Feedback submitted successfully",
            "content": {"application/json": {"example": {"status": "ok", "rating": "up"}}},
        },
        401: {"description": "Missing or invalid API key"},
    },
)
@limiter.limit("30/minute")
async def submit_feedback(
    request: Request,
    user: dict = Depends(get_current_user),
) -> FeedbackSubmitResponse:
    """Submit or update thumbs up/down feedback for a specific message.

    One rating per user per message — submitting again overwrites the previous rating.

    **Request body:** `FeedbackRequest` with `thread_id`, `message_id`, `rating` ('up' or 'down'),
    and optional `comment` (max 1000 chars).
    """
    # Body is parsed manually (independent of Content-Type) so the frontend can
    # avoid a CORS preflight OPTIONS request (see chat_stream for details).
    try:
        body = FeedbackRequest(**json.loads(await request.body()))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail="Invalid request body.")

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
    response_model=FeedbackStatsResponse,
    responses={
        200: {
            "description": "Aggregate feedback statistics",
            "content": {"application/json": {"example": {
                "total_up": 120, "total_down": 15, "total_ratings": 135,
                "satisfaction_ratio": 0.889, "recent_comments": [],
            }}},
        },
        401: {"description": "Missing or invalid API key"},
        403: {"description": "User is not in ADMIN_EMAILS allowlist"},
    },
)
@limiter.limit("10/minute")
async def get_feedback_stats(
    request: Request,
    admin: dict = Depends(verify_admin),
) -> FeedbackStatsResponse:
    """Get aggregate feedback statistics for admin observability.

    Returns total up/down counts, satisfaction ratio, and last 20 thumbs-down comments.

    **Requires:** Admin privileges.
    """
    stats = await feedback_store.get_aggregate_stats()
    return JSONResponse(content=stats)


@app.delete(
    "/admin/cache/research",
    summary="Invalidate all cached research results",
    tags=["admin"],
    dependencies=[Depends(verify_api_key)],
    response_model=CacheInvalidateResponse,
    responses={
        200: {
            "description": "Cache invalidated",
            "content": {"application/json": {"example": {"status": "ok", "cleared": 42}}},
        },
        401: {"description": "Missing or invalid API key"},
        403: {"description": "User is not in ADMIN_EMAILS allowlist"},
    },
)
@limiter.limit("5/minute")
async def invalidate_research_cache(
    request: Request,
    admin: dict = Depends(verify_admin),
) -> CacheInvalidateResponse:
    """Clear all cached Tavily search results.

    Forces fresh research on subsequent chat requests.

    **Requires:** Admin privileges.
    """
    count = await research_cache.invalidate_all()
    logger.info("Research cache invalidated by admin: %d entries cleared", count)
    return {"status": "ok", "cleared": count}


# --- Admin security endpoints (Phase 6.30) ---

@app.get(
    "/admin/security/flags",
    summary="Get aggregate security flag stats",
    tags=["admin"],
    dependencies=[Depends(verify_api_key)],
    response_model=SecurityFlagsResponse,
    responses={
        200: {
            "description": "Aggregate security flag statistics",
            "content": {"application/json": {"example": {
                "total_flags": 5,
                "by_category": {"instruction_override": 3, "extraction_attempt": 2},
                "by_source": {"message": 4, "pdf": 1},
                "by_confidence": {"high": 3, "low": 2},
                "unique_users": 2,
                "active_cooldowns": 1,
                "recent_flags": [],
            }}},
        },
        401: {"description": "Missing or invalid API key"},
        403: {"description": "User is not in ADMIN_EMAILS allowlist"},
    },
)
@limiter.limit("10/minute")
async def get_security_flags(
    request: Request,
    period: str = "week",
    admin: dict = Depends(verify_admin),
) -> SecurityFlagsResponse:
    """Get aggregate prompt injection flag statistics for admin observability.

    **Query parameters:**
    - `period`: Time window — "day", "week" (default), or "month"

    **Requires:** Admin privileges.
    """
    if period not in ("day", "week", "month"):
        period = "week"
    stats = await security_store.get_aggregate_stats(period=period)
    return JSONResponse(content=stats)


@app.get(
    "/admin/security/cooldowns",
    summary="Get currently active cooldowns",
    tags=["admin"],
    dependencies=[Depends(verify_api_key)],
    response_model=CooldownListResponse,
    responses={
        200: {
            "description": "List of active cooldowns",
            "content": {"application/json": {"example": {
                "cooldowns": [{"user_hash": "abc123def456", "until": 1735689600, "remaining_seconds": 3600}],
                "count": 1,
            }}},
        },
        401: {"description": "Missing or invalid API key"},
        403: {"description": "User is not in ADMIN_EMAILS allowlist"},
    },
)
@limiter.limit("10/minute")
async def get_active_cooldowns(
    request: Request,
    admin: dict = Depends(verify_admin),
) -> CooldownListResponse:
    """Get all currently active injection cooldowns for admin review.

    **Requires:** Admin privileges.
    """
    cooldowns = await security_store.get_active_cooldowns()
    return JSONResponse(content={"cooldowns": cooldowns, "count": len(cooldowns)})


@app.delete(
    "/admin/security/cooldowns/{user_hash}",
    summary="Manually remove a user's cooldown (admin unblock)",
    tags=["admin"],
    dependencies=[Depends(verify_api_key)],
    response_model=CooldownRemoveResponse,
    responses={
        200: {
            "description": "Cooldown removed or not found",
            "content": {"application/json": {"example": {"status": "ok", "user_hash": "abc123def456"}}},
        },
        401: {"description": "Missing or invalid API key"},
        403: {"description": "User is not in ADMIN_EMAILS allowlist"},
    },
)
@limiter.limit("10/minute")
async def remove_cooldown(
    request: Request,
    user_hash: str,
    admin: dict = Depends(verify_admin),
) -> CooldownRemoveResponse:
    """Manually remove a cooldown for a user (in case of false-positive lockout).

    **Path parameters:**
    - `user_hash`: The hashed user ID (12-char SHA256 prefix) to unblock

    **Requires:** Admin privileges.
    """
    removed = await security_store.remove_cooldown(user_hash)
    logger.info("Cooldown removed for user_hash=%s by admin (removed=%s)", user_hash, removed)
    return {"status": "ok" if removed else "not_found", "user_hash": user_hash}


# --- Admin observability endpoints (Phase 5.7) ---

@app.get(
    "/admin/observability/sessions",
    summary="Get paginated list of observability sessions",
    tags=["admin"],
    dependencies=[Depends(verify_api_key)],
    response_model=None,
    responses={
        200: {
            "description": "Paginated session list",
            "content": {"application/json": {"example": {
                "sessions": [],
                "total": 0,
                "limit": 50,
                "offset": 0,
            }}},
        },
        401: {"description": "Missing or invalid API key"},
        403: {"description": "User is not in ADMIN_EMAILS allowlist"},
    },
)
@limiter.limit("10/minute")
async def get_observability_sessions(
    request: Request,
    from_ts: float = 0,
    to_ts: float = 0,
    status: str = "",
    limit: int = 50,
    offset: int = 0,
    admin: dict = Depends(verify_admin),
) -> JSONResponse:
    """Get paginated list of observability sessions with filters.

    **Query parameters:**
    - `from_ts`: Unix timestamp start (default: 0 = all)
    - `to_ts`: Unix timestamp end (default: 0 = now)
    - `status`: Filter by status (running, completed, error, cancelled)
    - `limit`: Page size (default: 50, max: 200)
    - `offset`: Page offset (default: 0)

    **Requires:** Admin privileges.
    """
    limit = min(max(limit, 1), 200)
    result = await observability_store.get_sessions(
        from_ts=from_ts, to_ts=to_ts, status=status, limit=limit, offset=offset,
    )
    return JSONResponse(content=result)


@app.get(
    "/admin/observability/sessions/{thread_id}",
    summary="Get session detail with event timeline",
    tags=["admin"],
    dependencies=[Depends(verify_api_key)],
    response_model=None,
    responses={
        200: {
            "description": "Session detail with events",
            "content": {"application/json": {"example": {
                "session": {},
                "events": [],
            }}},
        },
        401: {"description": "Missing or invalid API key"},
        403: {"description": "User is not in ADMIN_EMAILS allowlist"},
        404: {"description": "Session not found"},
    },
)
@limiter.limit("10/minute")
async def get_observability_session_detail(
    request: Request,
    thread_id: str,
    admin: dict = Depends(verify_admin),
) -> JSONResponse:
    """Get full session detail including event timeline for waterfall rendering.

    **Path parameters:**
    - `thread_id`: The thread ID to inspect

    **Requires:** Admin privileges.
    """
    sessions = await observability_store.get_sessions(limit=10000)
    session = None
    for s in sessions["sessions"]:
        if s["thread_id"] == thread_id:
            session = s
            break
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    events = await observability_store.get_session_events(thread_id)
    return JSONResponse(content={"session": session, "events": events})


@app.get(
    "/admin/observability/sessions/{thread_id}/events",
    summary="Get raw event list for a session",
    tags=["admin"],
    dependencies=[Depends(verify_api_key)],
    response_model=None,
    responses={
        200: {
            "description": "Ordered event list",
            "content": {"application/json": {"example": []}},
        },
        401: {"description": "Missing or invalid API key"},
        403: {"description": "User is not in ADMIN_EMAILS allowlist"},
    },
)
@limiter.limit("10/minute")
async def get_observability_session_events(
    request: Request,
    thread_id: str,
    admin: dict = Depends(verify_admin),
) -> JSONResponse:
    """Get raw event list for a session (for waterfall rendering).

    **Path parameters:**
    - `thread_id`: The thread ID to inspect

    **Requires:** Admin privileges.
    """
    events = await observability_store.get_session_events(thread_id)
    return JSONResponse(content=events)


@app.get(
    "/admin/observability/errors",
    summary="Get error events with filters",
    tags=["admin"],
    dependencies=[Depends(verify_api_key)],
    response_model=None,
    responses={
        200: {
            "description": "Error list",
            "content": {"application/json": {"example": []}},
        },
        401: {"description": "Missing or invalid API key"},
        403: {"description": "User is not in ADMIN_EMAILS allowlist"},
    },
)
@limiter.limit("10/minute")
async def get_observability_errors(
    request: Request,
    from_ts: float = 0,
    to_ts: float = 0,
    subagent: str = "",
    tool: str = "",
    limit: int = 50,
    admin: dict = Depends(verify_admin),
) -> JSONResponse:
    """Get error events with filters.

    **Query parameters:**
    - `from_ts`: Unix timestamp start (default: 0 = all)
    - `to_ts`: Unix timestamp end (default: 0 = now)
    - `subagent`: Filter by subagent name
    - `tool`: Filter by tool name
    - `limit`: Max results (default: 50, max: 500)

    **Requires:** Admin privileges.
    """
    limit = min(max(limit, 1), 500)
    errors = await observability_store.get_errors(
        from_ts=from_ts, to_ts=to_ts, subagent=subagent, tool=tool, limit=limit,
    )
    return JSONResponse(content=errors)


@app.get(
    "/admin/observability/errors/summary",
    summary="Get error summary with counts and trends",
    tags=["admin"],
    dependencies=[Depends(verify_api_key)],
    response_model=None,
    responses={
        200: {
            "description": "Error summary",
            "content": {"application/json": {"example": {
                "total_errors": 0,
                "by_subagent": [],
                "by_tool": [],
                "per_day": [],
            }}},
        },
        401: {"description": "Missing or invalid API key"},
        403: {"description": "User is not in ADMIN_EMAILS allowlist"},
    },
)
@limiter.limit("10/minute")
async def get_observability_error_summary(
    request: Request,
    from_ts: float = 0,
    to_ts: float = 0,
    admin: dict = Depends(verify_admin),
) -> JSONResponse:
    """Get error counts grouped by subagent+tool, plus error rate trend.

    **Query parameters:**
    - `from_ts`: Unix timestamp start (default: 0 = all)
    - `to_ts`: Unix timestamp end (default: 0 = now)

    **Requires:** Admin privileges.
    """
    summary = await observability_store.get_error_summary(from_ts=from_ts, to_ts=to_ts)
    return JSONResponse(content=summary)


@app.get(
    "/admin/observability/usage",
    summary="Get aggregated token/cost usage analytics",
    tags=["admin"],
    dependencies=[Depends(verify_api_key)],
    response_model=None,
    responses={
        200: {
            "description": "Usage analytics",
            "content": {"application/json": {"example": {
                "per_day": [],
                "per_subagent": [],
                "per_user": [],
                "totals": {},
            }}},
        },
        401: {"description": "Missing or invalid API key"},
        403: {"description": "User is not in ADMIN_EMAILS allowlist"},
    },
)
@limiter.limit("10/minute")
async def get_observability_usage(
    request: Request,
    from_ts: float = 0,
    to_ts: float = 0,
    admin: dict = Depends(verify_admin),
) -> JSONResponse:
    """Get aggregated token/cost usage per day, per subagent, per user.

    **Query parameters:**
    - `from_ts`: Unix timestamp start (default: 0 = all)
    - `to_ts`: Unix timestamp end (default: 0 = now)

    **Requires:** Admin privileges.
    """
    usage = await observability_store.get_usage(from_ts=from_ts, to_ts=to_ts)
    return JSONResponse(content=usage)


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
    response_model=None,
    responses={
        200: {
            "description": "User preferences as JSON",
            "content": {"application/json": {"example": {"user_instructions": "I prefer budget travel.", "learned_preferences": {"travel_style": "relaxed"}}}},
        },
        401: {"description": "Missing or invalid API key"},
        503: {"description": "Preferences store unavailable"},
    },
)
@limiter.limit("30/minute")
async def get_preferences(request: Request, user: dict = Depends(get_current_user)) -> JSONResponse:
    """Get the current user's preferences as JSON.

    Returns `{"user_instructions": str, "learned_preferences": dict}`.
    Empty fields if no preferences have been saved.

    **Response:** `application/json`
    """
    user_id = user["user_id"]
    locale = extract_locale(request)
    logger.info("GET /preferences user=%s locale=%s", user_id, locale)
    try:
        store = get_redis_file_store()
        item = store.get((user_id,), "/preferences.md")
    except Exception:  # noqa: BLE001 (intentional fallback handler)
        logger.warning("Preferences store unavailable — returning empty preferences")
        return JSONResponse({"user_instructions": "", "learned_preferences": {}}, status_code=503)
    if item is None:
        return JSONResponse({"user_instructions": "", "learned_preferences": {}}, status_code=200)
    content = item.value.get("content", "")
    user_text, learned_text = _parse_preferences(content)
    learned_dict = _parse_learned_preferences_to_dict(learned_text)
    return JSONResponse({"user_instructions": user_text, "learned_preferences": learned_dict}, status_code=200)


@app.put(
    "/preferences",
    summary="Save user preferences",
    tags=["preferences"],
    dependencies=[Depends(verify_api_key)],
    response_model=PreferencesSaveResponse,
    responses={
        200: {
            "description": "Preferences saved successfully",
            "content": {"application/json": {"example": {"status": "ok", "user_id": "user@example.com"}}},
        },
        401: {"description": "Missing or invalid API key"},
        503: {"description": "Preferences store unavailable"},
    },
)
@limiter.limit("30/minute")
async def put_preferences(request: Request, user: dict = Depends(get_current_user)) -> PreferencesSaveResponse:
    """Save user preferences as JSON.

    **Request body:** JSON object with `user_instructions` (string).
    The `learned_preferences` section is preserved from existing storage.
    User instructions are sanitized to strip XML-like tags for safety.

    **Response:** `application/json`
    """
    user_id = user["user_id"]
    locale = extract_locale(request)
    logger.info("PUT /preferences user=%s locale=%s", user_id, locale)
    body = await request.body()
    try:
        payload = json.loads(body) if body else {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {"status": "error", "user_id": user_id, "error": "Invalid JSON body"}
    user_text = _sanitize_instructions(payload.get("user_instructions", ""))

    # Fetch existing content to preserve learned_preferences
    try:
        store = get_redis_file_store()
        existing_item = store.get((user_id,), "/preferences.md")
    except Exception:  # noqa: BLE001 (intentional fallback handler)
        logger.warning("Preferences store unavailable — preferences not saved")
        return {"status": "error", "user_id": user_id, "error": "Preferences store unavailable"}

    existing_learned_text = ""
    if existing_item is not None:
        existing_content = existing_item.value.get("content", "")
        _, existing_learned_text = _parse_preferences(existing_content)

    # Reconstruct the stored format with XML tags
    content = f"<user_instructions>\n{user_text}\n</user_instructions>\n\n<learned_preferences>\n{existing_learned_text}\n</learned_preferences>"

    try:
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
    response_model=UploadResponse,
    responses={
        200: {
            "description": "File uploaded successfully",
            "content": {"application/json": {"example": {
                "file_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "data_url": "data:image/jpeg;base64,/9j/4AAQ...",
                "filename": "photo.jpg",
                "content_type": "image/jpeg",
                "size": 102400,
            }}},
        },
        400: {"description": "Empty file"},
        401: {"description": "Missing or invalid API key"},
        413: {"description": "File too large (max 10MB)"},
        415: {"description": "Unsupported file type or extension"},
    },
)
@limiter.limit("10/minute")
async def upload_file(
    request: Request,
    file: UploadFile = FastAPIFile(...),
    user: dict = Depends(get_current_user),
) -> UploadResponse:
    """Upload a file (image or PDF) for use as a chat attachment.

    **Request body:** `multipart/form-data` with a `file` field.
    Supported types: JPG, PNG, WebP, PDF. Max size: 10MB.

    Files are stored in Redis with a 1-hour TTL and auto-expire.
    """
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
    response_model=None,
    responses={
        200: {
            "description": "Server-Sent Events stream of chat tokens and events",
            "content": {"text/event-stream": {"example": "event: thread_id\ndata: {\"event\": \"thread_id\", \"data\": {\"thread_id\": \"chat:abc123:def456\"}}\n\nevent: token\ndata: {\"event\": \"token\", \"data\": \"Hello\"}\n"}},
        },
        400: {"description": "Prompt injection detected — request blocked"},
        401: {"description": "Missing or invalid API key"},
        429: {"description": "Rate limit exceeded or user in cooldown"},
    },
)
@limiter.limit("20/minute")
async def chat_stream(
    request: Request,
    user: dict = Depends(get_current_user),
) -> EventSourceResponse:
    """Stream a chat conversation with the AI travel agent.

    Returns a Server-Sent Events (SSE) stream with token-by-token LLM output,
    subagent status updates, itinerary/comparison data, images, charts, and usage stats.

    **Request body:** `ChatRequest` with `message` (required), optional `thread_id`,
    `locale`, `timezone`, `attachments`, and `client_message_id`.

    **SSE event types:** `thread_id`, `status`, `token`, `itinerary`, `comparison`,
    `image`, `chart`, `usage`, `tool_error`, `subagent_progress`, `cancelled`, `error`, `done`.
    """
    # Body is parsed manually (independent of the Content-Type header) so the
    # frontend can send it as text/plain and avoid a CORS preflight OPTIONS
    # request, which some hosting proxies (e.g. Hugging Face Spaces) mishandle.
    try:
        raw_body = await request.body()
        chat_req = ChatRequest(**json.loads(raw_body))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail="Invalid request body.")

    _msg_safe = sanitize_prompt_input(chat_req.message, "message")

    user_id = user["user_id"]
    thread_id = _scoped_chat_thread_id(chat_req.thread_id, user_id, chat_req.client_message_id)

    # Determine locale: explicit request field takes priority, then Accept-Language header
    locale = extract_locale(request, chat_req.locale)

    # --- Phase 7.2: Daily cost cap + circuit breaker ---
    within_budget, _spent, _cap = await cost_store.check_daily_budget(user_id)
    if not within_budget:
        raise HTTPException(
            status_code=429,
            detail=f"Daily cost limit reached (${_spent:.2f}/${_cap:.2f}). Try again tomorrow.",
        )
    tripped, _p_spent, _p_cap = await cost_store.check_circuit_breaker()
    if tripped:
        raise HTTPException(
            status_code=503,
            detail="Platform temporarily unavailable due to high demand. Please try again shortly.",
        )

    # --- Phase 6.30: Prompt injection defense ---
    # Step 1: Check cooldown
    if await security_store.is_in_cooldown(user_id):
        raise HTTPException(
            status_code=429,
            detail=get_error_message("cooldown_active", locale),
        )

    # Step 2: Detailed sanitization with confidence levels
    sanitize_result = sanitize_prompt_input_detailed(chat_req.message, "message")
    _msg_safe = sanitize_result.text

    # Step 3: If high-confidence match, route to guard model
    if sanitize_result.confidence == "high" and settings.ENABLE_INJECTION_GUARD:
        guard_verdict = await classify_injection_risk(_msg_safe or "")
        if guard_verdict.is_malicious:
            # Record flag and strike
            await security_store.record_flag(
                user_id=user_id,
                category=",".join(sanitize_result.matched_categories),
                confidence="high",
                source="message",
                reasoning=guard_verdict.reasoning,
                thread_id=thread_id,
            )
            strikes = await security_store.record_strike(user_id)
            if strikes >= settings.INJECTION_STRIKE_THRESHOLD:
                await security_store.apply_cooldown(user_id)
                logger.warning(
                    "User %s hit strike threshold (%d) — cooldown applied",
                    user_id, strikes,
                )
            raise HTTPException(
                status_code=400,
                detail=get_error_message("injection_blocked", locale),
            )
        else:
            # Guard says benign — log as reviewed and continue
            await security_store.record_flag(
                user_id=user_id,
                category=",".join(sanitize_result.matched_categories),
                confidence="low",
                source="message",
                reasoning=f"Guard reviewed as benign: {guard_verdict.reasoning}",
                thread_id=thread_id,
            )
    elif sanitize_result.confidence == "low":
        # Control-token match only — log and continue with sanitized text
        await security_store.record_flag(
            user_id=user_id,
            category="control_token",
            confidence="low",
            source="message",
            thread_id=thread_id,
        )

    # A currency the user just typed (e.g. "₹50,000") is a stronger signal
    # than a stale app-wide currency preference — it wins.
    effective_currency = extract_stated_currency(_msg_safe) or chat_req.currency

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

        obs = _ObsQueue()
        obs.send(observability_store.start_session,
                 thread_id, user_id, locale=locale, timezone=chat_req.timezone or "")

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
                timezone=chat_req.timezone,
                currency=effective_currency,
                cancel_event=cancel_event,
                attachments=[a.model_dump() for a in chat_req.attachments] if chat_req.attachments else None,
                client_message_id=chat_req.client_message_id,
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
                    _send_obs_event(obs, thread_id, payload)
        except Exception as exc:  # noqa: BLE001 (intentional fallback handler)
            logger.error(
                "Chat stream failed for thread=%s: %s",
                thread_id,
                exc,
                exc_info=True,
            )
            stream_failed = True
            yield _sse("error", get_error_message(classify_exception(exc), locale))
            obs.send(observability_store.record_event,
                     thread_id=thread_id, event_type="error", error=str(exc)[:500])
        finally:
            unregister_cancel(thread_id)
            final_obs_status = "cancelled" if was_cancelled else ("error" if stream_failed else "completed")
            obs.send(observability_store.finalize_session, thread_id, final_obs_status)
            await obs.close()
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
    response_model=ChatCancelResponse,
    responses={
        200: {
            "description": "Cancellation status",
            "content": {"application/json": {"example": {"cancelled": True}}},
        },
        400: {"description": "Missing thread_id in request body"},
        401: {"description": "Missing or invalid API key"},
    },
)
@limiter.limit("30/minute")
async def chat_cancel(
    request: Request,
    user: dict = Depends(get_current_user),
) -> ChatCancelResponse:
    """Cancel an active chat stream for a given thread.

    **Request body:** `{"thread_id": "..."}` — the thread ID to cancel.

    Returns `cancelled: true` if a stream was found and cancelled, `false` otherwise.
    """
    # Body is parsed manually (independent of Content-Type) to allow the frontend
    # to avoid a CORS preflight OPTIONS request (see chat_stream for details).
    try:
        body = json.loads(await request.body())
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="Invalid JSON body")
    thread_id = body.get("thread_id", "")
    if not thread_id:
        raise HTTPException(status_code=400, detail="thread_id required")
    _validate_body_fields(body, {"thread_id": 200})
    user_id = user["user_id"]
    scoped_thread_id = _scoped_chat_thread_id(thread_id, user_id)
    cancelled = cancel_stream(scoped_thread_id)
    return {"cancelled": cancelled}


@app.post(
    "/chat/regenerate",
    summary="Regenerate the last assistant response",
    tags=["chat"],
    dependencies=[Depends(verify_api_key)],
    response_model=None,
    responses={
        200: {
            "description": "Server-Sent Events stream of regenerated chat tokens",
            "content": {"text/event-stream": {"example": "event: thread_id\ndata: {\"event\": \"thread_id\", \"data\": {\"thread_id\": \"chat:abc123:def456\"}}\n"}},
        },
        400: {"description": "Missing thread_id"},
        401: {"description": "Missing or invalid API key"},
    },
)
@limiter.limit("30/minute")
async def chat_regenerate(
    request: Request,
    user: dict = Depends(get_current_user),
):
    """Regenerate the last assistant response for a thread.

    Returns a Server-Sent Events (SSE) stream — same event types as `/chat/stream`.

    **Request body:** `{"thread_id": "...", "locale": "en", "timezone": "Asia/Kolkata"}`
    """
    # Body is parsed manually (independent of Content-Type) to allow the frontend
    # to avoid a CORS preflight OPTIONS request (see chat_stream for details).
    try:
        body = json.loads(await request.body())
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="Invalid JSON body")
    raw_thread_id = body.get("thread_id", "")
    if not raw_thread_id:
        raise HTTPException(status_code=400, detail="thread_id required")
    _validate_body_fields(body, {"thread_id": 200, "locale": 10, "timezone": 50, "currency": 10})

    user_id = user["user_id"]
    thread_id = _scoped_chat_thread_id(raw_thread_id, user_id)
    locale = extract_locale(request, body.get("locale"))
    timezone = body.get("timezone")
    currency = body.get("currency")

    # --- Phase 7.2: Daily cost cap + circuit breaker ---
    within_budget, _spent, _cap = await cost_store.check_daily_budget(user_id)
    if not within_budget:
        raise HTTPException(
            status_code=429,
            detail=f"Daily cost limit reached (${_spent:.2f}/${_cap:.2f}). Try again tomorrow.",
        )
    tripped, _p_spent, _p_cap = await cost_store.check_circuit_breaker()
    if tripped:
        raise HTTPException(
            status_code=503,
            detail="Platform temporarily unavailable due to high demand. Please try again shortly.",
        )

    logger.info("POST /chat/regenerate — thread_id=%s, user=%s", thread_id, user_id)

    async def event_generator():
        yield _sse("thread_id", {"thread_id": thread_id})
        yield _sse("status", {"tool": "agent", "status": "thinking"})

        cancel_event = register_cancel(thread_id)
        active_tasks: dict[str, str] = {}
        subagent_run_ids: set[str] = set()
        stream_failed = False
        stream_text = ""

        # Start observability session
        obs = _ObsQueue()
        obs.send(observability_store.start_session,
                 thread_id, user_id, locale=locale, timezone=timezone or "")

        try:
            await thread_store.update_status(user_id, thread_id, "busy")
        except Exception:  # noqa: BLE001, S110
            pass

        try:
            async for event in regenerate_chat_agent(
                thread_id=thread_id,
                user_id=user_id,
                locale=locale,
                timezone=timezone,
                currency=currency,
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
                    _send_obs_event(obs, thread_id, payload)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Chat regenerate failed for thread=%s: %s",
                thread_id,
                exc,
                exc_info=True,
            )
            stream_failed = True
            yield _sse("error", get_error_message(classify_exception(exc), locale))
            obs.send(observability_store.record_event,
                     thread_id=thread_id, event_type="error", error=str(exc)[:500])
        finally:
            unregister_cancel(thread_id)
            final_obs_status = "error" if stream_failed else "completed"
            obs.send(observability_store.finalize_session, thread_id, final_obs_status)
            await obs.close()
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
    response_model=None,
    responses={
        200: {
            "description": "Server-Sent Events stream of edited chat tokens",
            "content": {"text/event-stream": {"example": "event: thread_id\ndata: {\"event\": \"thread_id\", \"data\": {\"thread_id\": \"chat:abc123:def456\"}}\n"}},
        },
        400: {"description": "Missing thread_id or message"},
        401: {"description": "Missing or invalid API key"},
    },
)
@limiter.limit("30/minute")
async def chat_edit(
    request: Request,
    user: dict = Depends(get_current_user),
):
    """Edit the last user message and regenerate the assistant response.

    Replaces the last user message with the new text and regenerates the response.
    Returns a Server-Sent Events (SSE) stream — same event types as `/chat/stream`.

    **Request body:** `{"thread_id": "...", "message": "new text", "locale": "en", "timezone": "Asia/Kolkata"}`
    """
    # Body is parsed manually (independent of Content-Type) to allow the frontend
    # to avoid a CORS preflight OPTIONS request (see chat_stream for details).
    try:
        body = json.loads(await request.body())
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="Invalid JSON body")
    raw_thread_id = body.get("thread_id", "")
    if not raw_thread_id:
        raise HTTPException(status_code=400, detail="thread_id required")

    new_message = body.get("message", "")
    if not new_message:
        raise HTTPException(status_code=400, detail="message required")
    _validate_body_fields(body, {"thread_id": 200, "message": 2000, "locale": 10, "timezone": 50, "currency": 10, "client_message_id": 100})

    user_id = user["user_id"]
    thread_id = _scoped_chat_thread_id(raw_thread_id, user_id)
    locale = extract_locale(request, body.get("locale"))
    timezone = body.get("timezone")
    currency = extract_stated_currency(new_message) or body.get("currency")

    # --- Phase 7.2: Daily cost cap + circuit breaker ---
    within_budget, _spent, _cap = await cost_store.check_daily_budget(user_id)
    if not within_budget:
        raise HTTPException(
            status_code=429,
            detail=f"Daily cost limit reached (${_spent:.2f}/${_cap:.2f}). Try again tomorrow.",
        )
    tripped, _p_spent, _p_cap = await cost_store.check_circuit_breaker()
    if tripped:
        raise HTTPException(
            status_code=503,
            detail="Platform temporarily unavailable due to high demand. Please try again shortly.",
        )

    logger.info("POST /chat/edit — thread_id=%s, user=%s", thread_id, user_id)

    async def event_generator():
        yield _sse("thread_id", {"thread_id": thread_id})
        yield _sse("status", {"tool": "agent", "status": "thinking"})

        cancel_event = register_cancel(thread_id)
        active_tasks: dict[str, str] = {}
        subagent_run_ids: set[str] = set()
        stream_failed = False
        stream_text = ""

        # Start observability session
        obs = _ObsQueue()
        obs.send(observability_store.start_session,
                 thread_id, user_id, locale=locale, timezone=timezone or "")

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
                timezone=timezone,
                currency=currency,
                cancel_event=cancel_event,
                client_message_id=body.get("client_message_id"),
            ):
                if cancel_event.is_set():
                    yield _sse("cancelled", None)
                    break
                for payload in _parse_chat_event(event, active_tasks, subagent_run_ids):
                    if payload.get("event") == "token":
                        raw = json.loads(payload["data"])
                        stream_text += raw.get("data", "")
                    yield payload
                    _send_obs_event(obs, thread_id, payload)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Chat edit failed for thread=%s: %s",
                thread_id,
                exc,
                exc_info=True,
            )
            stream_failed = True
            yield _sse("error", get_error_message(classify_exception(exc), locale))
            obs.send(observability_store.record_event,
                     thread_id=thread_id, event_type="error", error=str(exc)[:500])
        finally:
            unregister_cancel(thread_id)
            final_obs_status = "error" if stream_failed else "completed"
            obs.send(observability_store.finalize_session, thread_id, final_obs_status)
            await obs.close()
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


@app.post(
    "/chat/{thread_id}/edit-itinerary",
    summary="Validate a user-edited itinerary via AI",
    tags=["chat"],
    dependencies=[Depends(verify_api_key)],
    response_model=None,
    responses={
        200: {
            "description": "Server-Sent Events stream of AI validation response",
            "content": {"text/event-stream": {"example": "event: itinerary\ndata: {\"event\": \"itinerary\", \"data\": {\"destination\": \"...\"}}\n"}},
        },
        400: {"description": "Missing or invalid itinerary"},
        401: {"description": "Missing or invalid API key"},
    },
)
@limiter.limit("30/minute")
async def chat_edit_itinerary(
    request: Request,
    thread_id: str,
    user: dict = Depends(get_current_user),
):
    """Validate a user-edited itinerary.

    Receives a modified itinerary JSON from the frontend editor, sends it
    to the AI for validation (budget, route, feasibility), and streams
    the validated itinerary back as SSE events.

    **Request body:** `{"itinerary": {...}, "locale": "en", "timezone": "...", "currency": "USD"}`
    """
    # Body is parsed manually (independent of Content-Type) to allow the frontend
    # to avoid a CORS preflight OPTIONS request (see chat_stream for details).
    try:
        body = json.loads(await request.body())
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="Invalid JSON body")
    itinerary_data = body.get("itinerary")
    if not itinerary_data or not isinstance(itinerary_data, dict):
        raise HTTPException(status_code=400, detail="itinerary object required")

    user_id = user["user_id"]
    scoped_thread_id = _scoped_chat_thread_id(thread_id, user_id)
    locale = extract_locale(request, body.get("locale"))
    timezone = body.get("timezone")
    currency = body.get("currency")

    # --- Phase 7.2: Daily cost cap + circuit breaker ---
    within_budget, _spent, _cap = await cost_store.check_daily_budget(user_id)
    if not within_budget:
        raise HTTPException(
            status_code=429,
            detail=f"Daily cost limit reached (${_spent:.2f}/${_cap:.2f}). Try again tomorrow.",
        )
    tripped, _p_spent, _p_cap = await cost_store.check_circuit_breaker()
    if tripped:
        raise HTTPException(
            status_code=503,
            detail="Platform temporarily unavailable due to high demand. Please try again shortly.",
        )

    logger.info("POST /chat/%s/edit-itinerary — user=%s", scoped_thread_id, user_id)

    async def event_generator():
        yield _sse("thread_id", {"thread_id": scoped_thread_id})
        yield _sse("status", {"tool": "agent", "status": "thinking"})

        cancel_event = register_cancel(scoped_thread_id)
        active_tasks: dict[str, str] = {}
        subagent_run_ids: set[str] = set()
        stream_failed = False
        stream_text = ""

        try:
            await thread_store.update_status(user_id, scoped_thread_id, "busy")
        except Exception:  # noqa: BLE001, S110
            pass

        try:
            async for event in edit_itinerary_agent(
                thread_id=scoped_thread_id,
                modified_itinerary=itinerary_data,
                user_id=user_id,
                locale=locale,
                timezone=timezone,
                currency=currency,
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
                "Itinerary edit failed for thread=%s: %s",
                scoped_thread_id,
                exc,
                exc_info=True,
            )
            stream_failed = True
            yield _sse("error", get_error_message(classify_exception(exc), locale))
        finally:
            unregister_cancel(scoped_thread_id)
            try:
                final_status = "error" if stream_failed else "idle"
                summary = await generate_summary("Edit itinerary", stream_text, locale=locale)
                await thread_store.upsert_thread(
                    user_id, scoped_thread_id, summary, status=final_status,
                    search_text=f"Edit itinerary {stream_text[:500]}",
                )
            except Exception:  # noqa: BLE001
                logger.warning("Failed to save thread metadata after itinerary edit", exc_info=True)

    return EventSourceResponse(event_generator())


@app.get(
    "/threads",
    summary="List user's recent threads",
    tags=["threads"],
    dependencies=[Depends(verify_api_key)],
    response_model=ThreadListResponse,
    responses={
        200: {
            "description": "List of threads with pagination info",
            "content": {"application/json": {"example": {
                "threads": [{"thread_id": "chat:abc123:def456", "summary": "Paris trip plan", "created_at": 1735689600, "updated_at": 1735693200, "status": "idle", "message_count": 4, "pinned": False, "pinned_at": 0}],
                "has_more": False,
            }}},
        },
        401: {"description": "Missing or invalid API key"},
    },
)
@limiter.limit("30/minute")
async def list_threads(
    request: Request,
    offset: int = 0,
    limit: int = 20,
    user: dict = Depends(get_current_user),
) -> ThreadListResponse:
    """List the user's recent conversation threads.

    Threads are sorted: pinned first (by pinned_at desc), then by updated_at desc.

    **Query parameters:**
    - `offset`: Pagination offset (default 0)
    - `limit`: Page size (default 20)
    """
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
        headers={"Cache-Control": "private, max-age=300"},
    )


@app.get(
    "/threads/search",
    summary="Search across all user's thread messages",
    tags=["threads"],
    dependencies=[Depends(verify_api_key)],
    response_model=ThreadSearchResponse,
    responses={
        200: {
            "description": "Search results with pagination info",
            "content": {"application/json": {"example": {
                "results": [{"thread_id": "chat:abc123:def456", "summary": "Paris trip", "snippet": "...Eiffel Tower...", "created_at": 1735689600}],
                "total": 1,
                "has_more": False,
            }}},
        },
        401: {"description": "Missing or invalid API key"},
    },
)
@limiter.limit("30/minute")
async def search_threads(
    request: Request,
    q: str = "",
    offset: int = 0,
    limit: int = 20,
    user: dict = Depends(get_current_user),
) -> ThreadSearchResponse:
    """Full-text search across all user's thread message content.

    **Query parameters:**
    - `q`: Search query string
    - `offset`: Pagination offset (default 0)
    - `limit`: Page size (default 20)
    """
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
    response_model=list[ThreadMessage],
    responses={
        200: {
            "description": "List of messages in the thread",
            "content": {"application/json": {"example": [
                {"role": "user", "content": "Plan a trip to Paris"},
                {"role": "assistant", "content": "Here's a 3-day Paris itinerary...", "itinerary": {"destination": "Paris"}},
            ]}},
        },
        401: {"description": "Missing or invalid API key"},
        403: {"description": "Thread does not belong to this user"},
        404: {"description": "Thread not found or empty"},
        503: {"description": "Failed to load thread history"},
    },
)
@limiter.limit("30/minute")
async def get_thread_history(
    thread_id: str,
    request: Request,
    checkpoint_id: str | None = None,
    user: dict = Depends(get_current_user),
) -> list[ThreadMessage]:
    """Get the full message history for a thread.

    **Path parameters:**
    - `thread_id`: The thread ID to fetch history for

    **Query parameters:**
    - `checkpoint_id`: Optional checkpoint ID to fetch a specific version

    Assistant messages may include `itinerary`, `comparison`, `activity`, `images`, and `charts` fields.
    """
    user_id = user["user_id"]
    locale = extract_locale(request)
    logger.info("GET /threads/%s/history user=%s locale=%s checkpoint_id=%s", thread_id, user_id, locale, checkpoint_id)

    # Security: verify the thread belongs to this user
    user_tag = hashlib.sha256(user_id.encode()).hexdigest()[:12]
    if not thread_id.startswith(f"chat:{user_tag}:"):
        raise HTTPException(status_code=403, detail="Thread does not belong to this user")

    try:
        values = await _read_thread_values(thread_id, checkpoint_id)
    except Exception:  # noqa: BLE001 (intentional fallback handler)
        logger.warning("Failed to load thread history for %s", thread_id, exc_info=True)
        raise HTTPException(status_code=503, detail="Failed to load thread history")

    if not values or not values.get("messages"):
        raise HTTPException(status_code=404, detail="Thread not found or empty")

    messages = values.get("messages", [])
    result: list[dict] = []

    # Load persisted activity metadata for this thread (per-message)
    all_activity: dict[str, dict] | None = None
    try:
        from agents.activity_store import load_all_activity as _load_all_activity
        from agents.deep_agent import get_activity_store
        _store = get_activity_store()
        all_activity = await _load_all_activity(_store, thread_id)
    except Exception:
        pass

    # Fallback: try legacy latest-only activity
    legacy_activity = None
    if all_activity is None:
        try:
            from agents.activity_store import load_activity as _load_activity
            from agents.deep_agent import get_activity_store
            _store = get_activity_store()
            legacy_activity = await _load_activity(_store, thread_id)
        except Exception:
            pass

    for i, msg in enumerate(messages):
        role = "user" if getattr(msg, "type", "") == "human" else "assistant"
        content = _history_message_text(getattr(msg, "content", ""))
        if content.strip():
            entry: dict = {"role": role, "content": _strip_structured_tags(content)}
            if role == "assistant":
                itinerary = _extract_itinerary_from_text(content)
                comparison = _extract_comparison_from_text(content)
                if itinerary:
                    itinerary = await _enrich_itinerary_with_coordinates(itinerary)
                    entry["itinerary"] = itinerary
                if comparison:
                    entry["comparison"] = comparison

                # Attach per-message activity
                msg_activity = None
                if all_activity is not None:
                    msg_activity = all_activity.get(str(i))
                elif legacy_activity is not None and i == len(messages) - 1:
                    msg_activity = legacy_activity

                if msg_activity:
                    entry["activity"] = msg_activity
                    # Extract images and charts from activity metadata
                    activity_images = msg_activity.get("images", [])
                    activity_charts = msg_activity.get("charts", [])
                    if activity_images:
                        entry["images"] = activity_images
                    if activity_charts:
                        entry["charts"] = activity_charts

            result.append(entry)

    return JSONResponse(
        content=result,
        headers={"Cache-Control": "private, max-age=300"},
    )


@app.get(
    "/threads/{thread_id}/branches",
    summary="List branches for the last assistant response",
    tags=["threads"],
    dependencies=[Depends(verify_api_key)],
    response_model=ThreadBranchesResponse,
    responses={
        200: {
            "description": "List of branches from the fork point",
            "content": {"application/json": {"example": {
                "branches": [{"checkpoint_id": "abc-123", "is_current": True, "preview": "Here's a 3-day Paris itinerary..."}],
            }}},
        },
        401: {"description": "Missing or invalid API key"},
        403: {"description": "Thread does not belong to this user"},
        503: {"description": "Failed to load branches"},
    },
)
@limiter.limit("30/minute")
async def get_thread_branches(
    thread_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
) -> ThreadBranchesResponse:
    """List all branches (alternative responses) from the last assistant response's fork point.

    **Path parameters:**
    - `thread_id`: The thread ID to inspect

    Returns checkpoints that share the same parent (fork point), with `is_current` flag
    and a 200-char preview of each branch's last message.
    """
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
                "preview": _strip_structured_tags(last_content)[:200],
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
    response_model=ThreadDeleteResponse,
    responses={
        200: {
            "description": "Thread deleted successfully",
            "content": {"application/json": {"example": {"status": "ok", "thread_id": "chat:abc123:def456"}}},
        },
        401: {"description": "Missing or invalid API key"},
        403: {"description": "Thread does not belong to this user"},
        404: {"description": "Thread not found"},
    },
)
@limiter.limit("30/minute")
async def delete_thread(
    thread_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
) -> ThreadDeleteResponse:
    """Delete a thread and its underlying checkpoint state.

    **Path parameters:**
    - `thread_id`: The thread ID to delete

    Removes both the thread metadata and the langgraph checkpointer state.
    """
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
    response_model=ThreadUpdateResponse,
    responses={
        200: {
            "description": "Thread updated successfully",
            "content": {"application/json": {"example": {"status": "ok", "thread_id": "chat:abc123:def456"}}},
        },
        401: {"description": "Missing or invalid API key"},
        403: {"description": "Thread does not belong to this user"},
        404: {"description": "Thread not found"},
    },
)
@limiter.limit("30/minute")
async def update_thread(
    thread_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
) -> ThreadUpdateResponse:
    """Update thread metadata (e.g., pin or unpin a thread).

    **Path parameters:**
    - `thread_id`: The thread ID to update

    **Request body:** `ThreadUpdateRequest` with optional `pinned` boolean.
    """
    # Body is parsed manually (independent of Content-Type) so the frontend can
    # avoid a CORS preflight OPTIONS request (see chat_stream for details).
    try:
        body = ThreadUpdateRequest(**json.loads(await request.body()))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail="Invalid request body.")

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


@app.get(
    "/auth/login",
    summary="Google OAuth login",
    tags=["auth"],
    response_model=None,
    responses={
        302: {"description": "Redirect to Google OAuth consent screen"},
        503: {"description": "Google OAuth is not configured on this server"},
    },
)
async def auth_login(request: Request) -> RedirectResponse:
    """Redirect to Google OAuth consent screen.

    Always redirects to Google OAuth — no dev bypass.

    **Returns:** 302 redirect — no JSON response.
    """
    if not hasattr(oauth, "google") or not (settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Google OAuth is not configured. Please set GOOGLE_CLIENT_ID and "
                "GOOGLE_CLIENT_SECRET in your Hugging Face Space secrets or environment variables."
            ),
        )

    redirect_uri = settings.OAUTH_REDIRECT_URI
    if "localhost" in redirect_uri and "localhost" not in str(request.base_url):
        proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        host = request.headers.get("x-forwarded-host", request.url.netloc)
        redirect_uri = f"{proto}://{host}/auth/callback"

    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get(
    "/auth/callback",
    summary="OAuth callback handler",
    tags=["auth"],
    response_model=None,
    responses={
        302: {"description": "Redirect to frontend with session cookie set"},
        400: {"description": "No email in Google response"},
        503: {"description": "Google OAuth is not configured"},
    },
)
async def auth_callback(request: Request) -> RedirectResponse:
    """Handle Google OAuth callback — exchange code for user info, create session.

    Sets a session cookie and redirects to the frontend callback URL.

    **Returns:** 302 redirect with `Set-Cookie` header.
    """
    if not hasattr(oauth, "google") or not (settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured.",
        )

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
    logger.info("OAuth callback: session created for %s (id=%s)", email, session_id[:12])

    redirect_target = f"{_frontend_base_url()}/auth/callback?success=1&token={session_id}"
    logger.info("OAuth callback: redirecting to %s", redirect_target[:80])
    resp = RedirectResponse(url=redirect_target)
    resp.set_cookie(
        SESSION_COOKIE_NAME, session_id,
        max_age=SESSION_TTL, httponly=True,
        samesite="none" if _use_secure_cookies else "lax",
        secure=_use_secure_cookies,
        path="/",
    )
    return resp


@app.post(
    "/auth/logout",
    summary="Logout",
    tags=["auth"],
    response_model=AuthLogoutResponse,
    responses={
        200: {
            "description": "Logged out successfully",
            "content": {"application/json": {"example": {"status": "ok"}}},
        },
    },
)
async def auth_logout(request: Request) -> AuthLogoutResponse:
    """Clear session cookie and delete session from Redis.

    No authentication required — always returns 200.
    """
    session_id = (
        request.cookies.get(SESSION_COOKIE_NAME)
        or request.headers.get("X-Session-Token")
        or request.query_params.get("session_token")
    )
    if session_id:
        await delete_session(session_id)
    response = JSONResponse({"status": "ok"})
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        samesite="none" if _use_secure_cookies else "lax",
        secure=_use_secure_cookies,
        path="/",
    )
    return response


@app.get(
    "/auth/me",
    summary="Get current user",
    tags=["auth"],
    response_model=AuthMeResponse,
    responses={
        200: {
            "description": "Current user info",
            "content": {"application/json": {"example": {
                "user_id": "user@example.com",
                "display_name": "Jane Doe",
                "avatar_url": "https://lh3.googleusercontent.com/...",
                "email": "user@example.com",
            }}},
        },
        401: {"description": "Not authenticated"},
    },
)
async def auth_me(user: dict = Depends(get_current_user)) -> AuthMeResponse:
    """Return current user info from session.

    Requires a valid session cookie.
    """
    return AuthMeResponse(
        user_id=user["user_id"],
        display_name=user.get("display_name", ""),
        avatar_url=user.get("avatar_url"),
        email=user.get("email", user["user_id"]),
        is_admin=is_admin_email(user.get("email") or user.get("user_id") or ""),
    )


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
        values = await _read_thread_values(thread_id)
    except Exception:  # noqa: BLE001
        logger.warning("Failed to load state for export/share thread=%s", thread_id, exc_info=True)
        return None
    if not values:
        return None
    return _extract_chat_itinerary(values)


@app.post(
    "/share/{thread_id}",
    summary="Create a shareable link for an itinerary",
    tags=["share"],
    dependencies=[Depends(verify_api_key)],
    response_model=ShareCreateResponse,
    responses={
        200: {
            "description": "Share link created",
            "content": {"application/json": {"example": {
                "share_url": "http://localhost:3000/en/share/abc123def456",
                "expires_at": 1736294400,
                "destination": "Paris",
            }}},
        },
        401: {"description": "Missing or invalid API key"},
        404: {"description": "No itinerary found in this thread"},
    },
)
@limiter.limit("10/minute")
async def create_share_link(
    thread_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
) -> ShareCreateResponse:
    """Create a shareable link for an itinerary.

    **Path parameters:**
    - `thread_id`: The thread containing the itinerary to share

    The itinerary is enriched with coordinates and stored with a token.
    Share links expire after `SHARE_TTL_DAYS` (default 7 days).
    """
    user_id = user["user_id"]
    itinerary = await _get_latest_itinerary(thread_id, user_id)
    if itinerary is None:
        raise HTTPException(status_code=404, detail="No itinerary found in this thread")
    itinerary = await _enrich_itinerary_with_coordinates(itinerary)
    destination = itinerary.get("destination", "Untitled Trip")
    itinerary_json = json.dumps(itinerary)
    image_base64 = await generate_destination_image(destination)
    token, expires_at = await share_store.create_share(
        user_id, thread_id, itinerary_json, destination, image_base64=image_base64,
    )
    locale = extract_locale(request) or "en"
    share_url = f"{_frontend_base_url()}/{locale}/share/{token}"
    logger.info("Created share link for user=%s thread=%s token=%s", user_id, thread_id, token[:8])
    return {"share_url": share_url, "expires_at": expires_at, "destination": destination}


@app.get(
    "/share/{token}",
    summary="Get shared itinerary (public, no auth)",
    tags=["share"],
    response_model=ShareGetResponse,
    responses={
        200: {
            "description": "Shared itinerary data",
            "content": {"application/json": {"example": {
                "itinerary": {"destination": "Paris", "total_days": 3, "estimated_total_cost_usd": 1500},
                "destination": "Paris",
                "created_at": 1735689600,
                "expires_at": 1736294400,
            }}},
        },
        404: {"description": "Share link not found or expired"},
        500: {"description": "Corrupted share data"},
    },
)
@limiter.limit("60/minute")
async def get_shared_itinerary(
    token: str,
    request: Request,
) -> ShareGetResponse:
    """Get a shared itinerary by token.

    **Public endpoint — no authentication required.**

    **Path parameters:**
    - `token`: The share token from the URL
    """
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
        "image_base64": data.get("image_base64"),
    }


@app.delete(
    "/share/{token}",
    summary="Revoke a share link",
    tags=["share"],
    dependencies=[Depends(verify_api_key)],
    response_model=ShareRevokeResponse,
    responses={
        200: {
            "description": "Share link revoked",
            "content": {"application/json": {"example": {"status": "ok"}}},
        },
        401: {"description": "Missing or invalid API key"},
        404: {"description": "Share link not found"},
    },
)
@limiter.limit("20/minute")
async def revoke_share_link(
    token: str,
    request: Request,
    user: dict = Depends(get_current_user),
) -> ShareRevokeResponse:
    """Revoke a share link.

    **Path parameters:**
    - `token`: The share token to revoke

    Only the original creator can revoke a share link.
    """
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
    response_model=list[ShareListItem],
    responses={
        200: {
            "description": "List of active share links",
            "content": {"application/json": {"example": [
                {"token": "abc123def456", "thread_id": "chat:abc123:def456", "destination": "Paris", "created_at": 1735689600, "expires_at": 1736294400, "share_url": "https://app.example.com/en/share/abc123def456"},
            ]}},
        },
        401: {"description": "Missing or invalid API key"},
    },
)
@limiter.limit("30/minute")
async def list_shares(
    request: Request,
    user: dict = Depends(get_current_user),
) -> list[ShareListItem]:
    """List all active share links for the current user.

    Expired shares are automatically filtered out.
    """
    user_id = user["user_id"]
    shares = await share_store.list_shares(user_id)
    locale = extract_locale(request) or "en"
    base = _frontend_base_url()
    return [
        {
            "token": s.token,
            "thread_id": s.thread_id,
            "destination": s.destination,
            "created_at": s.created_at,
            "expires_at": s.expires_at,
            "share_url": f"{base}/{locale}/share/{s.token}",
        }
        for s in shares
    ]


@app.get(
    "/export/{thread_id}",
    summary="Export itinerary as JSON, Markdown, or iCal",
    tags=["export"],
    dependencies=[Depends(verify_api_key)],
    response_model=None,
    responses={
        200: {
            "description": "Exported itinerary file",
            "content": {
                "application/json": {"example": {"destination": "Paris", "total_days": 3}},
                "text/markdown": {"example": "# Paris\n\n**Duration:** 3 days"},
                "text/calendar": {"example": "BEGIN:VCALENDAR\nVERSION:2.0\n..."},
            },
        },
        401: {"description": "Missing or invalid API key"},
        404: {"description": "No itinerary found in this thread"},
    },
)
@limiter.limit("10/minute")
async def export_itinerary(
    thread_id: str,
    request: Request,
    fmt: str = "json",
    user: dict = Depends(get_current_user),
) -> JSONResponse | PlainTextResponse:
    """Export an itinerary in JSON, Markdown, or iCal format.

    **Path parameters:**
    - `thread_id`: The thread containing the itinerary

    **Query parameters:**
    - `fmt`: Export format — "json" (default), "markdown", or "ical"

    Returns a file download with appropriate `Content-Type` and `Content-Disposition` headers.
    """
    user_id = user["user_id"]
    itinerary = await _get_latest_itinerary(thread_id, user_id)
    if itinerary is None:
        raise HTTPException(status_code=404, detail="No itinerary found in this thread")
    itinerary = await _enrich_itinerary_with_coordinates(itinerary)
    if fmt == "ical":
        ics_content = generate_ics(itinerary, thread_id=thread_id)
        return PlainTextResponse(
            ics_content,
            media_type="text/calendar",
            headers={"Content-Disposition": f'attachment; filename="{itinerary.get("destination", "itinerary").replace(" ", "_")}.ics"'},
        )
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
async def _export_openapi_schema() -> None:
    """Export OpenAPI JSON to static file for frontend consumption."""
    import os
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    os.makedirs(static_dir, exist_ok=True)
    schema = app.openapi()
    path = os.path.join(static_dir, "openapi.json")
    with open(path, "w") as f:
        json.dump(schema, f, indent=2)
    logger.info("OpenAPI schema exported to %s (%d endpoints)", path, len(schema.get("paths", {})))


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
            try:
                from sqlite_fallback import cleanup_expired
                deleted = await cleanup_expired()
                if deleted:
                    logger.info("SQLite fallback cleanup: %d expired rows", deleted)
            except Exception:  # noqa: BLE001
                logger.warning("SQLite fallback cleanup task error", exc_info=True)
            try:
                await cost_store.cleanup_expired()
                await observability_store.cleanup_expired()
            except Exception:  # noqa: BLE001
                logger.warning("Store cleanup task error", exc_info=True)

    app.state._cleanup_task = asyncio.create_task(_cleanup_loop())


@app.on_event("startup")
async def _warn_multi_worker() -> None:
    """Warn when running with >1 worker — several stores keep in-process state.

    cancel_registry, per-thread search quota, _mem fallbacks, and checkpointer
    caches are all per-process; multiple workers get divergent private copies.
    """
    import os
    for var in ("UVICORN_WORKERS", "WEB_CONCURRENCY", "GUNICORN_WORKERS"):
        try:
            workers = int(os.getenv(var, "") or 0)
        except ValueError:
            continue
        if workers > 1:
            logger.warning(
                "%s=%d: multi-worker deployment detected — in-process state "
                "(cancel_registry, _search_counts, _mem fallbacks, checkpointer "
                "caches) is per-worker and will diverge. Use a single worker or "
                "shared durable stores.",
                var, workers,
            )
            break


@app.on_event("shutdown")
async def _cancel_thread_cleanup_task() -> None:
    """Cancel the background cleanup task on shutdown."""
    task = getattr(app.state, "_cleanup_task", None)
    if task is not None:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


# --- Prometheus metrics endpoint (Phase 7.4) ---

if settings.PROMETHEUS_ENABLED:
    from prometheus_fastapi_instrumentator import Instrumentator

    Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        should_respect_env_var=False,
        excluded_handlers=["/metrics"],
    ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
