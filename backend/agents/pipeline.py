"""Deterministic plan-generation pipeline.

The orchestrator (an LLM) decides WHEN to plan — by calling the
generate_trip_plans / refine_itinerary tools. This module decides HOW:
research fan-out, plan generation, code validation, and reconciliation run
in a fixed order with typed inputs/outputs. The model never re-emits the
plan JSON — the full payload is parked in a thread-keyed side channel and
streamed to the frontend by the stream layer (mirrors the pending-visuals
pattern in agents/tools/visuals.py).

Every stage is timeout-guarded and non-throwing: a failed specialist
degrades to a gap note, a failed generation degrades to None (the tool then
returns a graceful message for the orchestrator to relay).
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any, Literal

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from agents.constraints import TripConstraints
from agents.llm import get_subagent_model
from payload_store import payload_store
from agents.prompts import (
    CONSTRAINT_ANALYZER_SYSTEM_PROMPT,
    LANGUAGE_INSTRUCTIONS,
    COMPARISON_SUMMARY_PROMPT,
    SINGLE_TIER_REGEN_PROMPT,
    RESEARCHER_SYSTEM_PROMPT,
    RISK_DETECTOR_SYSTEM_PROMPT,
)
from agents.tools.internet import get_internet_tools
from agents.validation import Issue, validate_comparison, validate_itinerary

logger = logging.getLogger("travel_agent.pipeline")

PIPELINE_TOOL_NAMES = frozenset({"generate_trip_plans", "refine_itinerary", "ask_clarifying_questions"})

# Per-stage ceilings — generous enough for real research, bounded so a hung
# provider can't stall the whole stream forever.
_SPECIALIST_TIMEOUT_S = 120
_GENERATOR_TIMEOUT_S = 180
_MAX_GENERATION_ATTEMPTS = 2  # initial + one bounded retry with issue feedback


def is_pipeline_tool(name: str) -> bool:
    return name in PIPELINE_TOOL_NAMES


# ---------------------------------------------------------------------------
# Side channel — full payloads never enter the model's context
#
# Storage lives in payload_store (Redis + TTL, bounded memory fallback) so a
# backend restart between the tool call and the SSE pop doesn't lose cards,
# and long-running processes can't leak unbounded payload memory.
# ---------------------------------------------------------------------------


async def store_payload(thread_id: str, kind: str, data: dict) -> str:
    payload_id = uuid.uuid4().hex
    await payload_store.store(payload_id, kind, data)
    if thread_id:
        # Durable per-id record so history can re-attach the card on reload —
        # the one-shot key above is consumed on delivery and is gone by then.
        await payload_store.set_thread_state(
            thread_id, f"payload:{payload_id}", {"kind": kind, "data": data}
        )
        await payload_store.set_thread_state(thread_id, f"latest_{kind}", data)
        await payload_store.set_thread_state(thread_id, f"latest_{kind}_id", payload_id)
    return payload_id


async def pop_payload(payload_id: str) -> dict | None:
    """Retrieve and remove a pending payload (one-shot delivery)."""
    return await payload_store.pop(payload_id)


async def get_latest_comparison(thread_id: str) -> dict | None:
    return await payload_store.get_thread_state(thread_id, "latest_comparison")


def _reset_for_tests() -> None:
    payload_store._mem.clear()


# ---------------------------------------------------------------------------
# Structured output schemas — the model fills these; code validates them
# ---------------------------------------------------------------------------


class PlanItineraryStub(BaseModel):
    """Summary-only itinerary for comparison cards — no day-by-day detail."""

    destination: str
    total_days: int
    currency: str
    estimated_total_cost_usd: float
    budget_status: Literal["within", "over", "under"] | None = None


class ComparisonPlan(BaseModel):
    tier: Literal["budget", "balanced", "premium"]
    itinerary: PlanItineraryStub
    cost_breakdown: dict | None = None
    highlights: list[str] = Field(default_factory=list)
    tradeoffs: list[str] = Field(default_factory=list)


class ComparisonSummary(BaseModel):
    plans: list[ComparisonPlan]
    comparison_matrix: dict | None = None


class DaySlot(BaseModel):
    activity: str
    location: str | None = None
    cost_usd: float | None = None
    duration: str | None = None


class ItineraryDay(BaseModel):
    day: int
    theme: str | None = None
    morning: DaySlot | None = None
    afternoon: DaySlot | None = None
    evening: DaySlot | None = None
    transport: str | None = None
    accommodation: str | None = None
    daily_cost_usd: float | None = None
    tips: list[str] = Field(default_factory=list)


class ItineraryPlan(BaseModel):
    destination: str
    total_days: int
    currency: str
    estimated_total_cost_usd: float
    budget_status: Literal["within", "over", "under"] | None = None
    visa_note: str | None = None
    best_season_note: str | None = None
    days: list[ItineraryDay]
    warnings: list[str] = Field(default_factory=list)
    packing_essentials: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Stage runners
# ---------------------------------------------------------------------------


def _last_ai_text(messages: list) -> str:
    for msg in reversed(messages):
        if getattr(msg, "type", "") == "ai":
            content = msg.content
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return " ".join(
                    p.get("text", "") for p in content
                    if isinstance(p, dict) and p.get("type") in ("text", "text-delta")
                )
    return ""


def _usage_of(messages: list) -> dict:
    """Sum usage_metadata across AI messages in an agent result."""
    total = {"input_tokens": 0, "output_tokens": 0, "model": ""}
    for msg in messages:
        usage = getattr(msg, "usage_metadata", None)
        if not isinstance(usage, dict):
            continue
        total["input_tokens"] += usage.get("input_tokens") or 0
        total["output_tokens"] += usage.get("output_tokens") or 0
        meta = getattr(msg, "response_metadata", None) or {}
        total["model"] = meta.get("model_name") or meta.get("model") or total["model"]
    return total


async def _run_specialist(
    name: str,
    system_prompt: str,
    task_text: str,
    tools: list | None = None,
) -> tuple[str, dict]:
    """Compile a specialist subagent directly and run it to completion.

    Same prompts, same tools, same models as the task-tool dispatch — just
    invoked by code instead of by the orchestrator's choice. Failure returns
    a gap note, matching the _ResilientModel semantics. Returns (brief text,
    token usage) so the caller can attribute cost per stage.
    """
    try:
        agent = create_agent(
            model=get_subagent_model(name),
            tools=tools or [],
            system_prompt=system_prompt,
        )
        result = await asyncio.wait_for(
            agent.ainvoke({"messages": [HumanMessage(content=task_text)]}),
            timeout=_SPECIALIST_TIMEOUT_S,
        )
        messages = result.get("messages", [])
        return _last_ai_text(messages), _usage_of(messages)
    except Exception as exc:
        logger.warning("Pipeline specialist '%s' failed: %s", name, exc)
        return f"[{name} unavailable — proceed with remaining context]", _usage_of([])


async def _generate_structured(
    schema: type[BaseModel],
    system_prompt: str,
    task_text: str,
    stage_name: str,
) -> tuple[dict | None, dict]:
    """One structured-output generation call. Returns (model_dump(), usage)."""
    try:
        model = get_subagent_model(stage_name)
        # include_raw so token usage survives — the parsed object alone
        # carries no usage_metadata.
        # strict=False: OpenAI strict mode rejects schemas whose objects have
        # optional fields ("required" must list every property). Non-strict
        # json_schema still constrains output shape; Pydantic validates after.
        structured = model.with_structured_output(
            schema, method="json_schema", strict=False, include_raw=True
        )
        result = await asyncio.wait_for(
            structured.ainvoke(
                [
                    ("system", system_prompt),
                    ("user", task_text),
                ]
            ),
            timeout=_GENERATOR_TIMEOUT_S,
        )
        parsed = result.get("parsed") if isinstance(result, dict) else result
        raw = result.get("raw") if isinstance(result, dict) else None
        usage = _usage_of([raw]) if raw is not None else _usage_of([])
        if parsed is None:
            perr = result.get("parsing_error") if isinstance(result, dict) else None
            logger.warning(
                "Pipeline stage '%s' returned unparseable output: %r",
                stage_name, perr,
            )
        return (parsed.model_dump() if parsed is not None else None), usage
    except Exception as exc:
        logger.warning("Pipeline stage '%s' generation failed: %r", stage_name, exc)
        return None, _usage_of([])


def _constraints_block(constraints: TripConstraints) -> str:
    lines = [
        f"Destination: {constraints.destination}",
        f"Duration: {constraints.total_days} days",
        f"Total budget: {constraints.budget_amount:,.0f} {constraints.budget_currency}",
        f"Travel style: {constraints.travel_style}",
        f"Group: {constraints.group_type}",
    ]
    if constraints.dietary_restrictions:
        lines.append(f"Dietary restrictions: {', '.join(constraints.dietary_restrictions)}")
    if constraints.accessibility_needs:
        lines.append(f"Accessibility needs: {', '.join(constraints.accessibility_needs)}")
    return "\n".join(lines)


def _language_block(locale: str | None) -> str:
    return LANGUAGE_INSTRUCTIONS.get(locale or "en", LANGUAGE_INSTRUCTIONS["en"])


def _check_cancel(cancel_event) -> bool:
    return bool(cancel_event is not None and cancel_event.is_set())


def _check_budget(budget_check) -> bool:
    try:
        return bool(budget_check and budget_check())
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Public pipelines
# ---------------------------------------------------------------------------


async def run_comparison_pipeline(
    constraints: TripConstraints,
    *,
    locale: str | None = None,
    cancel_event=None,
    budget_check=None,
    on_progress=None,
) -> dict | None:
    """Research → generate → validate → reconcile a 3-tier comparison.

    Returns the comparison dict on success, None on total failure (the tool
    translates that into a graceful message for the orchestrator).
    """
    from agents.deep_agent import _reconcile_comparison_budgets

    def progress(stage: str) -> None:
        if on_progress:
            on_progress(stage)

    if _check_cancel(cancel_event) or _check_budget(budget_check):
        return None

    stage_usage: dict[str, dict] = {}
    constraints_text = _constraints_block(constraints)

    # --- Stage 1: parallel research fan-out -------------------------------
    progress("researcher")
    internet_tools = get_internet_tools()
    researcher_task = (
        f"Research hotels, accommodation options, weather, events, and best season for "
        f"{constraints.destination} for a {constraints.total_days}-day trip."
    )
    constraint_task = (
        f"Analyze constraints for a {constraints.total_days}-day trip to "
        f"{constraints.destination} with total budget "
        f"{constraints.budget_amount:,.0f} {constraints.budget_currency}. "
        f"Dietary: {constraints.dietary_restrictions or 'none'}. "
        f"Accessibility: {constraints.accessibility_needs or 'none'}."
    )
    risk_task = f"Detect risks for {constraints.destination}."

    names = ("researcher", "constraint_analyzer", "risk_detector")
    briefs = await asyncio.gather(
        _run_specialist("researcher", RESEARCHER_SYSTEM_PROMPT, researcher_task, internet_tools),
        _run_specialist("constraint_analyzer", CONSTRAINT_ANALYZER_SYSTEM_PROMPT, constraint_task),
        _run_specialist("risk_detector", RISK_DETECTOR_SYSTEM_PROMPT, risk_task, internet_tools),
        return_exceptions=True,
    )
    # _run_specialist already degrades internally; this is the outer net so a
    # stage that throws anyway can never crash the whole pipeline.
    normalized = []
    for n, b in zip(names, briefs):
        if isinstance(b, tuple):
            normalized.append(b[0])
            stage_usage[n] = b[1]
        else:
            logger.warning("Pipeline specialist '%s' raised through gather: %s", n, b)
            normalized.append(f"[{n} unavailable — proceed with remaining context]")
    research_brief, constraint_brief, risk_brief = normalized

    if _check_cancel(cancel_event) or _check_budget(budget_check):
        return None

    # --- Stage 2: structured generation -----------------------------------
    progress("multi_plan_generator")
    task_text = (
        f"{constraints_text}\n\n"
        f"<research_brief>\n{research_brief}\n</research_brief>\n\n"
        f"<constraint_analysis>\n{constraint_brief}\n</constraint_analysis>\n\n"
        f"<risk_assessment>\n{risk_brief}\n</risk_assessment>\n\n"
        f"{_language_block(locale)}\n"
        f"All costs must be in {constraints.budget_currency}. "
        f"Every plan must cover exactly {constraints.total_days} days."
    )

    comparison: dict | None = None
    feedback = ""
    for attempt in range(_MAX_GENERATION_ATTEMPTS):
        attempt_text = task_text
        if feedback:
            attempt_text += f"\n\n<issues_to_fix>\n{feedback}\n</issues_to_fix>"
        comparison, usage = await _generate_structured(
            ComparisonSummary, COMPARISON_SUMMARY_PROMPT, attempt_text, "multi_plan_generator"
        )
        stage_usage["multi_plan_generator"] = usage
        if comparison is None:
            continue
        errors = [i for i in validate_comparison(comparison, constraints) if i.severity == "error"]
        if not errors:
            break
        feedback = "\n".join(i.message for i in errors)
        logger.warning("Comparison validation failed (attempt %d): %s", attempt + 1, feedback)
        comparison = None if attempt + 1 < _MAX_GENERATION_ATTEMPTS else comparison

    if comparison is None:
        logger.error("Comparison pipeline: generation failed after %d attempts", _MAX_GENERATION_ATTEMPTS)
        return None

    # --- Stage 3: deterministic enforcement --------------------------------
    # Constraints win over model output — currency and day count are facts
    # the user stated, not suggestions.
    plans = comparison.get("plans")
    if isinstance(plans, list):
        for plan in plans:
            it = plan.get("itinerary") if isinstance(plan, dict) else None
            if isinstance(it, dict):
                it["currency"] = constraints.budget_currency
                it["total_days"] = constraints.total_days
                it["destination"] = constraints.destination

    comparison = _reconcile_comparison_budgets(
        comparison, (constraints.budget_amount, constraints.budget_currency)
    )

    # The matrix is derivable data — synthesize it rather than trust the
    # model to keep it consistent (or emit it at all).
    matrix = comparison.get("comparison_matrix")
    if not isinstance(matrix, dict):
        matrix = {}
        comparison["comparison_matrix"] = matrix
    if isinstance(plans, list):
        totals = matrix.get("total_cost")
        if not isinstance(totals, dict):
            totals = {}
            matrix["total_cost"] = totals
        for plan in plans:
            if not isinstance(plan, dict):
                continue
            it = plan.get("itinerary")
            if isinstance(it, dict) and isinstance(it.get("estimated_total_cost_usd"), (int, float)):
                totals[plan.get("tier")] = it["estimated_total_cost_usd"]
    return comparison, stage_usage


async def regenerate_tier_plan(
    constraints: TripConstraints,
    tier: str,
    comparison: dict,
    *,
    locale: str | None = None,
    cancel_event=None,
    budget_check=None,
) -> dict | None:
    """Regenerate ONE plan card inside an existing comparison.

    Runs a single structured generation (no research fan-out — the sibling
    plans carry enough context), patches the plan in place so card order is
    preserved, then re-runs the same deterministic enforcement + validation
    the full pipeline applies. Returns the updated comparison, or None on
    total failure (caller keeps the old card).
    """
    if _check_cancel(cancel_event) or _check_budget(budget_check):
        return None

    plans = comparison.get("plans")
    if not isinstance(plans, list):
        return None
    idx = next(
        (i for i, p in enumerate(plans) if isinstance(p, dict) and p.get("tier") == tier),
        None,
    )
    if idx is None:
        logger.warning("Tier regen requested for missing tier '%s'", tier)
        return None

    rejected = plans[idx]
    siblings = [
        {
            "tier": p.get("tier"),
            "total": (p.get("itinerary") or {}).get("estimated_total_cost_usd"),
            "accommodation": (p.get("cost_breakdown") or {}).get("accommodation"),
        }
        for i, p in enumerate(plans)
        if i != idx and isinstance(p, dict)
    ]
    task_text = (
        f"{_constraints_block(constraints)}\n\n"
        f"<rejected_plan tier=\"{tier}\">\n{json.dumps(rejected, ensure_ascii=False)}\n</rejected_plan>\n\n"
        f"<sibling_plans>\n{json.dumps(siblings, ensure_ascii=False)}\n</sibling_plans>\n\n"
        f"{_language_block(locale)}\n"
        f"Regenerate ONLY the '{tier}' plan. All costs in {constraints.budget_currency}. "
        f"The plan must cover exactly {constraints.total_days} days."
    )

    stage_usage: dict[str, dict] = {}
    patched: dict | None = None
    feedback = ""
    for attempt in range(_MAX_GENERATION_ATTEMPTS):
        attempt_text = task_text
        if feedback:
            attempt_text += f"\n\n<issues_to_fix>\n{feedback}\n</issues_to_fix>"
        plan, usage = await _generate_structured(
            ComparisonPlan, SINGLE_TIER_REGEN_PROMPT, attempt_text, "multi_plan_generator"
        )
        stage_usage["multi_plan_generator"] = usage
        if plan is None:
            continue
        candidate = json.loads(json.dumps(comparison))  # deep copy, JSON-safe
        candidate["plans"][idx] = plan
        it = candidate["plans"][idx].get("itinerary")
        if isinstance(it, dict):
            it["currency"] = constraints.budget_currency
            it["total_days"] = constraints.total_days
            it["destination"] = constraints.destination
        from agents.deep_agent import _reconcile_comparison_budgets
        candidate = _reconcile_comparison_budgets(
            candidate, (constraints.budget_amount, constraints.budget_currency)
        )
        errors = [i for i in validate_comparison(candidate, constraints) if i.severity == "error"]
        if not errors:
            patched = candidate
            break
        feedback = "\n".join(i.message for i in errors)
        logger.warning("Tier regen validation failed (attempt %d): %s", attempt + 1, feedback)

    if patched is None:
        logger.error("Tier regen failed after %d attempts (tier=%s)", _MAX_GENERATION_ATTEMPTS, tier)
        return None
    logger.info("Tier regen succeeded (tier=%s, usage=%s)", tier, stage_usage.get("multi_plan_generator"))
    return patched


async def run_refinement_pipeline(
    constraints: TripConstraints,
    tier: str,
    adjustments: str | None = None,
    *,
    locale: str | None = None,
    cancel_event=None,
    budget_check=None,
    on_progress=None,
) -> dict | None:
    """Generate the full day-by-day itinerary for one selected tier.

    Returns the itinerary dict on success, None on failure.
    """
    from agents.deep_agent import (
        _enrich_itinerary_with_coordinates,
        _reconcile_itinerary_budget,
    )

    if _check_cancel(cancel_event) or _check_budget(budget_check):
        return None

    stage_usage: dict[str, dict] = {}
    plan_hint = ""
    latest = await get_latest_comparison(_current_thread_id())
    if isinstance(latest, dict):
        for plan in latest.get("plans", []):
            if isinstance(plan, dict) and str(plan.get("tier", "")).lower() == tier.lower():
                plan_hint = (
                    f"\n\nThe user selected the '{tier}' tier from this summary:\n"
                    f"{plan}\nExpand it into a complete day-by-day itinerary."
                )
                break

    adjustments_text = f"\n\nRequested adjustments: {adjustments}" if adjustments else ""
    task_text = (
        f"Generate a complete {constraints.total_days}-day itinerary for "
        f"{constraints.destination}.\n\n{_constraints_block(constraints)}\n"
        f"Tier: {tier}{plan_hint}{adjustments_text}\n\n"
        f"{_language_block(locale)}\n"
        f"All costs in {constraints.budget_currency}. "
        f"The days array MUST contain exactly {constraints.total_days} entries."
    )

    itinerary: dict | None = None
    feedback = ""
    for attempt in range(_MAX_GENERATION_ATTEMPTS):
        attempt_text = task_text
        if feedback:
            attempt_text += f"\n\n<issues_to_fix>\n{feedback}\n</issues_to_fix>"
        itinerary, usage = await _generate_structured(
            ItineraryPlan, _ITINERARY_GENERATION_PROMPT, attempt_text, "multi_plan_generator"
        )
        stage_usage["itinerary_generator"] = usage
        if itinerary is None:
            continue
        errors = [i for i in validate_itinerary(itinerary, constraints) if i.severity == "error"]
        if not errors:
            break
        feedback = "\n".join(i.message for i in errors)
        logger.warning("Itinerary validation failed (attempt %d): %s", attempt + 1, feedback)
        itinerary = None if attempt + 1 < _MAX_GENERATION_ATTEMPTS else itinerary

    if itinerary is None:
        logger.error("Refinement pipeline: generation failed after %d attempts", _MAX_GENERATION_ATTEMPTS)
        return None

    itinerary["currency"] = constraints.budget_currency
    itinerary = _reconcile_itinerary_budget(
        itinerary, (constraints.budget_amount, constraints.budget_currency)
    )
    itinerary = await _enrich_itinerary_with_coordinates(itinerary)
    return itinerary, stage_usage


async def run_edit_validation_pipeline(
    modified_itinerary: dict,
    *,
    locale: str | None = None,
    cancel_event=None,
    budget_check=None,
) -> tuple[dict, dict] | None:
    """Validate a user's manual itinerary edits — code first, LLM fix-pass only if broken.

    The user edited the itinerary in the UI (reordered/removed/added
    activities). Structure and budget math are checked deterministically;
    an LLM pass only runs when the edit left real damage (missing days,
    emptied slots, broken fields). Returns (itinerary, stage_usage) or None.
    """
    from agents.deep_agent import (
        _enrich_itinerary_with_coordinates,
        _reconcile_itinerary_budget,
    )

    if _check_cancel(cancel_event) or _check_budget(budget_check):
        return None

    stage_usage: dict[str, dict] = {}
    it = modified_itinerary
    days = it.get("days") if isinstance(it, dict) else None
    days = days if isinstance(days, list) else []

    # Pseudo-constraints derived from the edit itself — the user's edits are
    # the source of truth for destination/days/budget here.
    pseudo = TripConstraints(
        destination=str(it.get("destination") or "unknown"),
        total_days=max(1, len(days) or int(it.get("total_days") or 1)),
        budget_amount=float(it.get("estimated_total_cost_usd") or 1),
        budget_currency=str(it.get("currency") or "USD"),
        travel_style="balanced",
        group_type="solo",
    )

    issues = validate_itinerary(it, pseudo)
    errors = [i for i in issues if i.severity == "error"]
    # Edit-specific structural damage the generic validator doesn't cover:
    # a day with every slot empty (user deleted all activities).
    for d in days:
        if not isinstance(d, dict):
            continue
        if not any(d.get(slot) for slot in ("morning", "afternoon", "evening")):
            errors.append(Issue(
                code="empty_day",
                severity="error",
                message=f"Day {d.get('day')} has no activities in any slot",
            ))

    if errors:
        feedback = "\n".join(i.message for i in errors)
        task_text = (
            "The user manually edited their itinerary (reordered, removed, or "
            "added activities). Preserve their edits exactly — fix ONLY the "
            f"problems listed.\n\n<issues_to_fix>\n{feedback}\n</issues_to_fix>\n\n"
            f"<edited_itinerary>\n{json.dumps(it, ensure_ascii=False)}\n</edited_itinerary>\n\n"
            f"{_language_block(locale)}\n"
            f"All costs in {pseudo.budget_currency}. "
            f"The days array MUST contain exactly {pseudo.total_days} entries."
        )
        fixed, usage = await _generate_structured(
            ItineraryPlan, _EDIT_FIX_PROMPT, task_text, "multi_plan_generator"
        )
        stage_usage["edit_validator"] = usage
        if fixed is not None:
            still_bad = [
                i for i in validate_itinerary(fixed, pseudo) if i.severity == "error"
            ]
            if not still_bad:
                it = fixed
            else:
                logger.warning(
                    "Edit fix-pass still has issues: %s — emitting reconciled original",
                    "; ".join(i.message for i in still_bad),
                )

    it["currency"] = pseudo.budget_currency
    it = _reconcile_itinerary_budget(it, (pseudo.budget_amount, pseudo.budget_currency))
    it = await _enrich_itinerary_with_coordinates(it)
    return it, stage_usage


_ITINERARY_GENERATION_PROMPT = """<role>
You are an expert travel itinerary generator. Produce ONE complete,
day-by-day itinerary as structured output — realistic pricing, coherent
daily flow, respecting every stated constraint.
</role>

<rules>
- The days array MUST contain exactly the requested number of days — never fewer, never truncated
- estimated_total_cost_usd must equal the sum of all daily_cost_usd values
- All costs in the requested currency — never silently switch
- Respect dietary restrictions and accessibility needs in every activity and meal suggestion
- Keep daily pacing reasonable (not packed, not empty)
</rules>"""


_EDIT_FIX_PROMPT = """<role>
You are an itinerary repair specialist. The user manually edited their
itinerary in a UI (reordered days, removed or added activities). Return the
corrected itinerary as structured output.
</role>

<rules>
- Preserve the user's edits exactly — do not reorder, remove, or "improve" their choices
- Fix ONLY the listed issues: missing fields, emptied day slots, broken costs
- estimated_total_cost_usd must equal the sum of all daily_cost_usd values
- All costs in the itinerary's currency — never switch
- The days array MUST contain exactly the requested number of entries
</rules>"""


def _current_thread_id() -> str:
    from agents.tools.visuals import get_current_thread_id

    return get_current_thread_id()
