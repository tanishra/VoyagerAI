"""Security store — Redis-backed prompt injection flag and strike tracking.

Stores flagged injection attempts and per-user strike counts for cooldown
enforcement. Follows the same graceful degradation pattern as
cost_store.py, feedback_store.py, and research_cache.py.

Redis key layout:
  security:flags:{user_hash}         — sorted set: flag_id → timestamp
  security:flag:{flag_id}             — hash: category, confidence, source,
                                         thread_id (hashed), reasoning_snippet,
                                         created_at  [NEVER stores raw text]
  security:strikes:{user_hash}        — sorted set: strike_id → timestamp
  security:cooldown:{user_hash}       — string with TTL: cooldown until timestamp
  security:index                      — sorted set: all flag_ids by timestamp
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid

from redis.asyncio import Redis
from redis.exceptions import RedisError

from config import REDIS_URL, settings
from sqlite_fallback import get_sqlite_connection

logger = logging.getLogger("travel_agent.security_store")

_TTL_SECONDS: int = settings.THREAD_TTL_DAYS * 86_400
_STRIKE_WINDOW: int = settings.INJECTION_STRIKE_WINDOW_MINUTES * 60
_COOLDOWN_SECONDS: int = settings.INJECTION_COOLDOWN_MINUTES * 60


def _hash_user_id(user_id: str) -> str:
    """Hash user_id for privacy — same pattern as main.py's _scoped_chat_thread_id."""
    return hashlib.sha256(user_id.encode()).hexdigest()[:12]


class SecurityStore:
    """Redis-backed security flag/strike storage with SQLite + in-memory fallback."""

    def __init__(self) -> None:
        self._redis: Redis | None = None
        self._mem_flags: dict[str, list[dict]] = {}
        self._mem_strikes: dict[str, list[float]] = {}
        self._mem_cooldowns: dict[str, float] = {}

    async def _get_redis(self) -> Redis | None:
        if self._redis is None:
            try:
                self._redis = Redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)
                await self._redis.ping()
                logger.info("SecurityStore connected to Redis at %s", REDIS_URL)
            except (RedisError, RuntimeError) as exc:
                logger.warning("SecurityStore Redis unavailable — using in-memory fallback: %s", exc)
                self._redis = None
        return self._redis

    # -----------------------------------------------------------------
    # Flag recording
    # -----------------------------------------------------------------

    async def record_flag(
        self,
        user_id: str,
        category: str,
        confidence: str,
        source: str,
        reasoning: str = "",
        thread_id: str = "",
    ) -> str:
        """Record a flagged injection attempt. Returns the flag_id.

        NEVER stores the raw offending text — only metadata for admin review.
        """
        flag_id = uuid.uuid4().hex[:16]
        user_hash = _hash_user_id(user_id)
        thread_hash = hashlib.sha256(thread_id.encode()).hexdigest()[:12] if thread_id else ""
        now = time.time()

        entry = {
            "flag_id": flag_id,
            "user_hash": user_hash,
            "category": category,
            "confidence": confidence,
            "source": source,
            "thread_hash": thread_hash,
            "reasoning_snippet": reasoning[:200],
            "created_at": str(now),
        }

        persisted = False

        r = await self._get_redis()
        if r is not None:
            try:
                pipe = r.pipeline()
                pipe.hset(f"security:flag:{flag_id}", mapping=entry)
                pipe.expire(f"security:flag:{flag_id}", _TTL_SECONDS)
                pipe.zadd(f"security:flags:{user_hash}", {flag_id: now})
                pipe.expire(f"security:flags:{user_hash}", _TTL_SECONDS)
                pipe.zadd("security:index", {flag_id: now})
                pipe.expire("security:index", _TTL_SECONDS)
                await pipe.execute()
                persisted = True
            except (RedisError, RuntimeError) as exc:
                logger.warning("SecurityStore record_flag Redis error: %s", exc)

        # SQLite write-through (durable copy alongside Redis)
        db = await get_sqlite_connection()
        if db is not None:
            try:
                await db.execute(
                    "INSERT OR REPLACE INTO security_flags (flag_id, user_hash, category, confidence, source, thread_id, reasoning_snippet, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (flag_id, user_hash, category, confidence, source, thread_hash, reasoning[:200], now),
                )
                await db.commit()
                persisted = True
            except Exception as exc:  # noqa: BLE001
                logger.warning("SecurityStore record_flag SQLite error: %s", exc)

        if not persisted:
            self._mem_flags.setdefault(user_hash, []).append(entry)
        return flag_id

    # -----------------------------------------------------------------
    # Strike tracking
    # -----------------------------------------------------------------

    async def record_strike(self, user_id: str) -> int:
        """Record a strike for a user in all stores. Returns current strike count in rolling window."""
        user_hash = _hash_user_id(user_id)
        now = time.time()
        window_start = now - _STRIKE_WINDOW
        persisted = False

        r = await self._get_redis()
        if r is not None:
            try:
                key = f"security:strikes:{user_hash}"
                pipe = r.pipeline()
                pipe.zremrangebyscore(key, 0, window_start)
                pipe.zadd(key, {uuid.uuid4().hex[:16]: now})
                pipe.expire(key, _TTL_SECONDS)
                await pipe.execute()
                persisted = True
            except (RedisError, RuntimeError) as exc:
                logger.warning("SecurityStore record_strike Redis error: %s", exc)

        db = await get_sqlite_connection()
        if db is not None:
            try:
                await db.execute(
                    "INSERT INTO security_strikes (user_hash, created_at) VALUES (?, ?)",
                    (user_hash, now),
                )
                await db.commit()
                persisted = True
            except Exception as exc:  # noqa: BLE001
                logger.warning("SecurityStore record_strike SQLite error: %s", exc)

        if not persisted:
            self._mem_strikes.setdefault(user_hash, []).append(now)

        return await self.get_strike_count(user_id)

    async def get_strike_count(self, user_id: str) -> int:
        """Get current strike count within the rolling window — max across all stores."""
        user_hash = _hash_user_id(user_id)
        now = time.time()
        window_start = now - _STRIKE_WINDOW
        count = 0

        r = await self._get_redis()
        if r is not None:
            try:
                key = f"security:strikes:{user_hash}"
                pipe = r.pipeline()
                pipe.zremrangebyscore(key, 0, window_start)
                pipe.zcard(key)
                results = await pipe.execute()
                count = max(count, int(results[1]))
            except (RedisError, RuntimeError) as exc:
                logger.warning("SecurityStore get_strike_count Redis error: %s", exc)

        db = await get_sqlite_connection()
        if db is not None:
            try:
                await db.execute(
                    "DELETE FROM security_strikes WHERE user_hash = ? AND created_at < ?",
                    (user_hash, window_start),
                )
                await db.commit()
                cur = await db.execute(
                    "SELECT COUNT(*) FROM security_strikes WHERE user_hash = ? AND created_at >= ?",
                    (user_hash, window_start),
                )
                row = await cur.fetchone()
                count = max(count, int(row[0]) if row else 0)
            except Exception as exc:  # noqa: BLE001
                logger.warning("SecurityStore get_strike_count SQLite error: %s", exc)

        strikes = [s for s in self._mem_strikes.get(user_hash, []) if s > window_start]
        return max(count, len(strikes))

    # -----------------------------------------------------------------
    # Cooldown
    # -----------------------------------------------------------------

    async def is_in_cooldown(self, user_id: str) -> bool:
        """Check if a user is currently in cooldown."""
        user_hash = _hash_user_id(user_id)
        now = time.time()

        r = await self._get_redis()
        if r is not None:
            try:
                until = await r.get(f"security:cooldown:{user_hash}")
                if until is not None and float(until) > now:
                    return True
            except (RedisError, RuntimeError) as exc:
                logger.warning("SecurityStore is_in_cooldown Redis error: %s", exc)

        db = await get_sqlite_connection()
        if db is not None:
            try:
                cur = await db.execute(
                    "SELECT cooldown_until FROM security_cooldowns WHERE user_hash = ?",
                    (user_hash,),
                )
                row = await cur.fetchone()
                if row and float(row["cooldown_until"]) > now:
                    return True
            except Exception as exc:  # noqa: BLE001
                logger.warning("SecurityStore is_in_cooldown SQLite error: %s", exc)

        until = self._mem_cooldowns.get(user_hash, 0)
        return until > now

    async def apply_cooldown(self, user_id: str, minutes: int | None = None) -> None:
        """Apply a cooldown for a user."""
        user_hash = _hash_user_id(user_id)
        seconds = (minutes or settings.INJECTION_COOLDOWN_MINUTES) * 60
        until = time.time() + seconds

        persisted = False

        r = await self._get_redis()
        if r is not None:
            try:
                await r.set(f"security:cooldown:{user_hash}", str(until), ex=seconds + 60)
                persisted = True
            except (RedisError, RuntimeError) as exc:
                logger.warning("SecurityStore apply_cooldown Redis error: %s", exc)

        db = await get_sqlite_connection()
        if db is not None:
            try:
                await db.execute(
                    "INSERT OR REPLACE INTO security_cooldowns (user_hash, cooldown_until) VALUES (?, ?)",
                    (user_hash, until),
                )
                await db.commit()
                persisted = True
            except Exception as exc:  # noqa: BLE001
                logger.warning("SecurityStore apply_cooldown SQLite error: %s", exc)

        if not persisted:
            self._mem_cooldowns[user_hash] = until

    async def remove_cooldown(self, user_hash: str) -> bool:
        """Manually remove a cooldown (admin unblock). Returns True if removed."""
        existed = False

        r = await self._get_redis()
        if r is not None:
            try:
                deleted = await r.delete(f"security:cooldown:{user_hash}")
                existed = deleted > 0
            except (RedisError, RuntimeError) as exc:
                logger.warning("SecurityStore remove_cooldown Redis error: %s", exc)

        db = await get_sqlite_connection()
        if db is not None:
            try:
                cur = await db.execute(
                    "DELETE FROM security_cooldowns WHERE user_hash = ?", (user_hash,)
                )
                await db.commit()
                existed = existed or cur.rowcount > 0
            except Exception as exc:  # noqa: BLE001
                logger.warning("SecurityStore remove_cooldown SQLite error: %s", exc)

        if user_hash in self._mem_cooldowns:
            del self._mem_cooldowns[user_hash]
            existed = True
        return existed

    # -----------------------------------------------------------------
    # Admin queries
    # -----------------------------------------------------------------

    async def get_aggregate_stats(self, period: str = "week") -> dict:
        """Get aggregate security stats for admin dashboard."""
        now = time.time()
        period_seconds = {"day": 86400, "week": 604800, "month": 2592000}.get(period, 604800)
        since = now - period_seconds

        merged: dict[str, dict] = {}

        r = await self._get_redis()
        if r is not None:
            try:
                flag_ids = await r.zrangebyscore("security:index", since, now)
                if flag_ids:
                    pipe = r.pipeline()
                    for fid in flag_ids:
                        pipe.hgetall(f"security:flag:{fid}")
                    results = await pipe.execute()
                    for fid, data in zip(flag_ids, results, strict=False):
                        if data:
                            merged[fid] = dict(data)
            except (RedisError, RuntimeError) as exc:
                logger.warning("SecurityStore get_aggregate_stats Redis error: %s", exc)

        db = await get_sqlite_connection()
        if db is not None:
            try:
                cur = await db.execute(
                    "SELECT * FROM security_flags WHERE created_at > ?", (since,)
                )
                for row in await cur.fetchall():
                    fid = row["flag_id"]
                    if fid not in merged:
                        merged[fid] = {
                            "flag_id": fid,
                            "user_hash": row["user_hash"] or "",
                            "category": row["category"] or "unknown",
                            "confidence": row["confidence"] or "unknown",
                            "source": row["source"] or "unknown",
                            "reasoning_snippet": row["reasoning_snippet"] or "",
                            "created_at": str(row["created_at"] or 0),
                        }
            except Exception as exc:  # noqa: BLE001
                logger.warning("SecurityStore get_aggregate_stats SQLite error: %s", exc)

        for flags in self._mem_flags.values():
            for f in flags:
                if float(f.get("created_at", 0)) > since:
                    merged.setdefault(f["flag_id"], f)

        flag_ids = list(merged.keys())
        return self._compute_stats(flag_ids, [merged[f] for f in flag_ids])

    async def get_active_cooldowns(self) -> list[dict]:
        """Get all currently active cooldowns for admin review."""
        now = time.time()
        merged: dict[str, float] = {}

        r = await self._get_redis()
        if r is not None:
            try:
                keys = await r.keys("security:cooldown:*")
                if keys:
                    pipe = r.pipeline()
                    for k in keys:
                        pipe.get(k)
                    results = await pipe.execute()
                    for k, v in zip(keys, results, strict=False):
                        if v is not None and float(v) > now:
                            user_hash = k.split(":")[-1]
                            merged[user_hash] = max(merged.get(user_hash, 0), float(v))
            except (RedisError, RuntimeError) as exc:
                logger.warning("SecurityStore get_active_cooldowns Redis error: %s", exc)

        db = await get_sqlite_connection()
        if db is not None:
            try:
                cur = await db.execute(
                    "SELECT user_hash, cooldown_until FROM security_cooldowns WHERE cooldown_until > ?",
                    (now,),
                )
                for row in await cur.fetchall():
                    h = row["user_hash"]
                    merged[h] = max(merged.get(h, 0), float(row["cooldown_until"]))
            except Exception as exc:  # noqa: BLE001
                logger.warning("SecurityStore get_active_cooldowns SQLite error: %s", exc)

        for h, v in self._mem_cooldowns.items():
            if v > now:
                merged[h] = max(merged.get(h, 0), v)

        return [
            {"user_hash": h, "until": v, "remaining_seconds": int(v - now)}
            for h, v in merged.items()
        ]

    def _empty_stats(self) -> dict:
        return {
            "total_flags": 0,
            "by_category": {},
            "by_source": {},
            "by_confidence": {},
            "unique_users": 0,
            "active_cooldowns": 0,
            "recent_flags": [],
        }

    def _compute_stats(self, flag_ids: list[str], results: list[dict]) -> dict:
        by_category: dict[str, int] = {}
        by_source: dict[str, int] = {}
        by_confidence: dict[str, int] = {}
        users: set[str] = set()
        recent: list[dict] = []

        for _fid, data in zip(flag_ids, results, strict=False):
            if not data:
                continue
            cat = data.get("category", "unknown")
            src = data.get("source", "unknown")
            conf = data.get("confidence", "unknown")
            uh = data.get("user_hash", "")

            by_category[cat] = by_category.get(cat, 0) + 1
            by_source[src] = by_source.get(src, 0) + 1
            by_confidence[conf] = by_confidence.get(conf, 0) + 1
            users.add(uh)

            recent.append({
                "flag_id": data.get("flag_id", ""),
                "category": cat,
                "source": src,
                "confidence": conf,
                "user_hash": uh,
                "reasoning_snippet": data.get("reasoning_snippet", ""),
                "created_at": float(data.get("created_at", 0)),
            })

        recent.sort(key=lambda x: x["created_at"], reverse=True)

        return {
            "total_flags": len(recent),
            "by_category": by_category,
            "by_source": by_source,
            "by_confidence": by_confidence,
            "unique_users": len(users),
            "active_cooldowns": len(self._mem_cooldowns),
            "recent_flags": recent[:50],
        }


security_store = SecurityStore()
