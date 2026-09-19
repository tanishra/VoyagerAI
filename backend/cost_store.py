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

import calendar
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field

from redis.asyncio import Redis
from redis.exceptions import RedisError

from config import REDIS_URL, settings
from sqlite_fallback import get_sqlite_connection

logger = logging.getLogger("travel_agent.cost_store")

_TTL_SECONDS: int = settings.THREAD_TTL_DAYS * 86_400


def _utc_start_of_day(now: float) -> float:
    """Return the Unix timestamp of UTC midnight for the day containing *now*."""
    today = time.strftime("%Y-%m-%d", time.gmtime(now))
    return calendar.timegm(time.strptime(today, "%Y-%m-%d"))


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
    """Redis-backed cost storage with SQLite + in-memory fallback."""

    def __init__(self) -> None:
        self._redis: Redis | None = None
        self._mem_sessions: dict[str, dict] = {}
        self._mem_subagents: dict[str, list[dict]] = {}

    async def _get_redis(self) -> Redis | None:
        if self._redis is None:
            try:
                self._redis = Redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)
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
        persisted = False

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
                persisted = True
            except (RedisError, RuntimeError) as exc:
                logger.warning("CostStore record_subagent_cost Redis error: %s", exc)

        # SQLite write-through (durable copy alongside Redis)
        db = await get_sqlite_connection()
        if db is not None:
            try:
                await db.execute(
                    "INSERT INTO costs_subagent (thread_id, subagent_name, input_tokens, output_tokens, cost_usd, model_used, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (thread_id, subagent_name, input_tokens, output_tokens, cost_usd, model_used, ts),
                )
                await db.commit()
                persisted = True
            except Exception as exc:  # noqa: BLE001
                logger.warning("CostStore record_subagent_cost SQLite error: %s", exc)

        if not persisted:
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
        # Keep the original session start — resetting it on every update
        # mis-attributes spend to the last update time (budget caps and the
        # hourly circuit breaker both key off created_at).
        existing = await self.get_session_cost(thread_id)
        created_at = existing["created_at"] if existing else now
        data = {
            "thread_id": thread_id,
            "user_id": user_id,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_cost_usd": total_cost_usd,
            "efficiency_ratio": efficiency_ratio,
            "budget_limit_usd": budget_limit_usd,
            "budget_reached": "1" if budget_reached else "0",
            "created_at": str(created_at),
        }
        daily_key = f"costs:daily:{time.strftime('%Y-%m-%d', time.gmtime(now))}"

        persisted = False

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
                persisted = True
            except (RedisError, RuntimeError) as exc:
                logger.warning("CostStore update_session_total Redis error: %s", exc)

        # SQLite write-through (durable copy alongside Redis)
        db = await get_sqlite_connection()
        if db is not None:
            try:
                await db.execute(
                    "INSERT OR REPLACE INTO costs_session (thread_id, user_id, total_input_tokens, total_output_tokens, total_cost_usd, efficiency_ratio, budget_limit_usd, budget_reached, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (thread_id, user_id, total_input_tokens, total_output_tokens, total_cost_usd, efficiency_ratio, budget_limit_usd, 1 if budget_reached else 0, created_at),
                )
                await db.commit()
                persisted = True
            except Exception as exc:  # noqa: BLE001
                logger.warning("CostStore update_session_total SQLite error: %s", exc)

        if not persisted:
            self._mem_sessions[thread_id] = data

    async def get_session_cost(self, thread_id: str) -> dict | None:
        """Get the session-level cost summary for a thread."""
        r = await self._get_redis()
        if r is not None:
            try:
                data = await r.hgetall(f"costs:session:{thread_id}")
                if data:
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

        # SQLite — checked even when Redis is up but has no copy
        db = await get_sqlite_connection()
        if db is not None:
            try:
                cur = await db.execute(
                    "SELECT * FROM costs_session WHERE thread_id = ?", (thread_id,)
                )
                row = await cur.fetchone()
                if row:
                    return {
                        "thread_id": row["thread_id"],
                        "user_id": row["user_id"] or "",
                        "total_input_tokens": int(row["total_input_tokens"] or 0),
                        "total_output_tokens": int(row["total_output_tokens"] or 0),
                        "total_cost_usd": float(row["total_cost_usd"] or 0.0),
                        "efficiency_ratio": float(row["efficiency_ratio"] or 0.0),
                        "budget_limit_usd": float(row["budget_limit_usd"] or 0.0),
                        "budget_reached": bool(row["budget_reached"]),
                        "created_at": float(row["created_at"] or 0),
                    }
                return None
            except Exception as exc:  # noqa: BLE001
                logger.warning("CostStore get_session_cost SQLite error: %s", exc)

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
        """Get per-subagent cost breakdown for a thread, merged across all stores."""
        merged: dict[tuple, dict] = {}

        r = await self._get_redis()
        if r is not None:
            try:
                raw = await r.hgetall(f"costs:subagent:{thread_id}")
                for value in raw.values():
                    try:
                        entry = json.loads(value)
                    except (json.JSONDecodeError, TypeError):
                        continue
                    key = (entry.get("subagent_name"), entry.get("timestamp"))
                    merged[key] = entry
            except (RedisError, RuntimeError) as exc:
                logger.warning("CostStore get_subagent_breakdown Redis error: %s", exc)

        db = await get_sqlite_connection()
        if db is not None:
            try:
                cur = await db.execute(
                    "SELECT * FROM costs_subagent WHERE thread_id = ?", (thread_id,)
                )
                rows = await cur.fetchall()
                for row in rows:
                    entry = {
                        "subagent_name": row["subagent_name"],
                        "input_tokens": int(row["input_tokens"] or 0),
                        "output_tokens": int(row["output_tokens"] or 0),
                        "cost_usd": float(row["cost_usd"] or 0.0),
                        "model_used": row["model_used"] or "",
                        "timestamp": float(row["timestamp"] or 0),
                    }
                    merged.setdefault((entry["subagent_name"], entry["timestamp"]), entry)
            except Exception as exc:  # noqa: BLE001
                logger.warning("CostStore get_subagent_breakdown SQLite error: %s", exc)

        for entry in self._mem_subagents.get(thread_id, []):
            merged.setdefault((entry.get("subagent_name"), entry.get("timestamp")), entry)

        results = list(merged.values())
        results.sort(key=lambda x: x.get("timestamp", 0))
        return results

    async def _all_sessions(self) -> dict[str, dict]:
        """Merge session cost records from all stores, keyed by thread_id.

        When the same thread exists in multiple stores, the record with the
        highest total_cost_usd wins (costs are cumulative, so max = freshest).
        """
        merged: dict[str, dict] = {}

        def _merge(tid: str, data: dict) -> None:
            cur = merged.get(tid)
            if cur is None or float(data.get("total_cost_usd", 0)) >= float(cur.get("total_cost_usd", 0)):
                merged[tid] = data

        r = await self._get_redis()
        if r is not None:
            try:
                thread_ids = await r.zrange("costs:index", 0, -1)
                if thread_ids:
                    pipe = r.pipeline()
                    for tid in thread_ids:
                        pipe.hgetall(f"costs:session:{tid}")
                    sessions_raw = await pipe.execute()
                    for tid, data in zip(thread_ids, sessions_raw, strict=False):
                        if data:
                            _merge(tid, dict(data))
            except (RedisError, RuntimeError) as exc:
                logger.warning("CostStore _all_sessions Redis error: %s", exc)

        db = await get_sqlite_connection()
        if db is not None:
            try:
                cur = await db.execute("SELECT * FROM costs_session")
                for row in await cur.fetchall():
                    _merge(row["thread_id"], {
                        "thread_id": row["thread_id"],
                        "user_id": row["user_id"] or "",
                        "total_input_tokens": int(row["total_input_tokens"] or 0),
                        "total_output_tokens": int(row["total_output_tokens"] or 0),
                        "total_cost_usd": float(row["total_cost_usd"] or 0.0),
                        "efficiency_ratio": float(row["efficiency_ratio"] or 0.0),
                        "budget_reached": "1" if row["budget_reached"] else "0",
                        "created_at": str(row["created_at"] or 0),
                    })
            except Exception as exc:  # noqa: BLE001
                logger.warning("CostStore _all_sessions SQLite error: %s", exc)

        for tid, data in self._mem_sessions.items():
            _merge(tid, data)

        return merged

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

        merged = await self._all_sessions()
        sessions = [
            self._normalize_session(data)
            for data in merged.values()
            if float(data.get("created_at", 0)) >= start_ts
        ]
        subagent_entries = await self._all_subagent_entries()
        return self._compute_stats(sessions, subagent_entries)

    async def _all_subagent_entries(self) -> list[dict]:
        """Merge subagent cost entries across all stores (deduped)."""
        merged: dict[tuple, dict] = {}

        def _add(tid: str, entry: dict) -> None:
            key = (tid, entry.get("subagent_name"), entry.get("timestamp"))
            merged[key] = entry

        r = await self._get_redis()
        if r is not None:
            try:
                thread_ids = await r.zrange("costs:index", 0, -1)
                if thread_ids:
                    pipe = r.pipeline()
                    for tid in thread_ids:
                        pipe.hgetall(f"costs:subagent:{tid}")
                    for tid, raw in zip(thread_ids, await pipe.execute(), strict=False):
                        for value in raw.values():
                            try:
                                _add(tid, json.loads(value))
                            except (json.JSONDecodeError, TypeError):
                                continue
            except (RedisError, RuntimeError) as exc:
                logger.warning("CostStore _all_subagent_entries Redis error: %s", exc)

        db = await get_sqlite_connection()
        if db is not None:
            try:
                cur = await db.execute("SELECT * FROM costs_subagent")
                for row in await cur.fetchall():
                    _add(row["thread_id"], {
                        "subagent_name": row["subagent_name"],
                        "input_tokens": int(row["input_tokens"] or 0),
                        "output_tokens": int(row["output_tokens"] or 0),
                        "cost_usd": float(row["cost_usd"] or 0.0),
                        "model_used": row["model_used"] or "",
                        "timestamp": float(row["timestamp"] or 0),
                    })
            except Exception as exc:  # noqa: BLE001
                logger.warning("CostStore _all_subagent_entries SQLite error: %s", exc)

        for tid, entries in self._mem_subagents.items():
            for entry in entries:
                _add(tid, entry)

        return list(merged.values())

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

    def _compute_stats(
        self,
        sessions: list[dict],
        subagent_entries: list[dict],
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
        for entry in subagent_entries:
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

    # ------------------------------------------------------------------
    # Phase 7.2: Daily cost cap + circuit breaker
    # ------------------------------------------------------------------

    async def get_user_daily_spend(self, user_id: str) -> float:
        """Return total USD spent by *user_id* since UTC midnight."""
        now = time.time()
        start_of_day = _utc_start_of_day(now)

        merged = await self._all_sessions()
        total = 0.0
        for data in merged.values():
            if data.get("user_id", "") != user_id:
                continue
            created = float(data.get("created_at", 0))
            if created >= start_of_day:
                total += float(data.get("total_cost_usd", 0.0))
        return round(total, 6)

    async def check_daily_budget(self, user_id: str) -> tuple[bool, float, float]:
        """Check if user is within their daily cost cap.

        Returns ``(within_budget, spent, cap)``.
        """
        spent = await self.get_user_daily_spend(user_id)
        cap = settings.DAILY_COST_CAP_USD
        return (spent < cap, round(spent, 6), cap)

    async def get_hourly_platform_spend(self) -> float:
        """Return total USD spent across all users in the last hour."""
        one_hour_ago = time.time() - 3600

        merged = await self._all_sessions()
        total = 0.0
        for data in merged.values():
            created = float(data.get("created_at", 0))
            if created >= one_hour_ago:
                total += float(data.get("total_cost_usd", 0.0))
        return round(total, 6)

    async def check_circuit_breaker(self) -> tuple[bool, float, float]:
        """Check if the global circuit breaker is tripped.

        Returns ``(tripped, spent, cap)``.
        """
        if not settings.CIRCUIT_BREAKER_ENABLED:
            spent = await self.get_hourly_platform_spend()
            return (False, spent, settings.HOURLY_PLATFORM_CAP_USD)
        spent = await self.get_hourly_platform_spend()
        cap = settings.HOURLY_PLATFORM_CAP_USD
        return (spent >= cap, round(spent, 6), cap)

    # ------------------------------------------------------------------
    # Phase 7.4: Live cost monitoring + alerting
    # ------------------------------------------------------------------

    async def get_live_costs(self, hours: int = 24) -> list[dict]:
        """Return per-hour cost breakdown for the last N hours.

        Each entry: ``{hour: "2024-01-15T14:00", cost: 0.12, requests: 3,
        tokens_in: 1200, tokens_out: 800}``.
        """
        now = time.time()
        start_ts = now - (hours * 3600)

        merged = await self._all_sessions()
        hour_buckets: dict[str, dict] = {}
        for data in merged.values():
            created = float(data.get("created_at", 0))
            if created < start_ts:
                continue
            hour_key = time.strftime("%Y-%m-%dT%H:00", time.gmtime(created))
            bucket = hour_buckets.setdefault(hour_key, {
                "hour": hour_key,
                "cost": 0.0,
                "requests": 0,
                "tokens_in": 0,
                "tokens_out": 0,
            })
            bucket["cost"] += float(data.get("total_cost_usd", 0.0))
            bucket["requests"] += 1
            bucket["tokens_in"] += int(data.get("total_input_tokens", 0))
            bucket["tokens_out"] += int(data.get("total_output_tokens", 0))

        result = sorted(hour_buckets.values(), key=lambda x: x["hour"])
        for entry in result:
            entry["cost"] = round(entry["cost"], 6)
        return result

    async def check_platform_alerts(self) -> dict:
        """Check daily platform spend against alert thresholds.

        Returns ``{level, daily_spend, daily_cap, percentage, message}``.
        Level is "ok", "warning", or "critical".
        """
        # Daily cap = hourly cap * 24 (approximate daily platform cap)
        daily_cap = settings.HOURLY_PLATFORM_CAP_USD * 24
        now = time.time()
        start_of_day = _utc_start_of_day(now)

        merged = await self._all_sessions()
        daily_spend = 0.0
        for data in merged.values():
            created = float(data.get("created_at", 0))
            if created >= start_of_day:
                daily_spend += float(data.get("total_cost_usd", 0.0))

        daily_spend = round(daily_spend, 6)
        percentage = (daily_spend / daily_cap * 100) if daily_cap > 0 else 0.0
        threshold = settings.ALERT_DAILY_THRESHOLD_PCT

        if percentage >= 100:
            level = "critical"
            message = f"Daily platform spend ${daily_spend:.2f} has exceeded the cap ${daily_cap:.2f}"
        elif percentage >= threshold * 100:
            level = "warning"
            message = f"Daily platform spend ${daily_spend:.2f} has reached {percentage:.1f}% of the cap ${daily_cap:.2f}"
        else:
            level = "ok"
            message = "Spend within normal range"

        return {
            "level": level,
            "daily_spend": daily_spend,
            "daily_cap": daily_cap,
            "percentage": round(percentage, 1),
            "message": message,
        }


cost_store = CostStore()
