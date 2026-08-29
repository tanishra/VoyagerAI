"""Cost tracking store — Redis-backed with in-memory fallback.

Stores per-session and per-subagent API costs for internal analytics.
Follows the same graceful degradation pattern as threads.py and cache.py.

Redis key layout:
  costs:session:{thread_id}            — hash: total cost data per session
  costs:subagent:{thread_id}           — hash: subagent name → JSON cost breakdown
  costs:index                          — sorted set: thread_id → total_cost_usd (for analytics)
  costs:daily:{YYYY-MM-DD}             — sorted set: thread_id → cost_usd (for daily aggregates)
  costs:user:{user_id}                 — sorted set: thread_id → cost_usd (per-user totals)
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

logger = logging.getLogger("travel_agent.cost_store")

_TTL_SECONDS: int = settings.THREAD_TTL_DAYS * 86_400


@dataclass
class SessionCost:
    thread_id: str
    user_id: str
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    efficiency_ratio: float
    budget_limit_usd: float
    budget_reached: bool
    created_at: float = field(default_factory=time.time)


@dataclass
class SubagentCost:
    subagent_name: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    model_used: str
    timestamp: float


class CostStore:
    """Redis-backed cost storage with in-memory fallback."""

    def __init__(self) -> None:
        self._redis: Redis | None = None
        self._mem_sessions: dict[str, dict] = {}
        self._mem_subagents: dict[str, list[dict]] = {}

    async def _get_redis(self) -> Redis | None:
        if self._redis is None:
            try:
                self._redis = Redis.from_url(REDIS_URL, decode_responses=True)
                await self._redis.ping()
                logger.info("CostStore connected to Redis at %s", REDIS_URL)
            except (RedisError, RuntimeError) as exc:
                logger.warning("CostStore Redis unavailable — using in-memory fallback: %s", exc)
                self._redis = None
        return self._redis

    async def record_subagent_cost(
        self,
        thread_id: str,
        user_id: str,
        subagent_name: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        model_used: str,
    ) -> None:
        """Record a single subagent's cost for a thread."""
        ts = time.time()
        entry = {
            "subagent_name": subagent_name,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost_usd,
            "model_used": model_used,
            "timestamp": ts,
        }
        r = await self._get_redis()
        if r is not None:
            try:
                key = f"costs:subagent:{thread_id}"
                # Store as a list in a hash field keyed by subagent_name + timestamp
                field_name = f"{subagent_name}:{ts}"
                pipe = r.pipeline()
                pipe.hset(key, field_name, json.dumps(entry))
                pipe.expire(key, _TTL_SECONDS)
                await pipe.execute()
                return
            except (RedisError, RuntimeError) as exc:
                logger.warning("CostStore record_subagent_cost Redis error: %s", exc)

        self._mem_subagents.setdefault(thread_id, []).append(entry)

    async def update_session_total(
        self,
        thread_id: str,
        user_id: str,
        total_input_tokens: int,
        total_output_tokens: int,
        total_cost_usd: float,
        budget_limit_usd: float,
        budget_reached: bool,
    ) -> None:
        """Update or create the session-level cost summary for a thread."""
        efficiency_ratio = (
            total_input_tokens / max(total_output_tokens, 1)
        )
        now = time.time()
        data = {
            "thread_id": thread_id,
            "user_id": user_id,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_cost_usd": total_cost_usd,
            "efficiency_ratio": efficiency_ratio,
            "budget_limit_usd": budget_limit_usd,
            "budget_reached": "1" if budget_reached else "0",
            "created_at": str(now),
        }
        daily_key = f"costs:daily:{time.strftime('%Y-%m-%d', time.gmtime(now))}"

        r = await self._get_redis()
        if r is not None:
            try:
                pipe = r.pipeline()
                pipe.hset(f"costs:session:{thread_id}", mapping=data)
                pipe.expire(f"costs:session:{thread_id}", _TTL_SECONDS)
                pipe.zadd("costs:index", {thread_id: total_cost_usd})
                pipe.zadd(daily_key, {thread_id: total_cost_usd})
                pipe.expire(daily_key, _TTL_SECONDS)
                user_tag = hashlib.sha256(user_id.encode()).hexdigest()[:12]
                pipe.zadd(f"costs:user:{user_tag}", {thread_id: total_cost_usd})
                pipe.expire(f"costs:user:{user_tag}", _TTL_SECONDS)
                await pipe.execute()
                return
            except (RedisError, RuntimeError) as exc:
                logger.warning("CostStore update_session_total Redis error: %s", exc)

        self._mem_sessions[thread_id] = data

    async def get_session_cost(self, thread_id: str) -> dict | None:
        """Get the session-level cost summary for a thread."""
        r = await self._get_redis()
        if r is not None:
            try:
                data = await r.hgetall(f"costs:session:{thread_id}")
                if not data:
                    return None
                return {
                    "thread_id": data.get("thread_id", thread_id),
                    "user_id": data.get("user_id", ""),
                    "total_input_tokens": int(data.get("total_input_tokens", 0)),
                    "total_output_tokens": int(data.get("total_output_tokens", 0)),
                    "total_cost_usd": float(data.get("total_cost_usd", 0.0)),
                    "efficiency_ratio": float(data.get("efficiency_ratio", 0.0)),
                    "budget_limit_usd": float(data.get("budget_limit_usd", 0.0)),
                    "budget_reached": data.get("budget_reached") == "1",
                    "created_at": float(data.get("created_at", 0)),
                }
            except (RedisError, RuntimeError) as exc:
                logger.warning("CostStore get_session_cost Redis error: %s", exc)

        mem_data = self._mem_sessions.get(thread_id)
        if mem_data is None:
            return None
        return self._normalize_session(mem_data)

    def _normalize_session(self, data: dict) -> dict:
        """Normalize a raw session dict to consistent return format."""
        return {
            "thread_id": data.get("thread_id", ""),
            "user_id": data.get("user_id", ""),
            "total_input_tokens": int(data.get("total_input_tokens", 0)),
            "total_output_tokens": int(data.get("total_output_tokens", 0)),
            "total_cost_usd": float(data.get("total_cost_usd", 0.0)),
            "efficiency_ratio": float(data.get("efficiency_ratio", 0.0)),
            "budget_limit_usd": float(data.get("budget_limit_usd", 0.0)),
            "budget_reached": data.get("budget_reached") == "1" if isinstance(data.get("budget_reached"), str) else bool(data.get("budget_reached", False)),
            "created_at": float(data.get("created_at", 0)),
        }

    async def get_subagent_breakdown(self, thread_id: str) -> list[dict]:
        """Get per-subagent cost breakdown for a thread."""
        r = await self._get_redis()
        if r is not None:
            try:
                raw = await r.hgetall(f"costs:subagent:{thread_id}")
                if not raw:
                    return []
                results = []
                for field_name, value in raw.items():
                    try:
                        results.append(json.loads(value))
                    except (json.JSONDecodeError, TypeError):
                        continue
                results.sort(key=lambda x: x.get("timestamp", 0))
                return results
            except (RedisError, RuntimeError) as exc:
                logger.warning("CostStore get_subagent_breakdown Redis error: %s", exc)

        return self._mem_subagents.get(thread_id, [])

    async def get_aggregate_stats(self, period: str = "week") -> dict:
        """Get aggregate cost analytics for a time period.

        Args:
            period: "day", "week", or "month".

        Returns:
            Dict with total_cost, total_conversations, avg_cost,
            per_day breakdown, per_subagent breakdown, top_users.
        """
        now = time.time()
        if period == "day":
            days = 1
        elif period == "month":
            days = 30
        else:
            days = 7

        start_ts = now - (days * 86_400)

        r = await self._get_redis()
        if r is not None:
            try:
                # Get all thread IDs from the index
                thread_ids = await r.zrange("costs:index", 0, -1)
                if not thread_ids:
                    return self._empty_stats()

                pipe = r.pipeline()
                for tid in thread_ids:
                    pipe.hgetall(f"costs:session:{tid}")
                sessions_raw = await pipe.execute()

                sessions = []
                for tid, data in zip(thread_ids, sessions_raw, strict=False):
                    if not data:
                        continue
                    created = float(data.get("created_at", 0))
                    if created >= start_ts:
                        sessions.append({
                            "thread_id": tid,
                            "user_id": data.get("user_id", ""),
                            "total_input_tokens": int(data.get("total_input_tokens", 0)),
                            "total_output_tokens": int(data.get("total_output_tokens", 0)),
                            "total_cost_usd": float(data.get("total_cost_usd", 0.0)),
                            "efficiency_ratio": float(data.get("efficiency_ratio", 0.0)),
                            "budget_reached": data.get("budget_reached") == "1",
                            "created_at": created,
                        })

                return await self._compute_stats(sessions, thread_ids, r, start_ts)
            except (RedisError, RuntimeError) as exc:
                logger.warning("CostStore get_aggregate_stats Redis error: %s", exc)

        # In-memory fallback
        sessions = []
        for tid, data in self._mem_sessions.items():
            created = float(data.get("created_at", 0))
            if created >= start_ts:
                sessions.append({
                    "thread_id": tid,
                    "user_id": data.get("user_id", ""),
                    "total_input_tokens": int(data.get("total_input_tokens", 0)),
                    "total_output_tokens": int(data.get("total_output_tokens", 0)),
                    "total_cost_usd": float(data.get("total_cost_usd", 0.0)),
                    "efficiency_ratio": float(data.get("efficiency_ratio", 0.0)),
                    "budget_reached": data.get("budget_reached") == "1",
                    "created_at": created,
                })
        return await self._compute_stats(sessions, list(self._mem_sessions.keys()), None, start_ts)

    def _empty_stats(self) -> dict:
        return {
            "total_cost": 0.0,
            "total_conversations": 0,
            "avg_cost_per_conversation": 0.0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "per_day": [],
            "per_subagent": [],
            "top_users": [],
            "poor_efficiency_sessions": [],
        }

    async def _compute_stats(
        self,
        sessions: list[dict],
        all_thread_ids: list[str],
        r: Redis | None,
        start_ts: float,
    ) -> dict:
        total_cost = sum(s["total_cost_usd"] for s in sessions)
        total_conv = len(sessions)
        total_in = sum(s["total_input_tokens"] for s in sessions)
        total_out = sum(s["total_output_tokens"] for s in sessions)

        # Per-day breakdown
        per_day: dict[str, float] = {}
        for s in sessions:
            day = time.strftime("%Y-%m-%d", time.gmtime(s["created_at"]))
            per_day[day] = per_day.get(day, 0.0) + s["total_cost_usd"]
        per_day_list = [{"date": d, "cost": c} for d, c in sorted(per_day.items())]

        # Per-subagent breakdown (aggregate across all sessions)
        subagent_costs: dict[str, dict[str, float]] = {}
        if r is not None:
            pipe = r.pipeline()
            for tid in all_thread_ids:
                pipe.hgetall(f"costs:subagent:{tid}")
            subagent_raw = await pipe.execute()
            for raw in subagent_raw:
                if not raw:
                    continue
                for field_name, value in raw.items():
                    try:
                        entry = json.loads(value)
                        name = entry.get("subagent_name", "unknown")
                        if name not in subagent_costs:
                            subagent_costs[name] = {
                                "cost": 0.0,
                                "input_tokens": 0,
                                "output_tokens": 0,
                            }
                        subagent_costs[name]["cost"] += entry.get("cost_usd", 0.0)
                        subagent_costs[name]["input_tokens"] += entry.get("input_tokens", 0)
                        subagent_costs[name]["output_tokens"] += entry.get("output_tokens", 0)
                    except (json.JSONDecodeError, TypeError):
                        continue
        else:
            for tid, entries in self._mem_subagents.items():
                for entry in entries:
                    name = entry.get("subagent_name", "unknown")
                    if name not in subagent_costs:
                        subagent_costs[name] = {"cost": 0.0, "input_tokens": 0, "output_tokens": 0}
                    subagent_costs[name]["cost"] += entry.get("cost_usd", 0.0)
                    subagent_costs[name]["input_tokens"] += entry.get("input_tokens", 0)
                    subagent_costs[name]["output_tokens"] += entry.get("output_tokens", 0)

        per_subagent = [
            {"name": name, **data}
            for name, data in sorted(
                subagent_costs.items(), key=lambda x: x[1]["cost"], reverse=True
            )
        ]

        # Top users by spend
        user_costs: dict[str, float] = {}
        for s in sessions:
            uid = s["user_id"]
            user_costs[uid] = user_costs.get(uid, 0.0) + s["total_cost_usd"]
        top_users = [
            {"user_id": uid, "cost": c}
            for uid, c in sorted(user_costs.items(), key=lambda x: x[1], reverse=True)[:10]
        ]

        # Poor efficiency sessions (>50:1 ratio)
        poor_efficiency = [
            {
                "thread_id": s["thread_id"],
                "user_id": s["user_id"],
                "efficiency_ratio": s["efficiency_ratio"],
                "cost": s["total_cost_usd"],
            }
            for s in sessions
            if s["efficiency_ratio"] > 50.0
        ]

        return {
            "total_cost": round(total_cost, 6),
            "total_conversations": total_conv,
            "avg_cost_per_conversation": round(total_cost / max(total_conv, 1), 6),
            "total_input_tokens": total_in,
            "total_output_tokens": total_out,
            "per_day": per_day_list,
            "per_subagent": per_subagent,
            "top_users": top_users,
            "poor_efficiency_sessions": poor_efficiency,
        }

    async def cleanup_expired(self) -> list[str]:
        """Clean up cost data for expired threads. Returns cleaned thread IDs."""
        cleaned: list[str] = []
        r = await self._get_redis()
        if r is None:
            return cleaned

        try:
            thread_ids = await r.zrange("costs:index", 0, -1)
            pipe = r.pipeline()
            for tid in thread_ids:
                pipe.exists(f"costs:session:{tid}")
            exists_results = await pipe.execute()

            for tid, exists in zip(thread_ids, exists_results, strict=False):
                if not exists:
                    pipe2 = r.pipeline()
                    pipe2.zrem("costs:index", tid)
                    pipe2.delete(f"costs:session:{tid}")
                    pipe2.delete(f"costs:subagent:{tid}")
                    await pipe2.execute()
                    cleaned.append(tid)
        except (RedisError, RuntimeError) as exc:
            logger.warning("CostStore cleanup_expired error: %s", exc)

        return cleaned


cost_store = CostStore()
