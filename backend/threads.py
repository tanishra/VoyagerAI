"""Thread metadata store — a lightweight index of conversation threads per user.

The langgraph checkpointer stores full agent state per thread_id but has no
"list threads by user" API. This module maintains a simple Redis-backed index
mapping user_id → [{thread_id, summary, created_at, updated_at}] so the
frontend can list, resume, and delete past conversations.

Falls back to an in-memory dict when Redis is unavailable (same graceful
degradation pattern as cache.py).
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass

from redis.asyncio import Redis
from redis.exceptions import RedisError

from config import REDIS_URL

logger = logging.getLogger("travel_agent.threads")


@dataclass
class ThreadMeta:
    thread_id: str
    summary: str
    created_at: float
    updated_at: float


def _user_tag(user_id: str) -> str:
    """Hash the user_id to a 12-char tag (same scheme as _scoped_chat_thread_id)."""
    return hashlib.sha256(user_id.encode()).hexdigest()[:12]


class ThreadStore:
    """Redis-backed thread metadata index with in-memory fallback."""

    def __init__(self) -> None:
        self._redis: Redis | None = None
        self._mem: dict[str, dict[str, ThreadMeta]] = {}

    async def _get_redis(self) -> Redis | None:
        if self._redis is None:
            try:
                self._redis = Redis.from_url(REDIS_URL, decode_responses=True)
                await self._redis.ping()
                logger.info("ThreadStore connected to Redis at %s", REDIS_URL)
            except (RedisError, RuntimeError) as exc:
                logger.warning("ThreadStore Redis unavailable — using in-memory fallback: %s", exc)
                self._redis = None
        return self._redis

    async def list_threads(self, user_id: str, limit: int = 20) -> list[ThreadMeta]:
        """Return the user's most recent threads, sorted by updated_at descending."""
        tag = _user_tag(user_id)
        r = await self._get_redis()
        if r is not None:
            try:
                # Get thread IDs from the sorted set (highest score = most recent first)
                thread_ids = await r.zrevrange(f"threads:{tag}", 0, limit - 1)
                if not thread_ids:
                    return []
                pipe = r.pipeline()
                for tid in thread_ids:
                    pipe.hgetall(f"threads:{tag}:{tid}")
                results = await pipe.execute()
                threads = []
                for tid, data in zip(thread_ids, results, strict=False):
                    if data:
                        threads.append(ThreadMeta(
                            thread_id=data.get("thread_id", tid),
                            summary=data.get("summary", ""),
                            created_at=float(data.get("created_at", 0)),
                            updated_at=float(data.get("updated_at", 0)),
                        ))
                return threads
            except (RedisError, RuntimeError) as exc:
                logger.warning("ThreadStore list_threads Redis error — falling back: %s", exc)

        # In-memory fallback
        user_threads = self._mem.get(user_id, {})
        sorted_threads = sorted(user_threads.values(), key=lambda t: t.updated_at, reverse=True)
        return sorted_threads[:limit]

    async def upsert_thread(self, user_id: str, thread_id: str, summary: str) -> None:
        """Insert or update a thread's metadata. Updates summary and updated_at."""
        tag = _user_tag(user_id)
        now = time.time()
        r = await self._get_redis()
        if r is not None:
            try:
                key = f"threads:{tag}:{thread_id}"
                existing = await r.hgetall(key)
                created_at = float(existing.get("created_at", now)) if existing else now
                pipe = r.pipeline()
                pipe.hset(key, mapping={
                    "thread_id": thread_id,
                    "summary": summary[:100],
                    "created_at": str(created_at),
                    "updated_at": str(now),
                })
                pipe.zadd(f"threads:{tag}", {thread_id: now})
                await pipe.execute()
                return
            except (RedisError, RuntimeError) as exc:
                logger.warning("ThreadStore upsert_thread Redis error — falling back: %s", exc)

        # In-memory fallback
        user_threads = self._mem.setdefault(user_id, {})
        existing = user_threads.get(thread_id)
        created_at = existing.created_at if existing else now
        user_threads[thread_id] = ThreadMeta(
            thread_id=thread_id,
            summary=summary[:100],
            created_at=created_at,
            updated_at=now,
        )

    async def delete_thread(self, user_id: str, thread_id: str) -> bool:
        """Remove a thread from the metadata index. Returns True if it existed."""
        tag = _user_tag(user_id)
        r = await self._get_redis()
        if r is not None:
            try:
                key = f"threads:{tag}:{thread_id}"
                deleted = await r.delete(key)
                await r.zrem(f"threads:{tag}", thread_id)
                return deleted > 0
            except (RedisError, RuntimeError) as exc:
                logger.warning("ThreadStore delete_thread Redis error — falling back: %s", exc)

        # In-memory fallback
        user_threads = self._mem.get(user_id, {})
        if thread_id in user_threads:
            del user_threads[thread_id]
            return True
        return False

    async def get_thread(self, user_id: str, thread_id: str) -> ThreadMeta | None:
        """Get a single thread's metadata, or None if not found."""
        tag = _user_tag(user_id)
        r = await self._get_redis()
        if r is not None:
            try:
                data = await r.hgetall(f"threads:{tag}:{thread_id}")
                if not data:
                    return None
                return ThreadMeta(
                    thread_id=data.get("thread_id", thread_id),
                    summary=data.get("summary", ""),
                    created_at=float(data.get("created_at", 0)),
                    updated_at=float(data.get("updated_at", 0)),
                )
            except (RedisError, RuntimeError) as exc:
                logger.warning("ThreadStore get_thread Redis error — falling back: %s", exc)

        # In-memory fallback
        user_threads = self._mem.get(user_id, {})
        return user_threads.get(thread_id)


thread_store = ThreadStore()
