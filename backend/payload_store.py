"""Pipeline payload store — Redis-backed with durable + memory fallbacks.

The pipeline tools park full comparison/itinerary payloads here instead of
returning them to the model (mirrors the pending-visuals pattern). The
stream layer pops them on tool_end and emits them as SSE events.

Two key families:
- ``pipeline:payload:{id}`` — one-shot payloads, TTL 1h (consumed within
  seconds; TTL is leak insurance + survives a restart between tool_end and
  pop). Redis + memory only — seconds-lived, durability pointless.
- ``pipeline:thread:{tid}:{key}`` — per-thread state (latest itinerary/
  comparison, constraints, research brief, payload replay records) needed
  by refine_itinerary, history re-attach, export, and share on later
  turns. Redis primary (TTL 30d), write-through to the durable tier
  (Postgres via get_durable_db, else SQLite) so a Redis flush doesn't
  orphan exports while checkpoints survive; memory last resort.
"""

from __future__ import annotations

import json
import logging
import time
from collections import OrderedDict

from redis.asyncio import Redis
from redis.exceptions import RedisError

from config import REDIS_URL

logger = logging.getLogger("travel_agent.payload_store")

_PAYLOAD_TTL_S = 3600  # one-shot payloads
_THREAD_STATE_TTL_S = 30 * 86_400  # per-thread state (constraints, latest comparison)
_MEM_MAX_ENTRIES = 500


class PayloadStore:
    def __init__(self) -> None:
        self._redis: Redis | None = None
        self._redis_retry_after = 0.0
        # key -> (expires_at, json_str); OrderedDict for oldest-first eviction
        self._mem: OrderedDict[str, tuple[float, str]] = OrderedDict()

    async def _get_redis(self) -> Redis | None:
        # After a connect failure, retry at most every 60s — a Redis blip
        # shouldn't cost 2s on every call, but shouldn't be permanent either.
        if time.time() < self._redis_retry_after:
            return None
        if self._redis is None:
            try:
                self._redis = Redis.from_url(
                    REDIS_URL, decode_responses=True,
                    socket_connect_timeout=2, socket_timeout=2,
                )
                await self._redis.ping()
                logger.info("PayloadStore connected to Redis")
            except (RedisError, RuntimeError, OSError) as exc:
                logger.warning("PayloadStore Redis unavailable — in-memory fallback: %s", exc)
                self._redis = None
                self._redis_retry_after = time.time() + 60
        return self._redis

    # -- internals ---------------------------------------------------------

    def _mem_get(self, key: str) -> dict | None:
        entry = self._mem.get(key)
        if entry is None:
            return None
        exp, raw = entry
        if exp <= time.time():
            del self._mem[key]
            return None
        self._mem.move_to_end(key)
        return json.loads(raw)

    def _mem_set(self, key: str, data: dict, ttl: int) -> None:
        now = time.time()
        for k in [k for k, (exp, _) in self._mem.items() if exp <= now]:
            del self._mem[k]
        self._mem[key] = (now + ttl, json.dumps(data))
        self._mem.move_to_end(key)
        while len(self._mem) > _MEM_MAX_ENTRIES:
            self._mem.popitem(last=False)

    def _mem_del(self, key: str) -> None:
        self._mem.pop(key, None)

    # -- one-shot payloads ---------------------------------------------------

    async def store(self, payload_id: str, kind: str, data: dict) -> None:
        key = f"pipeline:payload:{payload_id}"
        blob = {"kind": kind, "data": data}
        r = await self._get_redis()
        if r is not None:
            try:
                await r.set(key, json.dumps(blob), ex=_PAYLOAD_TTL_S)
                return
            except (RedisError, RuntimeError) as exc:
                logger.warning("PayloadStore set error — memory fallback: %s", exc)
        self._mem_set(key, blob, _PAYLOAD_TTL_S)

    async def pop(self, payload_id: str) -> dict | None:
        key = f"pipeline:payload:{payload_id}"
        r = await self._get_redis()
        if r is not None:
            try:
                raw = await r.get(key)
                if raw is not None:
                    await r.delete(key)
                    return json.loads(raw)
            except (RedisError, RuntimeError) as exc:
                logger.warning("PayloadStore pop error — memory fallback: %s", exc)
        return self._mem_pop(key)

    def _mem_pop(self, key: str) -> dict | None:
        entry = self._mem.pop(key, None)
        if entry is None:
            return None
        exp, raw = entry
        if exp <= time.time():
            return None
        return json.loads(raw)

    # -- per-thread state ----------------------------------------------------

    async def set_thread_state(self, thread_id: str, key: str, data: dict) -> None:
        rkey = f"pipeline:thread:{thread_id}:{key}"
        raw = json.dumps(data)
        expires_at = time.time() + _THREAD_STATE_TTL_S
        r = await self._get_redis()
        redis_ok = False
        if r is not None:
            try:
                await r.set(rkey, raw, ex=_THREAD_STATE_TTL_S)
                redis_ok = True
            except (RedisError, RuntimeError) as exc:
                logger.warning("PayloadStore thread-state set error — memory fallback: %s", exc)

        # Durable write-through (best-effort, like share_store) — survives a
        # Redis flush so history/export/share still resolve the record.
        try:
            from pg_store import get_durable_db

            db = await get_durable_db()
            if db is not None:
                await db.execute(
                    "INSERT OR REPLACE INTO payload_thread_state "
                    "(thread_id, key, data, expires_at) VALUES (?, ?, ?, ?)",
                    (thread_id, key, raw, expires_at),
                )
                await db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.warning("PayloadStore durable set error: %s", exc)

        if not redis_ok:
            self._mem_set(rkey, data, _THREAD_STATE_TTL_S)

    async def get_thread_state(self, thread_id: str, key: str) -> dict | None:
        rkey = f"pipeline:thread:{thread_id}:{key}"
        r = await self._get_redis()
        if r is not None:
            try:
                raw = await r.get(rkey)
                if raw is not None:
                    return json.loads(raw)
            except (RedisError, RuntimeError) as exc:
                logger.warning("PayloadStore thread-state get error — memory fallback: %s", exc)

        # Durable fallback — on hit, rehydrate Redis so the hot path stays fast.
        try:
            from pg_store import get_durable_db

            db = await get_durable_db()
            if db is not None:
                cur = await db.execute(
                    "SELECT data, expires_at FROM payload_thread_state "
                    "WHERE thread_id = ? AND key = ?",
                    (thread_id, key),
                )
                row = await cur.fetchone()
                if row is not None:
                    if float(row["expires_at"] or 0) <= time.time():
                        await db.execute(
                            "DELETE FROM payload_thread_state "
                            "WHERE thread_id = ? AND key = ?",
                            (thread_id, key),
                        )
                        await db.commit()
                    else:
                        raw = row["data"]
                        if r is not None:
                            try:
                                await r.set(rkey, raw, ex=_THREAD_STATE_TTL_S)
                            except (RedisError, RuntimeError):
                                pass
                        return json.loads(raw)
        except Exception as exc:  # noqa: BLE001
            logger.warning("PayloadStore durable get error: %s", exc)

        return self._mem_get(rkey)


payload_store = PayloadStore()
