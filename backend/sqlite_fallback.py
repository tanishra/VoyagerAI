"""Shared SQLite fallback for all Redis-backed stores.

When Redis is unavailable, stores fall back to SQLite (persistent) before
the in-memory last resort. This module provides a single shared async
connection, schema creation, versioning, and TTL cleanup.

Usage:
    from sqlite_fallback import get_sqlite_connection, cleanup_expired

    db = await get_sqlite_connection()
    if db is not None:
        await db.execute("INSERT OR REPLACE INTO threads (...) VALUES (...)", (...))
        await db.commit()
"""

from __future__ import annotations

import logging
import os
import time

import aiosqlite

from config import settings

logger = logging.getLogger("travel_agent.sqlite_fallback")

_SCHEMA_VERSION = 1

_SCHEMA_SQL = """
-- ThreadStore
CREATE TABLE IF NOT EXISTS threads (
    thread_id TEXT PRIMARY KEY,
    user_tag TEXT NOT NULL,
    summary TEXT,
    created_at REAL,
    updated_at REAL,
    status TEXT DEFAULT 'idle',
    message_count INTEGER DEFAULT 0,
    search_text TEXT,
    pinned INTEGER DEFAULT 0,
    pinned_at REAL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_threads_user_tag ON threads(user_tag);
CREATE INDEX IF NOT EXISTS idx_threads_updated ON threads(user_tag, updated_at DESC);

-- ShareStore
CREATE TABLE IF NOT EXISTS shares (
    token TEXT PRIMARY KEY,
    user_tag TEXT NOT NULL,
    thread_id TEXT,
    destination TEXT,
    itinerary_json TEXT,
    created_at REAL,
    expires_at REAL
);
CREATE INDEX IF NOT EXISTS idx_shares_user_tag ON shares(user_tag);

-- OAuth sessions
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    payload_json TEXT,
    created_at REAL,
    expires_at REAL
);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);

-- CostStore
CREATE TABLE IF NOT EXISTS costs_session (
    thread_id TEXT PRIMARY KEY,
    user_id TEXT,
    total_input_tokens INTEGER,
    total_output_tokens INTEGER,
    total_cost_usd REAL,
    efficiency_ratio REAL,
    budget_limit_usd REAL,
    budget_reached INTEGER,
    created_at REAL
);
CREATE TABLE IF NOT EXISTS costs_subagent (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id TEXT,
    subagent_name TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd REAL,
    model_used TEXT,
    timestamp REAL
);
CREATE INDEX IF NOT EXISTS idx_costs_subagent_thread ON costs_subagent(thread_id);

-- FeedbackStore
CREATE TABLE IF NOT EXISTS feedback (
    key TEXT PRIMARY KEY,
    user_id TEXT,
    message_id TEXT,
    thread_id TEXT,
    rating TEXT,
    comment TEXT,
    created_at REAL,
    updated_at REAL
);
CREATE INDEX IF NOT EXISTS idx_feedback_thread ON feedback(thread_id);

-- SecurityStore
CREATE TABLE IF NOT EXISTS security_flags (
    flag_id TEXT PRIMARY KEY,
    user_hash TEXT,
    category TEXT,
    confidence REAL,
    source TEXT,
    thread_id TEXT,
    reasoning_snippet TEXT,
    created_at REAL
);
CREATE INDEX IF NOT EXISTS idx_security_flags_user ON security_flags(user_hash);
CREATE TABLE IF NOT EXISTS security_strikes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_hash TEXT,
    created_at REAL
);
CREATE INDEX IF NOT EXISTS idx_security_strikes_user ON security_strikes(user_hash);
CREATE TABLE IF NOT EXISTS security_cooldowns (
    user_hash TEXT PRIMARY KEY,
    cooldown_until REAL
);

-- ResearchCache
CREATE TABLE IF NOT EXISTS research_cache (
    key TEXT PRIMARY KEY,
    value TEXT,
    created_at REAL,
    expires_at REAL
);

-- GeocodeCache
CREATE TABLE IF NOT EXISTS geocode_cache (
    query_hash TEXT PRIMARY KEY,
    lat REAL,
    lng REAL,
    created_at REAL
);

-- FileStore
CREATE TABLE IF NOT EXISTS files (
    file_id TEXT PRIMARY KEY,
    user_tag TEXT,
    filename TEXT,
    content_type TEXT,
    size INTEGER,
    data_base64 TEXT,
    created_at REAL,
    expires_at REAL
);
CREATE INDEX IF NOT EXISTS idx_files_user_tag ON files(user_tag);

-- RateLimiter (Phase 7.2)
CREATE TABLE IF NOT EXISTS rate_limits (
    key TEXT NOT NULL,
    timestamp REAL NOT NULL,
    PRIMARY KEY (key, timestamp)
);
"""

_conn: aiosqlite.Connection | None = None
_init_failed = False


async def get_sqlite_connection() -> aiosqlite.Connection | None:
    """Return shared async SQLite connection, creating the DB + schema on first call.

    Returns None if SQLite cannot be initialised (in-memory fallback is the
    last resort).
    """
    global _conn, _init_failed
    if _init_failed:
        return None
    if _conn is not None:
        return _conn
    try:
        path = settings.SQLITE_FALLBACK_DB_PATH
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        _conn = await aiosqlite.connect(path)
        _conn.row_factory = aiosqlite.Row
        await _conn.execute("PRAGMA journal_mode=WAL")
        await _conn.execute("PRAGMA synchronous=NORMAL")
        await _conn.executescript(_SCHEMA_SQL)
        await _conn.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
        await _conn.commit()
        logger.info("SQLite fallback DB initialised at %s", path)
        return _conn
    except Exception as exc:  # noqa: BLE001
        logger.warning("SQLite fallback init failed: %s", exc)
        _init_failed = True
        return None


async def cleanup_expired() -> int:
    """Delete expired rows from all tables with an ``expires_at`` column.

    Returns the total number of rows deleted.
    """
    db = await get_sqlite_connection()
    if db is None:
        return 0
    now = time.time()
    total = 0
    try:
        for table in ("shares", "sessions", "research_cache", "files"):
            cur = await db.execute(
                f"DELETE FROM {table} WHERE expires_at < ?", (now,)
            )
            total += cur.rowcount
        # Rate limits: keep 1 hour of history
        cur = await db.execute(
            "DELETE FROM rate_limits WHERE timestamp < ?", (now - 3600,)
        )
        total += cur.rowcount
        await db.commit()
        if total:
            logger.info("SQLite cleanup: deleted %d expired rows", total)
    except Exception as exc:  # noqa: BLE001
        logger.warning("SQLite cleanup failed: %s", exc)
    return total


async def close_connection() -> None:
    """Close the shared connection (called on app shutdown)."""
    global _conn
    if _conn is not None:
        try:
            await _conn.close()
        except Exception:  # noqa: BLE001, S110
            pass
        _conn = None
