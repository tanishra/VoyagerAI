"""Observability store — Redis-backed with SQLite + in-memory fallback.

Stores per-session SSE event traces for the admin observability dashboard.
Follows the same graceful degradation pattern as cost_store.py and feedback_store.py.

Redis key layout:
  observability:events:{thread_id}     — list of JSON event records
  observability:sessions              — sorted set: thread_id → start_timestamp
  observability:errors                — sorted set: thread_id → timestamp
  observability:session:{thread_id}   — hash: session summary data
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field

from redis.asyncio import Redis
from redis.exceptions import RedisError

from config import REDIS_URL, settings
from sqlite_fallback import get_sqlite_connection

logger = logging.getLogger("travel_agent.observability_store")

_TTL_SECONDS: int = settings.THREAD_TTL_DAYS * 86_400

# Fields to redact from tool inputs (PII / sensitive data)
_PII_FIELDS = {"message", "query", "search_query", "q", "content", "text", "data_url", "image_url"}
_REDACT_FIELDS = {"messages", "input", "user_instructions"}


def _hash_user_id(user_id: str) -> str:
    """Hash a user ID for storage — never store raw user IDs."""
    return hashlib.sha256(user_id.encode()).hexdigest()[:12]


def _redact_tool_input(tool_input) -> dict | str | None:
    """Redact PII from tool input before storing.

    Keeps structural metadata (subagent_type, description, url, name, etc.)
    but replaces sensitive text fields with length + hash.
    """
    if tool_input is None:
        return None
    if isinstance(tool_input, str):
        if len(tool_input) > 500:
            return tool_input[:500] + "..."
        return tool_input
    if not isinstance(tool_input, dict):
        return str(tool_input)[:500]

    redacted: dict = {}
    for key, value in tool_input.items():
        if key in _PII_FIELDS:
            if isinstance(value, str) and value:
                redacted[key] = {
                    "_redacted": True,
                    "length": len(value),
                    "hash": hashlib.sha256(value.encode()).hexdigest()[:12],
                }
            else:
                redacted[key] = {"_redacted": True}
        elif key in _REDACT_FIELDS:
            redacted[key] = {"_redacted": True, "length": len(str(value))}
        elif isinstance(value, str):
            redacted[key] = value[:500] if len(value) > 500 else value
        elif isinstance(value, dict):
            redacted[key] = _redact_tool_input(value)
        elif isinstance(value, list):
            redacted[key] = [_redact_tool_input(v) if isinstance(v, dict) else str(v)[:200] for v in value[:10]]
        else:
            redacted[key] = value
    return redacted


def _truncate_output(output) -> str:
    """Truncate tool output for storage."""
    if output is None:
        return ""
    text = str(output)
    # Strip base64 image data
    if "data:image" in text or len(text) > 1000 and text.startswith("data:"):
        return "[base64 data redacted]"
    if len(text) > 500:
        return text[:500] + "..."
    return text


@dataclass
class ObservabilityEvent:
    thread_id: str
    event_type: str
    run_id: str = ""
    name: str = ""
    parent_run_id: str = ""
    input_data: dict | str | None = None
    output: str = ""
    error: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0
    model: str = ""
    timestamp: float = field(default_factory=time.time)


class ObservabilityStore:
    """Redis-backed observability storage with SQLite + in-memory fallback."""

    def __init__(self) -> None:
        self._redis: Redis | None = None
        # In-memory fallback
        self._mem_events: dict[str, list[dict]] = {}
        self._mem_sessions: dict[str, dict] = {}
        self._mem_errors: dict[str, list[dict]] = {}

    async def _get_redis(self) -> Redis | None:
        if self._redis is None:
            try:
                self._redis = Redis.from_url(REDIS_URL, decode_responses=True)
                await self._redis.ping()
                logger.info("ObservabilityStore connected to Redis at %s", REDIS_URL)
            except (RedisError, RuntimeError) as exc:
                logger.warning("ObservabilityStore Redis unavailable — using in-memory fallback: %s", exc)
                self._redis = None
        return self._redis

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    async def start_session(
        self,
        thread_id: str,
        user_id: str,
        locale: str = "",
        timezone: str = "",
    ) -> None:
        """Record the start of a chat session."""
        user_hash = _hash_user_id(user_id)
        now = time.time()
        session_data = {
            "thread_id": thread_id,
            "user_hash": user_hash,
            "start_time": str(now),
            "end_time": "",
            "duration_seconds": "",
            "status": "running",
            "subagent_count": "0",
            "tool_call_count": "0",
            "total_tokens_in": "0",
            "total_tokens_out": "0",
            "total_cost_usd": "0.0",
            "model_used": "",
            "locale": locale,
            "timezone": timezone,
        }

        r = await self._get_redis()
        if r is not None:
            try:
                pipe = r.pipeline()
                pipe.hset(f"observability:session:{thread_id}", mapping=session_data)
                pipe.expire(f"observability:session:{thread_id}", _TTL_SECONDS)
                pipe.zadd("observability:sessions", {thread_id: now})
                pipe.expire("observability:sessions", _TTL_SECONDS)
                await pipe.execute()
                return
            except (RedisError, RuntimeError) as exc:
                logger.warning("ObservabilityStore start_session Redis error: %s", exc)

        # SQLite fallback
        db = await get_sqlite_connection()
        if db is not None:
            try:
                await db.execute(
                    "INSERT OR REPLACE INTO observability_sessions "
                    "(thread_id, user_hash, start_time, end_time, duration_seconds, status, "
                    "subagent_count, tool_call_count, total_tokens_in, total_tokens_out, "
                    "total_cost_usd, model_used, expires_at) "
                    "VALUES (?, ?, ?, NULL, NULL, 'running', 0, 0, 0, 0, 0.0, '', ?)",
                    (thread_id, user_hash, now, now + _TTL_SECONDS),
                )
                await db.commit()
                return
            except Exception as exc:  # noqa: BLE001
                logger.warning("ObservabilityStore start_session SQLite error: %s", exc)

        self._mem_sessions[thread_id] = {**session_data, "start_time": now}

    async def record_event(
        self,
        thread_id: str,
        event_type: str,
        run_id: str = "",
        name: str = "",
        parent_run_id: str = "",
        input_data: dict | str | None = None,
        output: str = "",
        error: str = "",
        tokens_in: int = 0,
        tokens_out: int = 0,
        cost_usd: float = 0.0,
        duration_ms: int = 0,
        model: str = "",
    ) -> None:
        """Record a single SSE event for a thread."""
        now = time.time()
        redacted_input = _redact_tool_input(input_data) if input_data else None
        truncated_output = _truncate_output(output) if output else ""
        event_record = {
            "thread_id": thread_id,
            "event_type": event_type,
            "run_id": run_id,
            "name": name,
            "parent_run_id": parent_run_id,
            "input": json.dumps(redacted_input) if redacted_input and isinstance(redacted_input, dict) else (str(redacted_input) if redacted_input else ""),
            "output": truncated_output,
            "error": error[:500] if error else "",
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cost_usd": cost_usd,
            "duration_ms": duration_ms,
            "model": model,
            "timestamp": now,
        }

        r = await self._get_redis()
        if r is not None:
            try:
                key = f"observability:events:{thread_id}"
                pipe = r.pipeline()
                pipe.rpush(key, json.dumps(event_record))
                pipe.expire(key, _TTL_SECONDS)
                # Track errors separately
                if event_type == "tool_error" and error:
                    pipe.zadd("observability:errors", {f"{thread_id}:{now}": now})
                    pipe.expire("observability:errors", _TTL_SECONDS)
                await pipe.execute()
                return
            except (RedisError, RuntimeError) as exc:
                logger.warning("ObservabilityStore record_event Redis error: %s", exc)

        # SQLite fallback
        db = await get_sqlite_connection()
        if db is not None:
            try:
                await db.execute(
                    "INSERT INTO observability_events "
                    "(thread_id, event_type, run_id, name, parent_run_id, input, output, error, "
                    "tokens_in, tokens_out, cost_usd, duration_ms, model, timestamp, expires_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        thread_id, event_type, run_id, name, parent_run_id,
                        event_record["input"], truncated_output, event_record["error"],
                        tokens_in, tokens_out, cost_usd, duration_ms, model, now,
                        now + _TTL_SECONDS,
                    ),
                )
                if event_type == "tool_error" and error:
                    await db.execute(
                        "INSERT INTO observability_errors "
                        "(thread_id, subagent_name, tool_name, error_message, timestamp, expires_at) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (thread_id, "", name, error[:500], now, now + _TTL_SECONDS),
                    )
                await db.commit()
                return
            except Exception as exc:  # noqa: BLE001
                logger.warning("ObservabilityStore record_event SQLite error: %s", exc)

        self._mem_events.setdefault(thread_id, []).append(event_record)
        if event_type == "tool_error" and error:
            self._mem_errors.setdefault(thread_id, []).append({
                "thread_id": thread_id,
                "subagent_name": "",
                "tool_name": name,
                "error_message": error[:500],
                "timestamp": now,
            })

    async def finalize_session(
        self,
        thread_id: str,
        status: str,
        subagent_count: int = 0,
        tool_call_count: int = 0,
        total_tokens_in: int = 0,
        total_tokens_out: int = 0,
        total_cost_usd: float = 0.0,
        model_used: str = "",
    ) -> None:
        """Finalize a session with end time and final status."""
        now = time.time()

        r = await self._get_redis()
        if r is not None:
            try:
                key = f"observability:session:{thread_id}"
                session = await r.hgetall(key)
                start_time = float(session.get("start_time", now)) if session else now
                duration = round(now - start_time, 2) if start_time else 0.0
                pipe = r.pipeline()
                pipe.hset(key, mapping={
                    "end_time": str(now),
                    "duration_seconds": str(duration),
                    "status": status,
                    "subagent_count": str(subagent_count),
                    "tool_call_count": str(tool_call_count),
                    "total_tokens_in": str(total_tokens_in),
                    "total_tokens_out": str(total_tokens_out),
                    "total_cost_usd": str(round(total_cost_usd, 6)),
                    "model_used": model_used,
                })
                pipe.expire(key, _TTL_SECONDS)
                await pipe.execute()
                return
            except (RedisError, RuntimeError) as exc:
                logger.warning("ObservabilityStore finalize_session Redis error: %s", exc)

        # SQLite fallback
        db = await get_sqlite_connection()
        if db is not None:
            try:
                cur = await db.execute(
                    "SELECT start_time FROM observability_sessions WHERE thread_id = ?",
                    (thread_id,),
                )
                row = await cur.fetchone()
                start_time = float(row["start_time"]) if row else now
                duration = round(now - start_time, 2)
                await db.execute(
                    "UPDATE observability_sessions SET "
                    "end_time = ?, duration_seconds = ?, status = ?, "
                    "subagent_count = ?, tool_call_count = ?, "
                    "total_tokens_in = ?, total_tokens_out = ?, "
                    "total_cost_usd = ?, model_used = ? "
                    "WHERE thread_id = ?",
                    (
                        now, duration, status,
                        subagent_count, tool_call_count,
                        total_tokens_in, total_tokens_out,
                        round(total_cost_usd, 6), model_used,
                        thread_id,
                    ),
                )
                await db.commit()
                return
            except Exception as exc:  # noqa: BLE001
                logger.warning("ObservabilityStore finalize_session SQLite error: %s", exc)

        if thread_id in self._mem_sessions:
            start = self._mem_sessions[thread_id].get("start_time", now)
            if isinstance(start, str):
                start = float(start)
            self._mem_sessions[thread_id].update({
                "end_time": str(now),
                "duration_seconds": str(round(now - start, 2)) if start else "0",
                "status": status,
                "subagent_count": str(subagent_count),
                "tool_call_count": str(tool_call_count),
                "total_tokens_in": str(total_tokens_in),
                "total_tokens_out": str(total_tokens_out),
                "total_cost_usd": str(round(total_cost_usd, 6)),
                "model_used": model_used,
            })

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------

    async def get_sessions(
        self,
        from_ts: float = 0,
        to_ts: float = 0,
        status: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """Get paginated list of sessions with filters.

        Returns {"sessions": [...], "total": int, "limit": int, "offset": int}.
        """
        if to_ts == 0:
            to_ts = time.time()

        r = await self._get_redis()
        if r is not None:
            try:
                all_thread_ids = await r.zrangebyscore(
                    "observability:sessions", from_ts, to_ts
                )
                total = len(all_thread_ids)

                # Apply status filter and paginate
                page_ids = all_thread_ids[offset:offset + limit]
                pipe = r.pipeline()
                for tid in page_ids:
                    pipe.hgetall(f"observability:session:{tid}")
                sessions_raw = await pipe.execute()

                sessions = []
                for tid, data in zip(page_ids, sessions_raw, strict=False):
                    if not data:
                        continue
                    if status and data.get("status", "") != status:
                        continue
                    sessions.append(self._normalize_session(tid, data))

                return {"sessions": sessions, "total": total, "limit": limit, "offset": offset}
            except (RedisError, RuntimeError) as exc:
                logger.warning("ObservabilityStore get_sessions Redis error: %s", exc)

        # SQLite fallback
        db = await get_sqlite_connection()
        if db is not None:
            try:
                where_clauses = ["start_time >= ?", "start_time <= ?"]
                params: list = [from_ts, to_ts]
                if status:
                    where_clauses.append("status = ?")
                    params.append(status)
                where_sql = " AND ".join(where_clauses)

                cur = await db.execute(
                    f"SELECT COUNT(*) FROM observability_sessions WHERE {where_sql}",
                    params,
                )
                row = await cur.fetchone()
                total = int(row[0]) if row else 0

                cur = await db.execute(
                    f"SELECT * FROM observability_sessions WHERE {where_sql} "
                    f"ORDER BY start_time DESC LIMIT ? OFFSET ?",
                    [*params, limit, offset],
                )
                rows = await cur.fetchall()
                sessions = [self._normalize_session_row(row) for row in rows]
                return {"sessions": sessions, "total": total, "limit": limit, "offset": offset}
            except Exception as exc:  # noqa: BLE001
                logger.warning("ObservabilityStore get_sessions SQLite error: %s", exc)

        # In-memory fallback
        all_sessions = []
        for tid, data in self._mem_sessions.items():
            start = float(data.get("start_time", 0))
            if start < from_ts or start > to_ts:
                continue
            if status and data.get("status", "") != status:
                continue
            all_sessions.append(self._normalize_session(tid, data))
        total = len(all_sessions)
        sessions = all_sessions[offset:offset + limit]
        return {"sessions": sessions, "total": total, "limit": limit, "offset": offset}

    def _normalize_session(self, thread_id: str, data: dict) -> dict:
        return {
            "thread_id": thread_id,
            "user_hash": data.get("user_hash", ""),
            "start_time": float(data.get("start_time", 0)),
            "end_time": float(data.get("end_time", 0)) if data.get("end_time") else None,
            "duration_seconds": float(data.get("duration_seconds", 0)) if data.get("duration_seconds") else None,
            "status": data.get("status", "unknown"),
            "subagent_count": int(data.get("subagent_count", 0)),
            "tool_call_count": int(data.get("tool_call_count", 0)),
            "total_tokens_in": int(data.get("total_tokens_in", 0)),
            "total_tokens_out": int(data.get("total_tokens_out", 0)),
            "total_cost_usd": float(data.get("total_cost_usd", 0.0)),
            "model_used": data.get("model_used", ""),
        }

    def _normalize_session_row(self, row) -> dict:
        return {
            "thread_id": row["thread_id"],
            "user_hash": row["user_hash"] or "",
            "start_time": float(row["start_time"] or 0),
            "end_time": float(row["end_time"]) if row["end_time"] else None,
            "duration_seconds": float(row["duration_seconds"]) if row["duration_seconds"] else None,
            "status": row["status"] or "unknown",
            "subagent_count": int(row["subagent_count"] or 0),
            "tool_call_count": int(row["tool_call_count"] or 0),
            "total_tokens_in": int(row["total_tokens_in"] or 0),
            "total_tokens_out": int(row["total_tokens_out"] or 0),
            "total_cost_usd": float(row["total_cost_usd"] or 0.0),
            "model_used": row["model_used"] or "",
        }

    async def get_session_events(self, thread_id: str) -> list[dict]:
        """Get ordered event list for a session (for waterfall rendering)."""
        r = await self._get_redis()
        if r is not None:
            try:
                raw = await r.lrange(f"observability:events:{thread_id}", 0, -1)
                events = []
                for item in raw:
                    try:
                        events.append(json.loads(item))
                    except (json.JSONDecodeError, TypeError):
                        continue
                return events
            except (RedisError, RuntimeError) as exc:
                logger.warning("ObservabilityStore get_session_events Redis error: %s", exc)

        # SQLite fallback
        db = await get_sqlite_connection()
        if db is not None:
            try:
                cur = await db.execute(
                    "SELECT * FROM observability_events WHERE thread_id = ? ORDER BY timestamp",
                    (thread_id,),
                )
                rows = await cur.fetchall()
                events = []
                for row in rows:
                    input_str = row["input"] or ""
                    try:
                        input_data = json.loads(input_str) if input_str else None
                    except (json.JSONDecodeError, TypeError):
                        input_data = input_str if input_str else None
                    events.append({
                        "thread_id": row["thread_id"],
                        "event_type": row["event_type"],
                        "run_id": row["run_id"] or "",
                        "name": row["name"] or "",
                        "parent_run_id": row["parent_run_id"] or "",
                        "input": input_data,
                        "output": row["output"] or "",
                        "error": row["error"] or "",
                        "tokens_in": int(row["tokens_in"] or 0),
                        "tokens_out": int(row["tokens_out"] or 0),
                        "cost_usd": float(row["cost_usd"] or 0.0),
                        "duration_ms": int(row["duration_ms"] or 0),
                        "model": row["model"] or "",
                        "timestamp": float(row["timestamp"] or 0),
                    })
                return events
            except Exception as exc:  # noqa: BLE001
                logger.warning("ObservabilityStore get_session_events SQLite error: %s", exc)

        return self._mem_events.get(thread_id, [])

    async def get_errors(
        self,
        from_ts: float = 0,
        to_ts: float = 0,
        subagent: str = "",
        tool: str = "",
        limit: int = 50,
    ) -> list[dict]:
        """Get error events with filters."""
        if to_ts == 0:
            to_ts = time.time()

        r = await self._get_redis()
        if r is not None:
            try:
                error_keys = await r.zrangebyscore("observability:errors", from_ts, to_ts)
                errors = []
                for key in error_keys:
                    parts = key.rsplit(":", 1)
                    if len(parts) < 2:
                        continue
                    tid, ts_str = parts
                    events = await r.lrange(f"observability:events:{tid}", 0, -1)
                    for item in events:
                        try:
                            evt = json.loads(item)
                        except (json.JSONDecodeError, TypeError):
                            continue
                        if evt.get("event_type") != "tool_error":
                            continue
                        if subagent and evt.get("name", "") != subagent:
                            continue
                        if tool and evt.get("name", "") != tool:
                            continue
                        errors.append({
                            "thread_id": tid,
                            "subagent_name": evt.get("name", ""),
                            "tool_name": evt.get("name", ""),
                            "error_message": evt.get("error", ""),
                            "timestamp": evt.get("timestamp", 0),
                        })
                        if len(errors) >= limit:
                            break
                    if len(errors) >= limit:
                        break
                return errors
            except (RedisError, RuntimeError) as exc:
                logger.warning("ObservabilityStore get_errors Redis error: %s", exc)

        # SQLite fallback
        db = await get_sqlite_connection()
        if db is not None:
            try:
                where_clauses = ["timestamp >= ?", "timestamp <= ?"]
                params: list = [from_ts, to_ts]
                if subagent:
                    where_clauses.append("subagent_name = ?")
                    params.append(subagent)
                if tool:
                    where_clauses.append("tool_name = ?")
                    params.append(tool)
                where_sql = " AND ".join(where_clauses)
                cur = await db.execute(
                    f"SELECT * FROM observability_errors WHERE {where_sql} "
                    f"ORDER BY timestamp DESC LIMIT ?",
                    [*params, limit],
                )
                rows = await cur.fetchall()
                return [
                    {
                        "thread_id": row["thread_id"],
                        "subagent_name": row["subagent_name"] or "",
                        "tool_name": row["tool_name"] or "",
                        "error_message": row["error_message"] or "",
                        "timestamp": float(row["timestamp"] or 0),
                    }
                    for row in rows
                ]
            except Exception as exc:  # noqa: BLE001
                logger.warning("ObservabilityStore get_errors SQLite error: %s", exc)

        # In-memory
        errors = []
        for tid, errs in self._mem_errors.items():
            for err in errs:
                ts = err.get("timestamp", 0)
                if ts < from_ts or ts > to_ts:
                    continue
                if subagent and err.get("subagent_name", "") != subagent:
                    continue
                if tool and err.get("tool_name", "") != tool:
                    continue
                errors.append({**err, "thread_id": tid})
                if len(errors) >= limit:
                    break
        return errors

    async def get_error_summary(
        self,
        from_ts: float = 0,
        to_ts: float = 0,
    ) -> dict:
        """Get error counts grouped by subagent+tool, plus error rate trend.

        Returns {
            "total_errors": int,
            "by_subagent": [{"name": str, "count": int}, ...],
            "by_tool": [{"name": str, "count": int}, ...],
            "per_day": [{"date": str, "count": int}, ...],
        }
        """
        if to_ts == 0:
            to_ts = time.time()

        errors = await self.get_errors(from_ts, to_ts, limit=10000)

        total = len(errors)
        by_subagent: dict[str, int] = {}
        by_tool: dict[str, int] = {}
        per_day: dict[str, int] = {}

        for err in errors:
            sa = err.get("subagent_name", "") or err.get("tool_name", "") or "unknown"
            tool_name = err.get("tool_name", "") or "unknown"
            by_subagent[sa] = by_subagent.get(sa, 0) + 1
            by_tool[tool_name] = by_tool.get(tool_name, 0) + 1
            day = time.strftime("%Y-%m-%d", time.gmtime(err.get("timestamp", 0)))
            per_day[day] = per_day.get(day, 0) + 1

        return {
            "total_errors": total,
            "by_subagent": [
                {"name": k, "count": v}
                for k, v in sorted(by_subagent.items(), key=lambda x: x[1], reverse=True)
            ],
            "by_tool": [
                {"name": k, "count": v}
                for k, v in sorted(by_tool.items(), key=lambda x: x[1], reverse=True)
            ],
            "per_day": [
                {"date": d, "count": c}
                for d, c in sorted(per_day.items())
            ],
        }

    async def get_usage(
        self,
        from_ts: float = 0,
        to_ts: float = 0,
    ) -> dict:
        """Get aggregated token/cost usage per day, per subagent, per user.

        Returns {
            "per_day": [{"date": str, "tokens_in": int, "tokens_out": int, "cost": float, "sessions": int}, ...],
            "per_subagent": [{"name": str, "tokens_in": int, "tokens_out": int, "cost": float}, ...],
            "per_user": [{"user_hash": str, "sessions": int, "cost": float}, ...],
            "totals": {"tokens_in": int, "tokens_out": int, "cost": float, "sessions": int},
        }
        """
        if to_ts == 0:
            to_ts = time.time()

        sessions_data = await self.get_sessions(from_ts, to_ts, limit=10000)
        sessions = sessions_data["sessions"]

        per_day: dict[str, dict] = {}
        per_user: dict[str, dict] = {}
        total_in = 0
        total_out = 0
        total_cost = 0.0
        total_sessions = len(sessions)

        for s in sessions:
            day = time.strftime("%Y-%m-%d", time.gmtime(s["start_time"]))
            bucket = per_day.setdefault(day, {"date": day, "tokens_in": 0, "tokens_out": 0, "cost": 0.0, "sessions": 0})
            bucket["tokens_in"] += s["total_tokens_in"]
            bucket["tokens_out"] += s["total_tokens_out"]
            bucket["cost"] += s["total_cost_usd"]
            bucket["sessions"] += 1
            total_in += s["total_tokens_in"]
            total_out += s["total_tokens_out"]
            total_cost += s["total_cost_usd"]

            uh = s["user_hash"]
            ub = per_user.setdefault(uh, {"user_hash": uh, "sessions": 0, "cost": 0.0})
            ub["sessions"] += 1
            ub["cost"] += s["total_cost_usd"]

        # Per-subagent: aggregate from events
        per_subagent: dict[str, dict] = {}
        for s in sessions:
            events = await self.get_session_events(s["thread_id"])
            for evt in events:
                if evt.get("event_type") != "on_chat_model_end":
                    continue
                name = evt.get("name", "orchestrator") or "orchestrator"
                sa = per_subagent.setdefault(name, {"name": name, "tokens_in": 0, "tokens_out": 0, "cost": 0.0})
                sa["tokens_in"] += evt.get("tokens_in", 0)
                sa["tokens_out"] += evt.get("tokens_out", 0)
                sa["cost"] += evt.get("cost_usd", 0.0)

        return {
            "per_day": sorted(per_day.values(), key=lambda x: x["date"]),
            "per_subagent": sorted(per_subagent.values(), key=lambda x: x["cost"], reverse=True),
            "per_user": sorted(per_user.values(), key=lambda x: x["cost"], reverse=True)[:20],
            "totals": {
                "tokens_in": total_in,
                "tokens_out": total_out,
                "cost": round(total_cost, 6),
                "sessions": total_sessions,
            },
        }

    async def cleanup_expired(self) -> int:
        """Clean up expired observability data. Returns count of items removed."""
        cleaned = 0
        r = await self._get_redis()
        if r is not None:
            try:
                # Get all session IDs
                thread_ids = await r.zrange("observability:sessions", 0, -1)
                for tid in thread_ids:
                    exists = await r.exists(f"observability:session:{tid}")
                    if not exists:
                        pipe = r.pipeline()
                        pipe.zrem("observability:sessions", tid)
                        pipe.delete(f"observability:events:{tid}")
                        pipe.delete(f"observability:session:{tid}")
                        await pipe.execute()
                        cleaned += 1
            except (RedisError, RuntimeError) as exc:
                logger.warning("ObservabilityStore cleanup_expired error: %s", exc)

        # SQLite cleanup
        db = await get_sqlite_connection()
        if db is not None:
            try:
                now = time.time()
                for table in ("observability_events", "observability_errors", "observability_sessions"):
                    cur = await db.execute(f"DELETE FROM {table} WHERE expires_at < ?", (now,))
                    cleaned += cur.rowcount
                await db.commit()
            except Exception as exc:  # noqa: BLE001
                logger.warning("ObservabilityStore SQLite cleanup error: %s", exc)

        return cleaned


# Module-level singleton (same pattern as cost_store, feedback_store)
observability_store = ObservabilityStore()
