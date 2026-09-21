"""Share token store — Redis-backed shareable itinerary links with TTL.

Stores itinerary snapshots against unguessable tokens so users can share
read-only itinerary links with anyone. Tokens expire after a configurable
TTL (default 7 days). Includes listing and revocation for full management.

Falls back to SQLite (persistent) then in-memory when Redis is unavailable.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import time
from dataclasses import dataclass

from redis.asyncio import Redis
from redis.exceptions import RedisError

from config import REDIS_URL, settings
from sqlite_fallback import get_sqlite_connection

logger = logging.getLogger("travel_agent.share")

_TTL_SECONDS: int = settings.SHARE_TTL_DAYS * 86_400


@dataclass
class ShareMeta:
    token: str
    thread_id: str
    destination: str
    created_at: float
    expires_at: float


def _user_tag(user_id: str) -> str:
    """Hash the user_id to a 12-char tag (same scheme as threads.py)."""
    return hashlib.sha256(user_id.encode()).hexdigest()[:12]


class ShareStore:
    """Redis-backed share token store with SQLite + in-memory fallback."""

    def __init__(self) -> None:
        self._redis: Redis | None = None
        self._mem: dict[str, dict[str, dict]] = {}  # user_id → {token → data}

    def _prune_mem(self) -> None:
        """Drop expired in-memory shares (same expiry as Redis/SQLite)."""
        now = time.time()
        for uid in list(self._mem):
            shares = self._mem[uid]
            for tok in [tok for tok, d in shares.items() if float(d.get("expires_at", 0)) <= now]:
                del shares[tok]
            if not shares:
                del self._mem[uid]

    async def _get_redis(self) -> Redis | None:
        if self._redis is None:
            try:
                self._redis = Redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)
                await self._redis.ping()
                logger.info("ShareStore connected to Redis at %s", REDIS_URL)
            except (RedisError, RuntimeError) as exc:
                logger.warning("ShareStore Redis unavailable — using in-memory fallback: %s", exc)
                self._redis = None
        return self._redis

    async def create_share(
        self,
        user_id: str,
        thread_id: str,
        itinerary_json: str,
        destination: str,
        image_base64: str | None = None,
    ) -> tuple[str, float]:
        """Create a share token. Returns (token, expires_at)."""
        tag = _user_tag(user_id)
        token = secrets.token_urlsafe(16)
        now = time.time()
        expires_at = now + _TTL_SECONDS

        persisted = False

        r = await self._get_redis()
        if r is not None:
            try:
                key = f"shares:{tag}:{token}"
                pipe = r.pipeline()
                mapping = {
                    "token": token,
                    "thread_id": thread_id,
                    "destination": destination[:100],
                    "itinerary_json": itinerary_json,
                    "created_at": str(now),
                    "expires_at": str(expires_at),
                }
                if image_base64:
                    mapping["image_base64"] = image_base64
                pipe.hset(key, mapping=mapping)
                pipe.zadd(f"shares:{tag}", {token: now})
                pipe.expire(key, _TTL_SECONDS)
                await pipe.execute()
                persisted = True
            except (RedisError, RuntimeError) as exc:
                logger.warning("ShareStore create_share Redis error: %s", exc)

        # SQLite write-through (durable copy alongside Redis)
        db = await get_sqlite_connection()
        if db is not None:
            try:
                await db.execute(
                    "INSERT OR REPLACE INTO shares (token, user_tag, thread_id, destination, itinerary_json, created_at, expires_at, image_base64) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (token, tag, thread_id, destination[:100], itinerary_json, now, expires_at, image_base64),
                )
                await db.commit()
                persisted = True
            except Exception as exc:  # noqa: BLE001
                logger.warning("ShareStore create_share SQLite error: %s", exc)

        if not persisted:
            # In-memory last resort
            self._prune_mem()
            user_shares = self._mem.setdefault(user_id, {})
            user_shares[token] = {
                "token": token,
                "thread_id": thread_id,
                "destination": destination[:100],
                "itinerary_json": itinerary_json,
                "created_at": now,
                "expires_at": expires_at,
                "image_base64": image_base64,
            }
        return token, expires_at

    async def get_share(self, token: str) -> dict | None:
        """Get a share by token. Returns {itinerary_json, destination, created_at, expires_at} or None."""
        r = await self._get_redis()
        if r is not None:
            try:
                # Scan across all user tags — public access, no user_id needed
                cursor = 0
                while True:
                    cursor, keys = await r.scan(cursor, match=f"shares:*:{token}", count=100)
                    for key in keys:
                        data = await r.hgetall(key)
                        if data:
                            expires_at = float(data.get("expires_at", 0))
                            if expires_at < time.time():
                                await r.delete(key)
                            else:
                                return {
                                    "itinerary_json": data.get("itinerary_json", ""),
                                    "destination": data.get("destination", ""),
                                    "created_at": float(data.get("created_at", 0)),
                                    "expires_at": expires_at,
                                    "image_base64": data.get("image_base64"),
                                }
                    if cursor == 0:
                        break
            except (RedisError, RuntimeError) as exc:
                logger.warning("ShareStore get_share Redis error: %s", exc)

        # SQLite — checked even when Redis is up but has no copy
        db = await get_sqlite_connection()
        if db is not None:
            try:
                cur = await db.execute(
                    "SELECT * FROM shares WHERE token = ?", (token,)
                )
                row = await cur.fetchone()
                if row:
                    expires_at = float(row["expires_at"] or 0)
                    if expires_at < time.time():
                        await db.execute("DELETE FROM shares WHERE token = ?", (token,))
                        await db.commit()
                    else:
                        return {
                            "itinerary_json": row["itinerary_json"] or "",
                            "destination": row["destination"] or "",
                            "created_at": float(row["created_at"] or 0),
                            "expires_at": expires_at,
                            "image_base64": row["image_base64"] if "image_base64" in row.keys() else None,
                        }
            except Exception as exc:  # noqa: BLE001
                logger.warning("ShareStore get_share SQLite error: %s", exc)

        # In-memory fallback
        for user_shares in self._mem.values():
            if token in user_shares:
                data = user_shares[token]
                if data["expires_at"] < time.time():
                    del user_shares[token]
                    return None
                return {
                    "itinerary_json": data["itinerary_json"],
                    "destination": data["destination"],
                    "created_at": data["created_at"],
                    "expires_at": data["expires_at"],
                    "image_base64": data.get("image_base64"),
                }
        return None

    async def list_shares(self, user_id: str) -> list[ShareMeta]:
        """List all active shares for a user, merged across all stores."""
        tag = _user_tag(user_id)
        now = time.time()
        merged: dict[str, ShareMeta] = {}

        r = await self._get_redis()
        if r is not None:
            try:
                tokens = await r.zrevrange(f"shares:{tag}", 0, -1)
                if tokens:
                    pipe = r.pipeline()
                    for tok in tokens:
                        pipe.hgetall(f"shares:{tag}:{tok}")
                    results = await pipe.execute()
                    for tok, data in zip(tokens, results, strict=False):
                        if not data:
                            continue
                        expires_at = float(data.get("expires_at", 0))
                        if expires_at < now:
                            continue
                        merged[tok] = ShareMeta(
                            token=data.get("token", tok),
                            thread_id=data.get("thread_id", ""),
                            destination=data.get("destination", ""),
                            created_at=float(data.get("created_at", 0)),
                            expires_at=expires_at,
                        )
            except (RedisError, RuntimeError) as exc:
                logger.warning("ShareStore list_shares Redis error: %s", exc)

        db = await get_sqlite_connection()
        if db is not None:
            try:
                cur = await db.execute(
                    "SELECT * FROM shares WHERE user_tag = ?", (tag,)
                )
                rows = await cur.fetchall()
                for row in rows:
                    expires_at = float(row["expires_at"] or 0)
                    if expires_at < now:
                        continue
                    tok = row["token"]
                    if tok not in merged:
                        merged[tok] = ShareMeta(
                            token=tok,
                            thread_id=row["thread_id"] or "",
                            destination=row["destination"] or "",
                            created_at=float(row["created_at"] or 0),
                            expires_at=expires_at,
                        )
            except Exception as exc:  # noqa: BLE001
                logger.warning("ShareStore list_shares SQLite error: %s", exc)

        user_shares = self._mem.get(user_id, {})
        for tok, data in user_shares.items():
            if data["expires_at"] < now or tok in merged:
                continue
            merged[tok] = ShareMeta(
                token=data["token"],
                thread_id=data["thread_id"],
                destination=data["destination"],
                created_at=data["created_at"],
                expires_at=data["expires_at"],
            )

        shares = list(merged.values())
        shares.sort(key=lambda s: s.created_at, reverse=True)
        return shares

    async def revoke_share(self, user_id: str, token: str) -> bool:
        """Revoke a share token from ALL stores. Returns True if it existed anywhere."""
        tag = _user_tag(user_id)
        existed = False

        r = await self._get_redis()
        if r is not None:
            try:
                key = f"shares:{tag}:{token}"
                deleted = await r.delete(key)
                await r.zrem(f"shares:{tag}", token)
                existed = deleted > 0
            except (RedisError, RuntimeError) as exc:
                logger.warning("ShareStore revoke_share Redis error: %s", exc)

        db = await get_sqlite_connection()
        if db is not None:
            try:
                cur = await db.execute(
                    "DELETE FROM shares WHERE token = ? AND user_tag = ?", (token, tag)
                )
                await db.commit()
                existed = existed or cur.rowcount > 0
            except Exception as exc:  # noqa: BLE001
                logger.warning("ShareStore revoke_share SQLite error: %s", exc)

        user_shares = self._mem.get(user_id, {})
        if token in user_shares:
            del user_shares[token]
            existed = True

        return existed


share_store = ShareStore()
