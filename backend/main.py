from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from dataclasses import asdict

from fastapi import Depends, FastAPI, HTTPException, Request
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
    _extract_comparison_from_text,
    _extract_itinerary_from_text,
    create_checkpointer,
)
from auth import verify_api_key
from cache import cache_client
from config import REQUEST_TIMEOUT_SECONDS, logger, settings
from models import ChatRequest
from oauth import (
    DEV_USER,
    SESSION_COOKIE_NAME,
    SESSION_TTL,
    create_session,
    delete_session,
    get_current_user,
    oauth,
)
from sanitize import sanitize_prompt_input
from threads import generate_summary, thread_store

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
    if event_type == "comparison" and event_data is not None:
        return [_sse("comparison", event_data)]
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

    if event_type == "on_tool_error":
        run_id = event.get("run_id", "")
        if run_id in active_tasks:
            subagent_type = active_tasks.pop(run_id)
            return [_sse("status", {"tool": subagent_type, "status": "error"})]
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
async def get_preferences(request: Request, user: dict = Depends(get_current_user)) -> PlainTextResponse:
    user_id = user["user_id"]
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
    body = await request.body()
    content = body.decode("utf-8") if body else ""
    try:
        store = get_redis_file_store()
        store.put((user_id,), "/preferences.md", {"content": content, "encoding": "utf-8"})
    except Exception:  # noqa: BLE001 (intentional fallback handler)
        logger.warning("Preferences store unavailable — preferences not saved")
        return {"status": "error", "user_id": user_id, "error": "Preferences store unavailable"}
    logger.info("Saved preferences for user=%s (%d bytes)", user_id, len(content))
    return {"status": "ok", "user_id": user_id}


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
        stream_failed = False
        stream_text = ""

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
            ):
                for payload in _parse_chat_event(event, active_tasks):
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
            yield _sse("error", f"Streaming failed: {exc}")
        finally:
            # Save/update thread metadata with AI summary and status — never blocks stream
            try:
                final_status = "error" if stream_failed else "idle"
                summary = await generate_summary(_msg_safe, stream_text)
                await thread_store.upsert_thread(
                    user_id, thread_id, summary, status=final_status,
                )
            except Exception:  # noqa: BLE001 (intentional fallback handler)
                logger.warning("Failed to save thread metadata", exc_info=True)
                try:
                    await thread_store.upsert_thread(
                        user_id, thread_id, _msg_safe[:100], status="error" if stream_failed else "idle",
                    )
                except Exception:  # noqa: BLE001, S110
                    pass

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
    threads = await thread_store.list_threads(user_id, limit=limit, offset=offset)
    total = await thread_store.count_threads(user_id)
    return {
        "threads": [asdict(t) for t in threads],
        "has_more": (offset + limit) < total,
    }


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
    user: dict = Depends(get_current_user),
) -> list[dict]:
    user_id = user["user_id"]

    # Security: verify the thread belongs to this user
    user_tag = hashlib.sha256(user_id.encode()).hexdigest()[:12]
    if not thread_id.startswith(f"chat:{user_tag}:"):
        raise HTTPException(status_code=403, detail="Thread does not belong to this user")

    try:
        agent = await create_chat_agent(user_id=user_id)
        config = {
            "configurable": {"thread_id": thread_id, "user_id": user_id},
            "recursion_limit": 50,
        }
        state = await agent.aget_state(config)
    except Exception:  # noqa: BLE001 (intentional fallback handler)
        logger.warning("Failed to load thread history for %s", thread_id, exc_info=True)
        raise HTTPException(status_code=503, detail="Failed to load thread history")

    if state is None or not state.values or not state.values.get("messages"):
        raise HTTPException(status_code=404, detail="Thread not found or empty")

    messages = state.values.get("messages", [])
    result: list[dict] = []
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
                    entry["itinerary"] = itinerary
                if comparison:
                    entry["comparison"] = comparison
            result.append(entry)

    return result


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
