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

# Mock user for test session injection (not used for runtime bypass)
DEV_USER: dict = {
    "user_id": "dev@localhost",
    "display_name": "Dev User",
    "avatar_url": None,
    "email": "dev@localhost",
}


async def _get_redis() -> Redis | None:
    """Get a Redis connection for session storage."""
    try:
        r = Redis.from_url(settings.REDIS_URL, decode_responses=True)
        await r.ping()
        return r
    except (RedisError, RuntimeError) as exc:
        logger.warning("Session Redis unavailable: %s", exc)
        return None


async def create_session(user_info: dict) -> str:
    """Create a session in Redis (or SQLite / in-memory fallback) and return the session ID."""
    session_id = secrets.token_urlsafe(32)
    now = int(time.time())
    payload = {
        **user_info,
        "created_at": now,
        "exp": now + SESSION_TTL,
    }
    r = await _get_redis()
    if r is not None:
        try:
            await r.set(
                f"{SESSION_REDIS_PREFIX}{session_id}",
                json.dumps(payload),
                ex=SESSION_TTL,
            )
            return session_id
        except (RedisError, RuntimeError) as exc:
            logger.warning("Session Redis write failed — using fallback: %s", exc)
        finally:
            await r.aclose()

    # SQLite fallback
    db = await get_sqlite_connection()
    if db is not None:
        try:
            await db.execute(
                "INSERT OR REPLACE INTO sessions (session_id, payload_json, created_at, expires_at) VALUES (?, ?, ?, ?)",
                (session_id, json.dumps(payload), now, now + SESSION_TTL),
            )
            await db.commit()
            return session_id
        except Exception as exc:  # noqa: BLE001
            logger.warning("Session SQLite write failed — using in-memory: %s", exc)

    # In-memory fallback
    _mem_sessions[session_id] = payload
    return session_id


async def get_session(session_id: str) -> dict | None:
    """Read a session by ID from Redis (or SQLite / in-memory fallback)."""
    r = await _get_redis()
    if r is not None:
        try:
            data = await r.get(f"{SESSION_REDIS_PREFIX}{session_id}")
            if data:
                return json.loads(data)
        except (RedisError, RuntimeError):
            logger.warning("Failed to read session from Redis")
        finally:
            await r.aclose()

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
            logger.warning("Session SQLite read failed — using in-memory: %s", exc)

    # In-memory fallback
    return _mem_sessions.get(session_id)


async def delete_session(session_id: str) -> None:
    """Delete a session from Redis, SQLite, and in-memory fallback (logout)."""
    _mem_sessions.pop(session_id, None)
    r = await _get_redis()
    if r is not None:
        try:
            await r.delete(f"{SESSION_REDIS_PREFIX}{session_id}")
        except (RedisError, RuntimeError):
            logger.warning("Failed to delete session from Redis")
        finally:
            await r.aclose()

    # SQLite fallback
    db = await get_sqlite_connection()
    if db is not None:
        try:
            await db.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            await db.commit()
        except Exception:  # noqa: BLE001, S110
            pass


async def get_current_user(request: Request) -> dict:
    """FastAPI dependency: extract and verify the user from the session cookie.

    Returns a dict with keys: user_id, display_name, avatar_url, email.
    Raises 401 if not authenticated.
    """
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Cookie"},
        )

    session = await get_session(session_id)
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
