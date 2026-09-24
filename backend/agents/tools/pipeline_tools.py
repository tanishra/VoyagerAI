"""Pipeline tools — the orchestrator's contract with the deterministic layer.

generate_trip_plans / refine_itinerary are ordinary tools from the model's
perspective, but internally they run the full deterministic pipeline
(research fan-out → structured generation → code validation → reconcile)
and park the resulting payload in a side channel. The model receives only a
compact summary — it narrates, it never rewrites the plan data.

Context (thread_id, locale, cancel_event, budget check) arrives via
ContextVars set at stream start — same mechanism as visuals.py.
"""

from __future__ import annotations

import asyncio
import contextvars
import json
import logging
from typing import Callable, Literal

from langchain_core.tools import tool

from agents.constraints import TripConstraints
from agents.pipeline import (
    PIPELINE_TOOL_NAMES,
    get_latest_comparison,
    is_pipeline_tool,
    pop_payload,
    run_comparison_pipeline,
    run_refinement_pipeline,
    store_payload,
)
from agents.tools.visuals import get_current_thread_id
from payload_store import payload_store

logger = logging.getLogger("travel_agent.tools.pipeline")

__all__ = [
    "PIPELINE_TOOL_NAMES",
    "get_pipeline_tools",
    "is_pipeline_tool",
    "pop_payload",
    "get_latest_comparison",
    "set_pipeline_context",
]


_pipeline_locale: contextvars.ContextVar[str] = contextvars.ContextVar(
    "pipeline_locale", default="en"
)
_pipeline_cancel: contextvars.ContextVar[asyncio.Event | None] = contextvars.ContextVar(
    "pipeline_cancel", default=None
)
_pipeline_budget_check: contextvars.ContextVar[Callable[[], bool] | None] = contextvars.ContextVar(
    "pipeline_budget_check", default=None
)
# Constraints extracted deterministically from the user's actual messages —
# used to catch tool args the model invented or misheard.
_pipeline_stated: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "pipeline_stated", default=None
)
# Last constraints the pipeline ran with — refine_itinerary reuses them so
# the orchestrator doesn't have to re-state every field on tier selection.
# Stored per-thread in payload_store (Redis + TTL) so restarts don't lose them.
async def _get_last_constraints(thread_id: str) -> TripConstraints | None:
    data = await payload_store.get_thread_state(thread_id, "constraints")
    if not isinstance(data, dict):
        return None
    try:
        return TripConstraints.model_validate(data)
    except Exception:
        return None


def set_pipeline_context(
    *,
    locale: str | None = None,
    cancel_event: asyncio.Event | None = None,
    budget_check: Callable[[], bool] | None = None,
    stated_constraints: dict | None = None,
) -> None:
    """Bind pipeline context for the current stream (called once per request)."""
    if locale:
        _pipeline_locale.set(locale)
    _pipeline_cancel.set(cancel_event)
    _pipeline_budget_check.set(budget_check)
    _pipeline_stated.set(stated_constraints)


def get_pipeline_tools() -> list:
    return [generate_trip_plans, refine_itinerary]


def _budget_reached_msg() -> str:
    return (
        "Plan generation is unavailable: the session budget limit was reached. "
        "Tell the user politely and suggest they continue later."
    )


def _check_against_stated(constraints: TripConstraints, stated: dict | None) -> str | None:
    """Reject tool args that contradict what the user actually wrote.

    Only a *conflicting* stated value blocks — a field the user never
    mentioned in text can't produce a false positive.
    """
    if not stated:
        return None
    stated_days = stated.get("days")
    if stated_days is not None and stated_days != constraints.total_days:
        return (
            f"The user asked for {stated_days} days, but the constraints say "
            f"{constraints.total_days}. Confirm the trip length with the user "
            "before generating."
        )
    stated_budget = stated.get("budget_amount")
    stated_currency = stated.get("budget_currency")
    if stated_budget is not None:
        # ±5% tolerance — rounding like "50k" vs 50000 shouldn't trip this.
        if abs(stated_budget - constraints.budget_amount) > stated_budget * 0.05:
            return (
                f"The user stated a total budget of {stated_budget:,.0f} "
                f"{stated_currency or ''}, but the constraints say "
                f"{constraints.budget_amount:,.0f} {constraints.budget_currency}. "
                "Confirm the budget with the user before generating."
            )
        if stated_currency and stated_currency != constraints.budget_currency:
            return (
                f"The user wrote amounts in {stated_currency}, but the "
                f"constraints say {constraints.budget_currency}. Confirm the "
                "currency with the user before generating."
            )
    return None


@tool
async def generate_trip_plans(constraints: TripConstraints) -> str:
    """Generate three budget-tiered travel plan summaries (budget / balanced / premium).

    Call this ONLY when you know every required field. The arguments are a
    strict contract — if you don't know a value (e.g. trip length or total
    budget), ask the user instead of guessing. budget_amount is the TOTAL
    trip budget, never a per-day figure.

    The full plan data is delivered to the user's UI directly — you only
    need to write a short conversational summary comparing the tiers and
    ask which one they prefer. NEVER output plan JSON yourself.

    Args:
        constraints: The complete trip requirements gathered from the conversation.
    """
    thread_id = get_current_thread_id()
    budget_check = _pipeline_budget_check.get()
    cancel_event = _pipeline_cancel.get()
    locale = _pipeline_locale.get()

    if budget_check is not None and budget_check():
        return _budget_reached_msg()

    mismatch = _check_against_stated(constraints, _pipeline_stated.get())
    if mismatch:
        logger.warning(
            "generate_trip_plans rejected: tool args contradict user message (%s)",
            mismatch,
        )
        return mismatch

    result = await run_comparison_pipeline(
        constraints,
        locale=locale,
        cancel_event=cancel_event,
        budget_check=budget_check,
    )
    if result is None:
        if cancel_event is not None and cancel_event.is_set():
            return "Plan generation was cancelled."
        return (
            "Plan generation failed internally. Apologize briefly and ask the "
            "user if they'd like to try again."
        )

    comparison, stage_usage = result
    await payload_store.set_thread_state(thread_id, "constraints", constraints.model_dump())
    payload_id = await store_payload(thread_id, "comparison", comparison)

    totals = []
    for plan in comparison.get("plans", []):
        it = plan.get("itinerary", {}) if isinstance(plan, dict) else {}
        total = it.get("estimated_total_cost_usd")
        if isinstance(plan, dict) and plan.get("tier") and total is not None:
            totals.append(f"{plan['tier']} {total:,.0f} {constraints.budget_currency}")
    summary = "; ".join(totals) if totals else "3 tiers"

    return json.dumps({
        "_pipeline_payload_id": payload_id,
        "_stage_usage": stage_usage,
        "message": (
            f"Plans generated ({summary}). Briefly compare the tiers in plain "
            "language and ask the user which they'd like to see in detail. "
            "Do NOT output any JSON or plan data yourself."
        ),
    })


@tool
async def refine_itinerary(
    tier: Literal["budget", "balanced", "premium"],
    adjustments: str | None = None,
) -> str:
    """Generate the complete day-by-day itinerary for the tier the user selected.

    Call this when the user picks a plan tier (or asks for changes to an
    existing itinerary — pass their requested changes as `adjustments`).
    The full itinerary is delivered to the user's UI directly; write a short
    conversational summary and ask if they want any changes. NEVER output
    itinerary JSON yourself.

    Args:
        tier: Which plan tier to expand (budget / balanced / premium).
        adjustments: Optional user-requested changes to fold into the itinerary.
    """
    thread_id = get_current_thread_id()
    budget_check = _pipeline_budget_check.get()
    cancel_event = _pipeline_cancel.get()
    locale = _pipeline_locale.get()

    if budget_check is not None and budget_check():
        return _budget_reached_msg()

    constraints = await _get_last_constraints(thread_id)
    if constraints is None:
        return (
            "No trip constraints are on record for this conversation — ask the "
            "user for destination, duration, and budget, then call "
            "generate_trip_plans first."
        )

    result = await run_refinement_pipeline(
        constraints,
        tier,
        adjustments,
        locale=locale,
        cancel_event=cancel_event,
        budget_check=budget_check,
    )
    if result is None:
        if cancel_event is not None and cancel_event.is_set():
            return "Itinerary generation was cancelled."
        return (
            "Itinerary generation failed internally. Apologize briefly and ask "
            "the user if they'd like to try again."
        )

    itinerary, stage_usage = result
    payload_id = await store_payload(thread_id, "itinerary", itinerary)
    total = itinerary.get("estimated_total_cost_usd")
    total_text = f"{total:,.0f} {constraints.budget_currency}" if total else "unknown total"

    return json.dumps({
        "_pipeline_payload_id": payload_id,
        "_stage_usage": stage_usage,
        "message": (
            f"A {constraints.total_days}-day {tier} itinerary for "
            f"{constraints.destination} is ready (total ~{total_text}). "
            "Summarize the highlights briefly and ask if the user wants any "
            "changes. Do NOT output any JSON or itinerary data yourself."
        ),
    })


def _reset_for_tests() -> None:
    payload_store._mem.clear()
    payload_store._redis = None
    payload_store._redis_retry_after = 0.0
