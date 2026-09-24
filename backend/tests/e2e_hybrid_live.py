"""Live E2E verification of the hybrid pipeline against real LLMs.

NOT a pytest test — real API calls, real money. Run manually:

    cd backend && conda run -n deepagents python tests/e2e_hybrid_live.py

Requires real OPENAI_API_KEY / TAVILY_API_KEY / REDIS_URL in .env.
Prints PASS/FAIL per scenario and exits non-zero on any failure.
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid

sys.path.insert(0, ".")

from dotenv import load_dotenv  # noqa: E402

load_dotenv()  # litellm reads keys from os.environ, not the settings object

from agents.deep_agent import stream_chat_agent  # noqa: E402
from config.settings import settings  # noqa: E402

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  {PASS if cond else FAIL} {name}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)


def _chunk_text(chunk) -> str:
    c = getattr(chunk, "content", None)
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "".join(
            b.get("text", "") for b in c
            if isinstance(b, dict) and b.get("type") in ("text", "text-delta")
        )
    return ""


async def collect(agen, cancel_after_events: int | None = None, cancel_event=None):
    events = []
    async for ev in agen:
        events.append(ev)
        if ev["event"] == "on_chat_model_stream":
            text = _chunk_text(ev.get("data", {}).get("chunk"))
            if text:
                events.append({"event": "token", "data": text})
                print(f"    · token: {text[:80]}", flush=True)
                continue
        d = ev.get("data")
        preview = (d[:80] if isinstance(d, str) else str(type(d).__name__))
        print(f"    · {ev['event']}: {preview}", flush=True)
        if cancel_after_events and cancel_event and len(events) >= cancel_after_events:
            cancel_event.set()
    return events


def kinds(events):
    return [e["event"] for e in events]


async def scenario_happy_path():
    """5-day Delhi ₹50k pure veg → comparison card with consistent facts."""
    print("\n== Scenario 1: comparison generation ==")
    tid = f"e2e-{uuid.uuid4().hex[:8]}"
    events = await collect(stream_chat_agent(
        "Plan a 5-day trip to Delhi for 2 friends. Total budget ₹50,000. "
        "We're pure vegetarian. Balanced travel style.",
        tid, "e2e-user", locale="en", currency="INR",
    ))
    k = kinds(events)
    comp = next((e["data"] for e in events if e["event"] == "comparison"), None)
    check("comparison event emitted", comp is not None, f"events: {k}")
    if comp is None:
        return None
    check("3 plans", len(comp.get("plans", [])) == 3)
    for plan in comp.get("plans", []):
        it = plan.get("itinerary", {})
        check(f"{plan.get('tier')} total_days==5", it.get("total_days") == 5)
        check(f"{plan.get('tier')} currency==INR", it.get("currency") == "INR")
    totals = comp.get("comparison_matrix", {}).get("total_cost", {})
    for plan in comp.get("plans", []):
        tier = plan["tier"]
        it_total = plan["itinerary"].get("estimated_total_cost_usd")
        check(f"{tier} matrix==card total",
              totals.get(tier) is not None and abs(totals[tier] - it_total) < it_total * 0.05,
              f"matrix={totals.get(tier)} card={it_total}")
        cb_total = (plan.get("cost_breakdown") or {}).get("total")
        check(f"{tier} breakdown==card total",
              cb_total is None or abs(cb_total - it_total) < it_total * 0.05,
              f"breakdown={cb_total} card={it_total}")
    balanced = next((p for p in comp["plans"] if p["tier"] == "balanced"), None)
    check("balanced within ₹50k±5%",
          balanced is not None and balanced["itinerary"]["estimated_total_cost_usd"] <= 50000 * 1.05,
          f"balanced={balanced and balanced['itinerary'].get('estimated_total_cost_usd')}")
    check("prose tokens streamed", "token" in k)
    check("progress events", any(e["event"] == "subagent_progress" for e in events))
    return tid


async def scenario_tier_select(tid):
    """Follow-up turn → full itinerary, exactly 5 days, INR, sums consistent."""
    print("\n== Scenario 2: tier selection → full itinerary ==")
    events = await collect(stream_chat_agent(
        "Show me the balanced plan in detail.", tid, "e2e-user", locale="en", currency="INR",
    ))
    it = next((e["data"] for e in events if e["event"] == "itinerary"), None)
    check("itinerary event emitted", it is not None, f"events: {kinds(events)}")
    if it is None:
        return
    check("exactly 5 days", len(it.get("days", [])) == 5, f"got {len(it.get('days', []))}")
    check("currency INR", it.get("currency") == "INR", it.get("currency"))
    day_sum = sum(d.get("daily_cost_usd") or 0 for d in it.get("days", []))
    total = it.get("estimated_total_cost_usd") or 0
    check("daily costs ≈ total", total > 0 and abs(day_sum - total) <= total * 0.05,
          f"sum={day_sum} total={total}")


async def scenario_missing_fields():
    """Vague request → model asks questions instead of calling the tool."""
    print("\n== Scenario 3: missing fields → clarification ==")
    tid = f"e2e-{uuid.uuid4().hex[:8]}"
    events = await collect(stream_chat_agent(
        "plan a trip to japan", tid, "e2e-user", locale="en",
    ))
    k = kinds(events)
    comp = any(e["event"] == "comparison" for e in events)
    tool_started = any(
        e["event"] == "subagent_progress" or
        (e["event"] == "status" and "generate_trip_plans" in str(e.get("data", "")))
        for e in events
    )
    check("no comparison generated", not comp)
    check("no pipeline tool call", not tool_started, str(k))
    tokens = "".join(e["data"] for e in events if e["event"] == "token" and isinstance(e["data"], str))
    check("clarifying question asked", "?" in tokens, f"tokens: {tokens[:120]}")


async def scenario_persistence(tid):
    """Payload + constraints landed in Redis, readable after 'restart'."""
    print("\n== Scenario 4: Redis persistence ==")
    try:
        from redis.asyncio import Redis
        from config import REDIS_URL
        r = Redis.from_url(REDIS_URL, decode_responses=True,
                           socket_connect_timeout=3, socket_timeout=3)
        keys = await r.keys(f"pipeline:thread:{tid}:*")
        check("thread state in Redis", len(keys) >= 1, f"keys={keys}")
        for kk in keys:
            ttl = await r.ttl(kk)
            check(f"TTL set on {kk.split(':')[-1]}", ttl > 0, f"ttl={ttl}")
        raw = await r.get(f"pipeline:thread:{tid}:constraints")
        check("constraints stored", raw is not None and "Delhi" in raw, raw)
        await r.aclose()
    except Exception as exc:
        check("redis reachable", False, str(exc))


async def scenario_cancel():
    """Cancel mid-pipeline → cancelled event, no partial card."""
    print("\n== Scenario 5: cancellation ==")
    tid = f"e2e-{uuid.uuid4().hex[:8]}"
    cancel = asyncio.Event()
    events = []
    gen = stream_chat_agent(
        "Plan a 7-day trip to Tokyo for a couple. Budget $3000 total. Balanced.",
        tid, "e2e-user", locale="en",
        cancel_event=cancel,
    )
    async for ev in gen:
        events.append(ev)
        # Cancel as soon as the pipeline tool starts working
        if ev["event"] == "subagent_progress" and not cancel.is_set():
            cancel.set()
    k = kinds(events)
    check("cancelled event", "cancelled" in k, str(k))
    check("no comparison card after cancel", "comparison" not in k)


async def main():
    tid = await scenario_happy_path()
    if tid:
        await scenario_tier_select(tid)
        await scenario_persistence(tid)
    await scenario_missing_fields()
    await scenario_cancel()

    print("\n" + ("=" * 50))
    if failures:
        print(f"{len(failures)} FAILURES: {failures}")
        sys.exit(1)
    print("ALL LIVE E2E SCENARIOS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
