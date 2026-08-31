"""File upload store — Redis-backed temporary file storage with TTL.

Stores uploaded files (images, PDFs) as base64 in Redis hashes with a
configurable TTL (default 1 hour). Files auto-expire and are cleaned up
by Redis. Falls back to an in-memory dict when Redis is unavailable
(same graceful degradation pattern as threads.py, share_store.py, etc.).
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
    """Redis-backed file store with in-memory fallback."""

    def __init__(self) -> None:
        self._redis: Redis | None = None
        self._mem: dict[str, dict[str, dict]] = {}  # user_id -> {file_id -> data}

    async def _get_redis(self) -> Redis | None:
        if self._redis is None:
            try:
                self._redis = Redis.from_url(REDIS_URL, decode_responses=True)
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
        """Store file in Redis, return metadata dict with data_url."""
        file_id = str(uuid.uuid4())
        tag = _user_tag(user_id)
        b64_data = base64.b64encode(data).decode("ascii")
        now = time.time()
        size = len(data)
        data_url = f"data:{content_type};base64,{b64_data}"

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
                return {
                    "file_id": file_id,
                    "data_url": data_url,
                    "filename": filename,
                    "content_type": content_type,
                    "size": size,
                }
            except (RedisError, RuntimeError) as exc:
                logger.warning("FileStore upload Redis error — falling back: %s", exc)

        # In-memory fallback
        user_files = self._mem.setdefault(user_id, {})
        user_files[file_id] = {
            "file_id": file_id,
            "filename": filename[:200],
            "content_type": content_type,
            "size": size,
            "data": b64_data,
            "created_at": now,
        }
        return {
            "file_id": file_id,
            "data_url": data_url,
            "filename": filename,
            "content_type": content_type,
            "size": size,
        }

    async def get(self, user_id: str, file_id: str) -> FileMeta | None:
        """Retrieve file metadata + data from Redis."""
        tag = _user_tag(user_id)
        r = await self._get_redis()
        if r is not None:
            try:
                key = f"files:{tag}:{file_id}"
                data = await r.hgetall(key)
                if not data:
                    return None
                return FileMeta(
                    file_id=data.get("file_id", file_id),
                    filename=data.get("filename", ""),
                    content_type=data.get("content_type", ""),
                    size=int(data.get("size", 0)),
                    data=data.get("data", ""),
                    created_at=float(data.get("created_at", 0)),
                )
            except (RedisError, RuntimeError) as exc:
                logger.warning("FileStore get Redis error — falling back: %s", exc)

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
        """Delete a file from Redis."""
        tag = _user_tag(user_id)
        r = await self._get_redis()
        if r is not None:
            try:
                key = f"files:{tag}:{file_id}"
                deleted = await r.delete(key)
                return deleted > 0
            except (RedisError, RuntimeError) as exc:
                logger.warning("FileStore delete Redis error — falling back: %s", exc)

        # In-memory fallback
        user_files = self._mem.get(user_id, {})
        if file_id in user_files:
            del user_files[file_id]
            return True
        return False


file_store = FileStore()
