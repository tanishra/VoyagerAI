"""Google OAuth 2.0 authentication with Redis-backed sessions.

Provides:
- OAuth client configuration (authlib + Google)
- Session create / read / delete in Redis
- get_current_user FastAPI dependency for protected endpoints
- DEV_USER mock dict for test session injection (no runtime bypass)
"""

from __future__ import annotations

import json
import logging
import secrets
import time

from authlib.integrations.starlette_client import OAuth
from fastapi import Depends, HTTPException, Request, status
from redis.asyncio import Redis
from redis.exceptions import RedisError

from config import settings
from sqlite_fallback import get_sqlite_connection

logger = logging.getLogger("travel_agent.oauth")

# --- OAuth client setup ---
oauth = OAuth()

if settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET:
    oauth.register(
        name="google",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

SESSION_COOKIE_NAME = "voyager_session"
SESSION_TTL = 7 * 24 * 3600  # 7 days in seconds
SESSION_REDIS_PREFIX = "session:"

# In-memory session fallback (used when Redis is unavailable — same pattern as cache.py / threads.py)
_mem_sessions: dict[str, dict] = {}


def _prune_mem_sessions() -> None:
    """Drop expired entries from the in-memory session fallback."""
    now = time.time()
    for sid in [sid for sid, p in _mem_sessions.items() if float(p.get("exp", 0)) <= now]:
        _mem_sessions.pop(sid, None)

# Mock user for test session injection (not used for runtime bypass)
DEV_USER: dict = {
    "user_id": "dev@localhost",
    "display_name": "Dev User",
    "avatar_url": None,
    "email": "dev@localhost",
}


_redis_client: Redis | None = None


async def _get_redis() -> Redis | None:
    """Shared Redis client for session storage.

    Cached after the first successful ping (redis.asyncio has an internal
    connection pool — safe for concurrent use). Dropped via _drop_redis()
    when an operation fails so the next call reconnects.
    """
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        r = Redis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)
        await r.ping()
        _redis_client = r
        return r
    except (RedisError, RuntimeError) as exc:
        logger.warning("Session Redis unavailable: %s", exc)
        return None


async def _drop_redis() -> None:
    """Discard the pooled client after a failed op — next call reconnects."""
    global _redis_client
    r, _redis_client = _redis_client, None
    if r is not None:
        try:
            await r.aclose()
        except Exception:  # noqa: BLE001, S110
            pass


async def create_session(user_info: dict) -> str:
    """Create a session, writing through to Redis AND SQLite (in-memory only as last resort).

    Write-through ensures a transient Redis read failure later cannot orphan the
    session — the SQLite copy still resolves it.
    """
    session_id = secrets.token_urlsafe(32)
    now = int(time.time())
    payload = {
        **user_info,
        "created_at": now,
        "exp": now + SESSION_TTL,
    }
    persisted = False

    r = await _get_redis()
    if r is not None:
        try:
            await r.set(
                f"{SESSION_REDIS_PREFIX}{session_id}",
                json.dumps(payload),
                ex=SESSION_TTL,
            )
            persisted = True
        except (RedisError, RuntimeError) as exc:
            await _drop_redis()
            logger.warning("Session Redis write failed: %s", exc)

    # SQLite fallback (also acts as the durable copy when Redis is up)
    db = await get_sqlite_connection()
    if db is not None:
        try:
            await db.execute(
                "INSERT OR REPLACE INTO sessions (session_id, payload_json, created_at, expires_at) VALUES (?, ?, ?, ?)",
                (session_id, json.dumps(payload), now, now + SESSION_TTL),
            )
            await db.commit()
            persisted = True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Session SQLite write failed: %s", exc)

    if not persisted:
        _prune_mem_sessions()
        _mem_sessions[session_id] = payload
    return session_id


class SessionStoreUnavailable(Exception):
    """All durable session stores failed — lookup result can't be trusted."""


async def get_session(session_id: str) -> dict | None:
    """Read a session by ID from Redis (or SQLite / in-memory fallback).

    Returns None when the session genuinely isn't found. Raises
    SessionStoreUnavailable when a durable store errored and the session
    was not found anywhere — a miss under failure isn't trustworthy.
    """
    store_errors = 0
    r = await _get_redis()
    if r is not None:
        try:
            data = await r.get(f"{SESSION_REDIS_PREFIX}{session_id}")
            if data:
                return json.loads(data)
        except (RedisError, RuntimeError):
            store_errors += 1
            await _drop_redis()
            logger.warning("Failed to read session from Redis")

    # SQLite fallback
    db = await get_sqlite_connection()
    if db is not None:
        try:
            cur = await db.execute(
                "SELECT payload_json, expires_at FROM sessions WHERE session_id = ?",
                (session_id,),
            )
            row = await cur.fetchone()
            if row:
                if float(row["expires_at"]) < time.time():
                    await db.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
                    await db.commit()
                    return None
                return json.loads(row["payload_json"])
        except Exception as exc:  # noqa: BLE001
            store_errors += 1
            logger.warning("Session SQLite read failed — using in-memory: %s", exc)

    session = _mem_sessions.get(session_id)
    if session is not None and float(session.get("exp", 0)) <= time.time():
        _mem_sessions.pop(session_id, None)
        session = None
    if session is None and store_errors:
        raise SessionStoreUnavailable(f"{store_errors} session store(s) failed during lookup")
    return session


async def delete_session(session_id: str) -> None:
    """Delete a session from Redis, SQLite, and in-memory fallback (logout)."""
    _mem_sessions.pop(session_id, None)
    r = await _get_redis()
    if r is not None:
        try:
            await r.delete(f"{SESSION_REDIS_PREFIX}{session_id}")
        except (RedisError, RuntimeError):
            await _drop_redis()
            logger.warning("Failed to delete session from Redis")

    # SQLite fallback
    db = await get_sqlite_connection()
    if db is not None:
        try:
            await db.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            await db.commit()
        except Exception:  # noqa: BLE001, S110
            pass


async def get_current_user(request: Request) -> dict:
    """FastAPI dependency: extract and verify the user from the session cookie or token.

    Checks the session cookie first, then falls back to the X-Session-Token header,
    then the session_token query parameter (used when third-party cookies are
    blocked by the browser and a custom header would trigger a CORS preflight
    that some hosting proxies mishandle).

    Returns a dict with keys: user_id, display_name, avatar_url, email.
    Raises 401 if not authenticated.
    """
    candidates = [
        request.cookies.get(SESSION_COOKIE_NAME),
        request.headers.get("X-Session-Token"),
        request.query_params.get("session_token"),
    ]
    if not any(candidates):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Cookie"},
        )

    # Try each candidate in turn — a stale cookie must not shadow a valid token.
    session = None
    try:
        for session_id in dict.fromkeys(s for s in candidates if s):
            session = await get_session(session_id)
            if session:
                break
    except SessionStoreUnavailable:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Session store temporarily unavailable",
            headers={"Retry-After": "2"},
        )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid",
            headers={"WWW-Authenticate": "Cookie"},
        )

    return {
        "user_id": session["user_id"],
        "display_name": session.get("display_name", ""),
        "avatar_url": session.get("avatar_url"),
        "email": session.get("email", session["user_id"]),
    }


async def verify_admin(user: dict = Depends(get_current_user)) -> dict:
    """FastAPI dependency: verify the authenticated user is an admin.

    Checks the user's email against the ADMIN_EMAILS setting (comma-separated).
    Raises 403 if admin emails are not configured or the user is not an admin.
    """
    if not is_admin_email(user.get("email") or ""):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    return user


def is_admin_email(email: str) -> bool:
    """Check whether an email address is in the ADMIN_EMAILS allowlist."""
    admin_emails = [e.strip().lower() for e in settings.ADMIN_EMAILS.split(",") if e.strip()]
    if not admin_emails:
        return False
    return email.lower() in admin_emails
