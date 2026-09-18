"""File upload store — Redis-backed temporary file storage with TTL.

Stores uploaded files (images, PDFs) as base64 in Redis hashes with a
configurable TTL (default 1 hour). Files auto-expire and are cleaned up
by Redis. Writes go through to SQLite as well so a Redis blip can't
hide a file that was uploaded while Redis was down. In-memory is the
last-resort fallback.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import time
import uuid
from dataclasses import dataclass

from redis.asyncio import Redis
from redis.exceptions import RedisError

from config import REDIS_URL
from sqlite_fallback import get_sqlite_connection

logger = logging.getLogger("travel_agent.file_store")

_TTL_SECONDS: int = 3600  # 1 hour


@dataclass
class FileMeta:
    file_id: str
    filename: str
    content_type: str
    size: int
    data: str  # base64-encoded file bytes
    created_at: float


def _user_tag(user_id: str) -> str:
    """Hash the user_id to a 12-char tag (same scheme as threads.py)."""
    return hashlib.sha256(user_id.encode()).hexdigest()[:12]


class FileStore:
    """Redis-backed file store with SQLite write-through + in-memory fallback."""

    def __init__(self) -> None:
        self._redis: Redis | None = None
        self._mem: dict[str, dict[str, dict]] = {}  # user_id -> {file_id -> data}

    async def _get_redis(self) -> Redis | None:
        if self._redis is None:
            try:
                self._redis = Redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)
                await self._redis.ping()
                logger.info("FileStore connected to Redis at %s", REDIS_URL)
            except (RedisError, RuntimeError) as exc:
                logger.warning("FileStore Redis unavailable — using in-memory fallback: %s", exc)
                self._redis = None
        return self._redis

    async def upload(
        self,
        user_id: str,
        filename: str,
        content_type: str,
        data: bytes,
    ) -> dict:
        """Store file in Redis + SQLite, return metadata dict with data_url."""
        file_id = str(uuid.uuid4())
        tag = _user_tag(user_id)
        b64_data = base64.b64encode(data).decode("ascii")
        now = time.time()
        size = len(data)
        data_url = f"data:{content_type};base64,{b64_data}"
        result = {
            "file_id": file_id,
            "data_url": data_url,
            "filename": filename,
            "content_type": content_type,
            "size": size,
        }
        persisted = False

        r = await self._get_redis()
        if r is not None:
            try:
                key = f"files:{tag}:{file_id}"
                pipe = r.pipeline()
                pipe.hset(key, mapping={
                    "file_id": file_id,
                    "filename": filename[:200],
                    "content_type": content_type,
                    "size": str(size),
                    "data": b64_data,
                    "created_at": str(now),
                })
                pipe.expire(key, _TTL_SECONDS)
                await pipe.execute()
                persisted = True
            except (RedisError, RuntimeError) as exc:
                logger.warning("FileStore upload Redis error: %s", exc)

        # SQLite write-through (durable copy alongside Redis)
        db = await get_sqlite_connection()
        if db is not None:
            try:
                await db.execute(
                    "INSERT OR REPLACE INTO files (file_id, user_tag, filename, content_type, size, data_base64, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (file_id, tag, filename[:200], content_type, size, b64_data, now, now + _TTL_SECONDS),
                )
                await db.commit()
                persisted = True
            except Exception as exc:  # noqa: BLE001
                logger.warning("FileStore upload SQLite error: %s", exc)

        if not persisted:
            # In-memory last resort
            user_files = self._mem.setdefault(user_id, {})
            user_files[file_id] = {
                "file_id": file_id,
                "filename": filename[:200],
                "content_type": content_type,
                "size": size,
                "data": b64_data,
                "created_at": now,
            }
        return result

    async def get(self, user_id: str, file_id: str) -> FileMeta | None:
        """Retrieve file metadata + data from the first store that has it."""
        tag = _user_tag(user_id)

        r = await self._get_redis()
        if r is not None:
            try:
                data = await r.hgetall(f"files:{tag}:{file_id}")
                if data:
                    return FileMeta(
                        file_id=data.get("file_id", file_id),
                        filename=data.get("filename", ""),
                        content_type=data.get("content_type", ""),
                        size=int(data.get("size", 0)),
                        data=data.get("data", ""),
                        created_at=float(data.get("created_at", 0)),
                    )
            except (RedisError, RuntimeError) as exc:
                logger.warning("FileStore get Redis error: %s", exc)

        db = await get_sqlite_connection()
        if db is not None:
            try:
                cur = await db.execute(
                    "SELECT * FROM files WHERE file_id = ? AND user_tag = ?", (file_id, tag)
                )
                row = await cur.fetchone()
                if row:
                    if float(row["expires_at"]) < time.time():
                        await db.execute("DELETE FROM files WHERE file_id = ?", (file_id,))
                        await db.commit()
                    else:
                        return FileMeta(
                            file_id=row["file_id"],
                            filename=row["filename"] or "",
                            content_type=row["content_type"] or "",
                            size=int(row["size"] or 0),
                            data=row["data_base64"] or "",
                            created_at=float(row["created_at"] or 0),
                        )
            except Exception as exc:  # noqa: BLE001
                logger.warning("FileStore get SQLite error: %s", exc)

        # In-memory fallback
        user_files = self._mem.get(user_id, {})
        entry = user_files.get(file_id)
        if not entry:
            return None
        return FileMeta(
            file_id=entry["file_id"],
            filename=entry["filename"],
            content_type=entry["content_type"],
            size=entry["size"],
            data=entry["data"],
            created_at=entry["created_at"],
        )

    async def delete(self, user_id: str, file_id: str) -> bool:
        """Delete a file from ALL stores. Returns True if it existed anywhere."""
        tag = _user_tag(user_id)
        existed = False

        r = await self._get_redis()
        if r is not None:
            try:
                deleted = await r.delete(f"files:{tag}:{file_id}")
                existed = deleted > 0
            except (RedisError, RuntimeError) as exc:
                logger.warning("FileStore delete Redis error: %s", exc)

        db = await get_sqlite_connection()
        if db is not None:
            try:
                cur = await db.execute(
                    "DELETE FROM files WHERE file_id = ? AND user_tag = ?", (file_id, tag)
                )
                await db.commit()
                existed = existed or cur.rowcount > 0
            except Exception as exc:  # noqa: BLE001
                logger.warning("FileStore delete SQLite error: %s", exc)

        user_files = self._mem.get(user_id, {})
        if file_id in user_files:
            del user_files[file_id]
            existed = True

        return existed


file_store = FileStore()
