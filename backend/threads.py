"""Thread metadata store — a lightweight index of conversation threads per user.

The langgraph checkpointer stores full agent state per thread_id but has no
"list threads by user" API. This module maintains a simple Redis-backed index
mapping user_id → [{thread_id, summary, created_at, updated_at, status, message_count}]
so the frontend can list, resume, and delete past conversations.

Includes:
- Cursor-based pagination (offset + limit)
- Thread status tracking (idle, busy, error)
- Message count per thread
- TTL-based automatic expiration (Redis key EXPIRE)
- AI-generated summaries (via generate_summary helper)
- Cleanup of expired thread metadata

Falls back to SQLite (persistent) then in-memory when Redis is unavailable.
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass

from redis.asyncio import Redis
from redis.exceptions import RedisError

from config import REDIS_URL, settings
from sqlite_fallback import get_sqlite_connection

logger = logging.getLogger("travel_agent.threads")

_TTL_SECONDS: int = settings.THREAD_TTL_DAYS * 86_400


@dataclass
class ThreadMeta:
    thread_id: str
    summary: str
    created_at: float
    updated_at: float
    status: str = "idle"
    message_count: int = 0
    search_text: str = ""
    pinned: bool = False
    pinned_at: float = 0.0


def _user_tag(user_id: str) -> str:
    """Hash the user_id to a 12-char tag (same scheme as _scoped_chat_thread_id)."""
    return hashlib.sha256(user_id.encode()).hexdigest()[:12]


class ThreadStore:
    """Redis-backed thread metadata index with SQLite + in-memory fallback."""

    def __init__(self) -> None:
        self._redis: Redis | None = None
        self._mem: dict[str, dict[str, ThreadMeta]] = {}

    async def _get_redis(self) -> Redis | None:
        if self._redis is None:
            try:
                self._redis = Redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)
                await self._redis.ping()
                logger.info("ThreadStore connected to Redis at %s", REDIS_URL)
            except (RedisError, RuntimeError) as exc:
                logger.warning("ThreadStore Redis unavailable — using in-memory fallback: %s", exc)
                self._redis = None
        return self._redis

    # -----------------------------------------------------------------
    # Store-level helpers — every read consults ALL stores and merges,
    # every write/delete hits ALL stores. A Redis blip can never hide
    # data that landed in SQLite or memory while Redis was down.
    # -----------------------------------------------------------------

    async def _redis_threads(self, tag: str) -> dict[str, ThreadMeta] | None:
        """All thread metas from Redis, keyed by thread_id. None if unavailable."""
        r = await self._get_redis()
        if r is None:
            return None
        try:
            thread_ids = await r.zrange(f"threads:{tag}", 0, -1)
            if not thread_ids:
                return {}
            pipe = r.pipeline()
            for tid in thread_ids:
                pipe.hgetall(f"threads:{tag}:{tid}")
            results = await pipe.execute()
            out: dict[str, ThreadMeta] = {}
            for tid, data in zip(thread_ids, results, strict=False):
                if data:
                    out[tid] = ThreadMeta(
                        thread_id=data.get("thread_id", tid),
                        summary=data.get("summary", ""),
                        created_at=float(data.get("created_at", 0)),
                        updated_at=float(data.get("updated_at", 0)),
                        status=data.get("status", "idle"),
                        message_count=int(data.get("message_count", 0)),
                        search_text=data.get("search_text", ""),
                        pinned=data.get("pinned", "0") == "1",
                        pinned_at=float(data.get("pinned_at", 0)),
                    )
            return out
        except (RedisError, RuntimeError) as exc:
            logger.warning("ThreadStore Redis read error: %s", exc)
            return None

    async def _sqlite_threads(self, tag: str) -> dict[str, ThreadMeta] | None:
        """All thread metas from SQLite, keyed by thread_id. None if unavailable."""
        db = await get_sqlite_connection()
        if db is None:
            return None
        try:
            cur = await db.execute(
                "SELECT * FROM threads WHERE user_tag = ?", (tag,)
            )
            rows = await cur.fetchall()
            return {
                row["thread_id"]: ThreadMeta(
                    thread_id=row["thread_id"],
                    summary=row["summary"] or "",
                    created_at=float(row["created_at"] or 0),
                    updated_at=float(row["updated_at"] or 0),
                    status=row["status"] or "idle",
                    message_count=int(row["message_count"] or 0),
                    search_text=row["search_text"] or "",
                    pinned=bool(row["pinned"]),
                    pinned_at=float(row["pinned_at"] or 0),
                )
                for row in rows
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("ThreadStore SQLite read error: %s", exc)
            return None

    async def _all_threads(self, user_id: str, tag: str) -> dict[str, ThreadMeta]:
        """Merge thread metas from all stores; freshest copy (max updated_at) wins."""
        merged: dict[str, ThreadMeta] = {}

        def _merge(src: dict[str, ThreadMeta] | None) -> None:
            if not src:
                return
            for tid, meta in src.items():
                cur = merged.get(tid)
                if cur is None or meta.updated_at >= cur.updated_at:
                    merged[tid] = meta

        _merge(await self._redis_threads(tag))
        _merge(await self._sqlite_threads(tag))
        _merge(self._mem.get(user_id, {}))
        return merged

    @staticmethod
    def _sort_threads(threads: list[ThreadMeta]) -> list[ThreadMeta]:
        """Pinned first (by pinned_at desc), then unpinned (by updated_at desc)."""
        threads.sort(key=lambda t: (
            not t.pinned,
            -t.pinned_at if t.pinned else -t.updated_at,
        ))
        return threads

    async def _redis_get_thread(self, tag: str, thread_id: str) -> dict | None:
        """Raw hash for one thread from Redis. None on miss or error."""
        r = await self._get_redis()
        if r is None:
            return None
        try:
            data = await r.hgetall(f"threads:{tag}:{thread_id}")
            return data or None
        except (RedisError, RuntimeError) as exc:
            logger.warning("ThreadStore Redis get error: %s", exc)
            return None

    async def _sqlite_get_thread(self, tag: str, thread_id: str) -> dict | None:
        """Raw row for one thread from SQLite. None on miss or error."""
        db = await get_sqlite_connection()
        if db is None:
            return None
        try:
            cur = await db.execute(
                "SELECT * FROM threads WHERE thread_id = ? AND user_tag = ?",
                (thread_id, tag),
            )
            row = await cur.fetchone()
            return dict(row) if row else None
        except Exception as exc:  # noqa: BLE001
            logger.warning("ThreadStore SQLite get error: %s", exc)
            return None

    async def _existing_meta(self, user_id: str, tag: str, thread_id: str) -> ThreadMeta | None:
        """Find the freshest existing meta for a thread across all stores."""
        data = await self._redis_get_thread(tag, thread_id)
        if data:
            return ThreadMeta(
                thread_id=data.get("thread_id", thread_id),
                summary=data.get("summary", ""),
                created_at=float(data.get("created_at", 0)),
                updated_at=float(data.get("updated_at", 0)),
                status=data.get("status", "idle"),
                message_count=int(data.get("message_count", 0)),
                search_text=data.get("search_text", ""),
                pinned=data.get("pinned", "0") == "1",
                pinned_at=float(data.get("pinned_at", 0)),
            )
        row = await self._sqlite_get_thread(tag, thread_id)
        if row:
            return ThreadMeta(
                thread_id=row["thread_id"],
                summary=row["summary"] or "",
                created_at=float(row["created_at"] or 0),
                updated_at=float(row["updated_at"] or 0),
                status=row["status"] or "idle",
                message_count=int(row["message_count"] or 0),
                search_text=row["search_text"] or "",
                pinned=bool(row["pinned"]),
                pinned_at=float(row["pinned_at"] or 0),
            )
        return self._mem.get(user_id, {}).get(thread_id)

    async def list_threads(
        self, user_id: str, limit: int = 20, offset: int = 0
    ) -> list[ThreadMeta]:
        """Return the user's threads, pinned first (by pinned_at desc), then by updated_at desc, with pagination."""
        tag = _user_tag(user_id)
        merged = await self._all_threads(user_id, tag)
        threads = self._sort_threads(list(merged.values()))
        return threads[offset : offset + limit]

    async def upsert_thread(
        self,
        user_id: str,
        thread_id: str,
        summary: str,
        status: str = "idle",
        message_count: int = 0,
        search_text: str = "",
    ) -> None:
        """Insert or update a thread's metadata. Updates summary, status, and updated_at."""
        tag = _user_tag(user_id)
        now = time.time()

        # Merge with the freshest existing copy found in ANY store
        existing = await self._existing_meta(user_id, tag, thread_id)
        created_at = existing.created_at if existing else now
        prev_count = existing.message_count if existing else 0
        prev_search = existing.search_text if existing else ""
        prev_pinned = existing.pinned if existing else False
        prev_pinned_at = existing.pinned_at if existing else 0.0
        count = message_count if message_count > 0 else prev_count
        final_search = search_text if search_text else prev_search
        persisted = False

        r = await self._get_redis()
        if r is not None:
            try:
                key = f"threads:{tag}:{thread_id}"
                pipe = r.pipeline()
                pipe.hset(key, mapping={
                    "thread_id": thread_id,
                    "summary": summary[:50],
                    "created_at": str(created_at),
                    "updated_at": str(now),
                    "status": status,
                    "message_count": str(count),
                    "search_text": final_search[:1000],
                    "pinned": "1" if prev_pinned else "0",
                    "pinned_at": str(prev_pinned_at),
                })
                pipe.zadd(f"threads:{tag}", {thread_id: now})
                pipe.expire(key, _TTL_SECONDS)
                await pipe.execute()
                persisted = True
            except (RedisError, RuntimeError) as exc:
                logger.warning("ThreadStore upsert_thread Redis error: %s", exc)

        # SQLite write-through (durable copy alongside Redis)
        db = await get_sqlite_connection()
        if db is not None:
            try:
                await db.execute(
                    "INSERT OR REPLACE INTO threads (thread_id, user_tag, summary, created_at, updated_at, status, message_count, search_text, pinned, pinned_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (thread_id, tag, summary[:50], created_at, now, status, count, final_search[:1000], 1 if prev_pinned else 0, prev_pinned_at),
                )
                await db.commit()
                persisted = True
            except Exception as exc:  # noqa: BLE001
                logger.warning("ThreadStore upsert_thread SQLite error: %s", exc)

        if not persisted:
            # In-memory last resort
            user_threads = self._mem.setdefault(user_id, {})
            user_threads[thread_id] = ThreadMeta(
                thread_id=thread_id,
                summary=summary[:50],
                created_at=created_at,
                updated_at=now,
                status=status,
                message_count=count,
                search_text=final_search[:1000],
                pinned=prev_pinned,
                pinned_at=prev_pinned_at,
            )

    async def delete_thread(self, user_id: str, thread_id: str) -> bool:
        """Remove a thread from ALL stores. Returns True if it existed anywhere."""
        tag = _user_tag(user_id)
        existed = False

        r = await self._get_redis()
        if r is not None:
            try:
                key = f"threads:{tag}:{thread_id}"
                deleted = await r.delete(key)
                await r.zrem(f"threads:{tag}", thread_id)
                existed = deleted > 0
            except (RedisError, RuntimeError) as exc:
                logger.warning("ThreadStore delete_thread Redis error: %s", exc)

        db = await get_sqlite_connection()
        if db is not None:
            try:
                cur = await db.execute(
                    "DELETE FROM threads WHERE thread_id = ? AND user_tag = ?", (thread_id, tag)
                )
                await db.commit()
                existed = existed or cur.rowcount > 0
            except Exception as exc:  # noqa: BLE001
                logger.warning("ThreadStore delete_thread SQLite error: %s", exc)

        user_threads = self._mem.get(user_id, {})
        if thread_id in user_threads:
            del user_threads[thread_id]
            existed = True

        return existed

    async def get_thread(self, user_id: str, thread_id: str) -> ThreadMeta | None:
        """Get a single thread's metadata, or None if not found in any store."""
        tag = _user_tag(user_id)
        return await self._existing_meta(user_id, tag, thread_id)

    async def update_status(self, user_id: str, thread_id: str, status: str) -> None:
        """Update only the status field of a thread (e.g., busy → idle) in every store."""
        tag = _user_tag(user_id)

        r = await self._get_redis()
        if r is not None:
            try:
                key = f"threads:{tag}:{thread_id}"
                if await r.exists(key):
                    pipe = r.pipeline()
                    pipe.hset(key, "status", status)
                    pipe.expire(key, _TTL_SECONDS)
                    await pipe.execute()
            except (RedisError, RuntimeError) as exc:
                logger.warning("ThreadStore update_status Redis error: %s", exc)

        db = await get_sqlite_connection()
        if db is not None:
            try:
                await db.execute(
                    "UPDATE threads SET status = ? WHERE thread_id = ? AND user_tag = ?",
                    (status, thread_id, tag),
                )
                await db.commit()
            except Exception as exc:  # noqa: BLE001
                logger.warning("ThreadStore update_status SQLite error: %s", exc)

        user_threads = self._mem.get(user_id, {})
        if thread_id in user_threads:
            user_threads[thread_id].status = status

    async def update_pin_status(
        self, user_id: str, thread_id: str, pinned: bool
    ) -> bool:
        """Set or clear the pinned status of a thread in every store. Returns True if thread exists."""
        tag = _user_tag(user_id)
        now = time.time()
        existed = False

        r = await self._get_redis()
        if r is not None:
            try:
                key = f"threads:{tag}:{thread_id}"
                if await r.exists(key):
                    pipe = r.pipeline()
                    pipe.hset(key, mapping={
                        "pinned": "1" if pinned else "0",
                        "pinned_at": str(now) if pinned else "0",
                    })
                    pipe.expire(key, _TTL_SECONDS)
                    await pipe.execute()
                    existed = True
            except (RedisError, RuntimeError) as exc:
                logger.warning("ThreadStore update_pin_status Redis error: %s", exc)

        db = await get_sqlite_connection()
        if db is not None:
            try:
                cur = await db.execute(
                    "UPDATE threads SET pinned = ?, pinned_at = ? WHERE thread_id = ? AND user_tag = ?",
                    (1 if pinned else 0, now if pinned else 0.0, thread_id, tag),
                )
                await db.commit()
                existed = existed or cur.rowcount > 0
            except Exception as exc:  # noqa: BLE001
                logger.warning("ThreadStore update_pin_status SQLite error: %s", exc)

        user_threads = self._mem.get(user_id, {})
        if thread_id in user_threads:
            user_threads[thread_id].pinned = pinned
            user_threads[thread_id].pinned_at = now if pinned else 0.0
            existed = True

        return existed

    async def count_threads(self, user_id: str) -> int:
        """Return the total number of threads for a user across all stores."""
        tag = _user_tag(user_id)
        merged = await self._all_threads(user_id, tag)
        return len(merged)

    async def search_threads(
        self, user_id: str, query: str, limit: int = 20, offset: int = 0
    ) -> tuple[list[dict], int]:
        """Search across all user's thread messages for a keyword.

        Returns (results, total) where each result is:
        { thread_id, summary, snippet, updated_at, message_count }
        """
        tag = _user_tag(user_id)
        query_lower = query.lower()
        merged = await self._all_threads(user_id, tag)

        matches = []
        for meta in merged.values():
            search_text = meta.search_text or ""
            idx = search_text.lower().find(query_lower)
            if idx >= 0:
                start_i = max(0, idx - 75)
                end_i = min(len(search_text), idx + len(query) + 75)
                snippet = (
                    ("..." if start_i > 0 else "")
                    + search_text[start_i:end_i]
                    + ("..." if end_i < len(search_text) else "")
                )
                matches.append({
                    "thread_id": meta.thread_id,
                    "summary": meta.summary,
                    "snippet": snippet,
                    "updated_at": meta.updated_at,
                    "message_count": meta.message_count,
                })
        matches.sort(key=lambda m: m["updated_at"], reverse=True)
        total = len(matches)
        return matches[offset : offset + limit], total

    async def cleanup_expired_threads(self) -> list[str]:
        """Find thread IDs still in sorted sets whose hash metadata has expired.

        Returns a list of thread_ids that need checkpoint cleanup.
        Called periodically by the background cleanup task.
        """
        expired_ids: list[str] = []
        r = await self._get_redis()
        if r is None:
            return expired_ids

        try:
            # Scan all sorted set keys (pattern: threads:*)
            cursor = 0
            while True:
                cursor, keys = await r.scan(cursor, match="threads:*", count=100)
                for key in keys:
                    # Skip hash keys (they contain colons after the tag)
                    key_str = key if isinstance(key, str) else key.decode()
                    parts = key_str.split(":")
                    # Sorted set keys are "threads:{tag}" (2 parts)
                    # Hash keys are "threads:{tag}:{thread_id}" (3+ parts)
                    if len(parts) != 2:
                        continue

                    # Get all thread IDs in this sorted set
                    thread_ids = await r.zrange(key_str, 0, -1)
                    if not thread_ids:
                        continue

                    # Check which ones have expired hash metadata
                    pipe = r.pipeline()
                    for tid in thread_ids:
                        pipe.exists(f"{key_str}:{tid}")
                    exists_results = await pipe.execute()

                    for tid, exists in zip(thread_ids, exists_results, strict=False):
                        if not exists:
                            # Hash expired but still in sorted set — clean up
                            await r.zrem(key_str, tid)
                            tid_str = tid if isinstance(tid, str) else tid.decode()
                            expired_ids.append(tid_str)
                if cursor == 0:
                    break
        except (RedisError, RuntimeError) as exc:
            logger.warning("ThreadStore cleanup_expired_threads error: %s", exc)

        return expired_ids


thread_store = ThreadStore()


_LANGUAGE_NAMES = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "hi": "Hindi",
    "ja": "Japanese",
}


async def generate_summary(
    user_message: str, assistant_text: str, *, locale: str | None = None,
) -> str:
    """Generate a one-line AI summary of the conversation turn.

    Uses the cheap subagent model. Falls back to first 100 chars of user
    message if the LLM call fails. When *locale* is provided and not "en",
    the summary is generated in that language.
    """
    try:
        from agents.llm import get_subagent_model

        model = get_subagent_model()
        system_content = (
            "Summarize this travel conversation in 2-5 words "
            "(max 40 chars). Just destination and trip type. "
            "No preamble, no quotes, no periods."
        )
        if locale and locale in _LANGUAGE_NAMES and locale != "en":
            system_content += f" Respond in {_LANGUAGE_NAMES[locale]}."
        response = await model.ainvoke([
            {
                "role": "system",
                "content": system_content,
            },
            {
                "role": "user",
                "content": (
                    f"User: {user_message[:200]}\n"
                    f"Assistant: {assistant_text[:300]}"
                ),
            },
        ])
        content = getattr(response, "content", "")
        if isinstance(content, list):
            content = " ".join(
                p.get("text", "") for p in content
                if isinstance(p, dict) and p.get("type") == "text"
            )
        summary = content.strip() if isinstance(content, str) else str(content).strip()
        return summary[:50] if summary else user_message[:50]
    except Exception:  # noqa: BLE001 (intentional fallback)
        logger.warning("AI summary generation failed, using fallback")
        return user_message[:50]
