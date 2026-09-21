"""Feedback store — Redis-backed with in-memory fallback.

Stores per-user, per-message feedback ratings (thumbs up/down).
Follows the same graceful degradation pattern as cost_store.py and threads.py.

Redis key layout:
  feedback:{user_id}:{message_id}   — hash: rating, comment, thread_id, created_at, updated_at
  feedback:index                     — sorted set: "{user_id}:{message_id}" → timestamp (for aggregation)
  feedback:thread:{thread_id}        — set: all "{user_id}:{message_id}" keys with feedback in this thread
"""

from __future__ import annotations

import json
import logging
import time

from redis.asyncio import Redis
from redis.exceptions import RedisError

from config import REDIS_URL, settings
from sqlite_fallback import get_sqlite_connection

logger = logging.getLogger("travel_agent.feedback_store")

_TTL_SECONDS: int = settings.THREAD_TTL_DAYS * 86_400


class FeedbackStore:
    """Redis-backed feedback storage with SQLite + in-memory fallback."""

    def __init__(self) -> None:
        self._redis: Redis | None = None
        self._mem_feedback: dict[str, dict] = {}

    def _prune_mem(self) -> None:
        """Drop expired in-memory feedback (same TTL as Redis/SQLite)."""
        cutoff = time.time() - _TTL_SECONDS
        for k in [k for k, v in self._mem_feedback.items() if float(v.get("updated_at", 0)) <= cutoff]:
            del self._mem_feedback[k]

    async def _get_redis(self) -> Redis | None:
        if self._redis is None:
            try:
                self._redis = Redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)
                await self._redis.ping()
                logger.info("FeedbackStore connected to Redis at %s", REDIS_URL)
            except (RedisError, RuntimeError) as exc:
                logger.warning("FeedbackStore Redis unavailable — using in-memory fallback: %s", exc)
                self._redis = None
        return self._redis

    async def submit_feedback(
        self,
        user_id: str,
        message_id: str,
        thread_id: str,
        rating: str,
        comment: str | None = None,
    ) -> dict:
        """Submit or update feedback for a message. Overwrites existing (mutable)."""
        now = time.time()
        key = f"{user_id}:{message_id}"
        redis_key = f"feedback:{key}"

        data = {
            "user_id": user_id,
            "message_id": message_id,
            "thread_id": thread_id,
            "rating": rating,
            "comment": comment or "",
            "created_at": str(now),
            "updated_at": str(now),
        }

        persisted = False

        r = await self._get_redis()
        if r is not None:
            try:
                pipe = r.pipeline()
                pipe.hset(redis_key, mapping=data)
                pipe.expire(redis_key, _TTL_SECONDS)
                pipe.zadd("feedback:index", {key: now})
                pipe.expire("feedback:index", _TTL_SECONDS)
                pipe.sadd(f"feedback:thread:{thread_id}", key)
                pipe.expire(f"feedback:thread:{thread_id}", _TTL_SECONDS)
                await pipe.execute()
                persisted = True
            except (RedisError, RuntimeError) as exc:
                logger.warning("FeedbackStore submit_feedback Redis error: %s", exc)

        # SQLite write-through (durable copy alongside Redis)
        db = await get_sqlite_connection()
        if db is not None:
            try:
                await db.execute(
                    "INSERT OR REPLACE INTO feedback (key, user_id, message_id, thread_id, rating, comment, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (key, user_id, message_id, thread_id, rating, comment or "", now, now),
                )
                await db.commit()
                persisted = True
            except Exception as exc:  # noqa: BLE001
                logger.warning("FeedbackStore submit_feedback SQLite error: %s", exc)

        if not persisted:
            self._prune_mem()
            self._mem_feedback[key] = data
        return {"status": "ok", "rating": rating}

    async def get_feedback(self, user_id: str, message_id: str) -> dict | None:
        """Get a single user's feedback for a specific message."""
        key = f"{user_id}:{message_id}"
        r = await self._get_redis()
        if r is not None:
            try:
                data = await r.hgetall(f"feedback:{key}")
                if data:
                    return {
                        "user_id": data.get("user_id", user_id),
                        "message_id": data.get("message_id", message_id),
                        "thread_id": data.get("thread_id", ""),
                        "rating": data.get("rating", ""),
                        "comment": data.get("comment", ""),
                        "created_at": float(data.get("created_at", 0)),
                        "updated_at": float(data.get("updated_at", 0)),
                    }
            except (RedisError, RuntimeError) as exc:
                logger.warning("FeedbackStore get_feedback Redis error: %s", exc)

        # SQLite — checked even when Redis is up but has no copy
        db = await get_sqlite_connection()
        if db is not None:
            try:
                cur = await db.execute(
                    "SELECT * FROM feedback WHERE key = ?", (key,)
                )
                row = await cur.fetchone()
                if row:
                    return {
                        "user_id": row["user_id"] or user_id,
                        "message_id": row["message_id"] or message_id,
                        "thread_id": row["thread_id"] or "",
                        "rating": row["rating"] or "",
                        "comment": row["comment"] or "",
                        "created_at": float(row["created_at"] or 0),
                        "updated_at": float(row["updated_at"] or 0),
                    }
            except Exception as exc:  # noqa: BLE001
                logger.warning("FeedbackStore get_feedback SQLite error: %s", exc)

        mem = self._mem_feedback.get(key)
        if mem is None:
            return None
        if float(mem.get("updated_at", 0)) <= time.time() - _TTL_SECONDS:
            del self._mem_feedback[key]
            return None
        return {
            "user_id": mem.get("user_id", user_id),
            "message_id": mem.get("message_id", message_id),
            "thread_id": mem.get("thread_id", ""),
            "rating": mem.get("rating", ""),
            "comment": mem.get("comment", ""),
            "created_at": float(mem.get("created_at", 0)),
            "updated_at": float(mem.get("updated_at", 0)),
        }

    async def get_aggregate_stats(self) -> dict:
        """Get aggregate feedback stats for admin observability.

        Returns:
            Dict with total_up, total_down, total_ratings, satisfaction_ratio,
            recent_comments (last 20 thumbs-down with non-empty comments).
        """
        merged: dict[str, dict] = {}

        def _merge(k: str, data: dict) -> None:
            cur = merged.get(k)
            if cur is None or float(data.get("updated_at", 0)) >= float(cur.get("updated_at", 0)):
                merged[k] = data

        r = await self._get_redis()
        if r is not None:
            try:
                keys = await r.zrange("feedback:index", 0, -1)
                if keys:
                    pipe = r.pipeline()
                    for k in keys:
                        pipe.hgetall(f"feedback:{k}")
                    results = await pipe.execute()
                    for k, data in zip(keys, results, strict=False):
                        if data:
                            _merge(k, dict(data))
            except (RedisError, RuntimeError) as exc:
                logger.warning("FeedbackStore get_aggregate_stats Redis error: %s", exc)

        db = await get_sqlite_connection()
        if db is not None:
            try:
                cur = await db.execute("SELECT * FROM feedback")
                for row in await cur.fetchall():
                    _merge(row["key"], {
                        "user_id": row["user_id"] or "",
                        "message_id": row["message_id"] or "",
                        "thread_id": row["thread_id"] or "",
                        "rating": row["rating"] or "",
                        "comment": row["comment"] or "",
                        "created_at": str(row["created_at"] or 0),
                        "updated_at": str(row["updated_at"] or 0),
                    })
            except Exception as exc:  # noqa: BLE001
                logger.warning("FeedbackStore get_aggregate_stats SQLite error: %s", exc)

        self._prune_mem()
        for k, v in self._mem_feedback.items():
            _merge(k, v)

        keys = list(merged.keys())
        return self._compute_stats(keys, [merged[k] for k in keys])

    def _empty_stats(self) -> dict:
        return {
            "total_up": 0,
            "total_down": 0,
            "total_ratings": 0,
            "satisfaction_ratio": 0.0,
            "recent_comments": [],
        }

    def _compute_stats(self, keys: list[str], results: list[dict]) -> dict:
        total_up = 0
        total_down = 0
        comments: list[dict] = []

        for _key, data in zip(keys, results, strict=False):
            if not data:
                continue
            rating = data.get("rating", "")
            if rating == "up":
                total_up += 1
            elif rating == "down":
                total_down += 1
                comment = data.get("comment", "")
                if comment:
                    comments.append({
                        "comment": comment,
                        "thread_id": data.get("thread_id", ""),
                        "created_at": float(data.get("updated_at", data.get("created_at", 0))),
                    })

        total = total_up + total_down
        ratio = round(total_up / total, 4) if total > 0 else 0.0

        comments.sort(key=lambda x: x["created_at"], reverse=True)

        return {
            "total_up": total_up,
            "total_down": total_down,
            "total_ratings": total,
            "satisfaction_ratio": ratio,
            "recent_comments": comments[:20],
        }


feedback_store = FeedbackStore()
