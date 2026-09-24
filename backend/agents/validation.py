"""Deterministic plan validation — code checks what the LLM claimed.

An LLM self-reporting "budget_status: within" or a day count is a claim, not
a fact. These validators recompute the facts: does the day count match the
request, do the numbers sum, does the currency match, does the plan respect
the stated budget. Never raises — returns a list of Issue objects.
"""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel

from agents.constraints import TripConstraints

logger = logging.getLogger("travel_agent.validation")

_TOLERANCE = 0.05
_BUDGET_OVER_TOLERANCE = 1.05

_REQUIRED_ITINERARY_FIELDS = ("destination", "days")


class Issue(BaseModel):
    """A single validation finding. Mirrors the validator subagent's output
    shape so it can be dropped in where the LLM validator used to sit."""

    code: str
    severity: Literal["error", "warning"]
    message: str


def _as_float(value) -> float | None:
    import math
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f  # NaN guard


def validate_itinerary(
    itinerary: dict,
    constraints: TripConstraints | None = None,
    summary_only: bool = False,
) -> list[Issue]:
    """Check a single itinerary for internal consistency + stated constraints.

    Never raises. `constraints=None` still performs internal-consistency
    checks (sums, required fields) that don't need the user's request.
    """
    issues: list[Issue] = []
    if not isinstance(itinerary, dict):
        return [Issue(code="not_a_dict", severity="error", message="itinerary is not an object")]

    required = () if summary_only else _REQUIRED_ITINERARY_FIELDS
    for field in required:
        if not itinerary.get(field):
            issues.append(Issue(code="missing_field", severity="error", message=f"missing '{field}'"))

    days = itinerary.get("days")
    day_count = len(days) if isinstance(days, list) else 0
    declared_days = itinerary.get("total_days")
    declared_total = _as_float(itinerary.get("estimated_total_cost_usd"))
    day_sum = sum(
        f for d in days or [] if isinstance(d, dict)
        for f in [_as_float(d.get("daily_cost_usd"))] if f is not None
    )

    # --- day count vs declared/requested ---
    if isinstance(declared_days, int) and day_count > 0 and declared_days != day_count:
        issues.append(Issue(
            code="total_days_mismatch",
            severity="warning",
            message=f"total_days={declared_days} but days[] has {day_count} entries",
        ))
    if constraints is not None and day_count > 0 and day_count != constraints.total_days:
        issues.append(Issue(
            code="wrong_trip_length",
            severity="error",
            message=(
                f"plan covers {day_count} days but the user asked for "
                f"{constraints.total_days}"
            ),
        ))

    # --- header total vs day sum ---
    if declared_total is not None and day_sum > 0:
        if abs(declared_total - day_sum) / day_sum > _TOLERANCE:
            issues.append(Issue(
                code="total_mismatch",
                severity="error",
                message=f"estimated_total_cost_usd={declared_total} but daily costs sum to {day_sum}",
            ))
    elif declared_total is None and day_sum > 0:
        issues.append(Issue(code="missing_total", severity="warning", message="no estimated_total_cost_usd"))

    # --- cost_breakdown categories vs total ---
    breakdown = itinerary.get("cost_breakdown")
    if isinstance(breakdown, dict) and declared_total:
        cat_sum = sum(
            f for k in ("accommodation", "food", "activities", "transport")
            if (f := _as_float(breakdown.get(k))) is not None
        )
        breakdown_total = _as_float(breakdown.get("total"))
        if cat_sum > 0 and abs(cat_sum - declared_total) / declared_total > _TOLERANCE:
            issues.append(Issue(
                code="breakdown_sum_mismatch",
                severity="warning",
                message=f"cost_breakdown categories sum to {cat_sum}, total is {declared_total}",
            ))
        if breakdown_total is not None and abs(breakdown_total - declared_total) / declared_total > _TOLERANCE:
            issues.append(Issue(
                code="breakdown_total_mismatch",
                severity="warning",
                message=f"cost_breakdown.total={breakdown_total} but itinerary total is {declared_total}",
            ))

    # --- stated constraints ---
    if constraints is not None:
        currency = str(itinerary.get("currency") or "").upper()
        if currency and currency != constraints.budget_currency:
            issues.append(Issue(
                code="currency_mismatch",
                severity="error",
                message=f"plan currency is {currency}, user stated {constraints.budget_currency}",
            ))
        if declared_total is not None and declared_total > constraints.budget_amount * _BUDGET_OVER_TOLERANCE:
            issues.append(Issue(
                code="over_budget",
                severity="error",
                message=(
                    f"total {declared_total} exceeds stated budget "
                    f"{constraints.budget_amount} {constraints.budget_currency}"
                ),
            ))
        destination = str(itinerary.get("destination") or "")
        if destination and constraints.destination:  # noqa: SIM102
            if constraints.destination.split(",")[0].strip().lower() not in destination.lower():
                issues.append(Issue(
                    code="destination_mismatch",
                    severity="warning",
                    message=f"plan destination '{destination}' doesn't mention '{constraints.destination}'",
                ))

    return issues


def validate_comparison(
    comparison: dict,
    constraints: TripConstraints | None = None,
) -> list[Issue]:
    """Validate all plans in a comparison + cross-plan sanity.

    Never raises.
    """
    issues: list[Issue] = []
    if not isinstance(comparison, dict):
        return [Issue(code="not_a_dict", severity="error", message="comparison is not an object")]

    plans = comparison.get("plans")
    if not isinstance(plans, list) or not plans:
        return [Issue(code="no_plans", severity="error", message="comparison has no plans")]

    tiers = [str(p.get("tier", "")).lower() for p in plans if isinstance(p, dict)]
    for expected in ("budget", "balanced", "premium"):
        if expected not in tiers:
            issues.append(Issue(
                code="missing_tier", severity="error", message=f"no '{expected}' plan present"
            ))

    totals: dict[str, float] = {}
    for plan in plans:
        if not isinstance(plan, dict):
            continue
        tier = str(plan.get("tier", "?"))
        it = plan.get("itinerary")
        if isinstance(it, dict):
            for issue in validate_itinerary(it, constraints, summary_only=True):
                # Premium intentionally targets ~150% of the stated budget —
                # over_budget is an error for budget/balanced, expected there.
                if issue.code == "over_budget" and tier == "premium":
                    continue
                issues.append(issue.model_copy(update={"message": f"[{tier}] {issue.message}"}))
            total = _as_float(it.get("estimated_total_cost_usd"))
            if total is not None:
                totals[tier] = total
        # A plan may also carry cost_breakdown at plan level (comparison schema)
        cb = plan.get("cost_breakdown")
        it_total = _as_float(it.get("estimated_total_cost_usd")) if isinstance(it, dict) else None
        if isinstance(cb, dict) and it_total:
            cb_total = _as_float(cb.get("total"))
            if cb_total is not None and abs(cb_total - it_total) / it_total > _TOLERANCE:
                issues.append(Issue(
                    code="plan_breakdown_total_mismatch",
                    severity="warning",
                    message=f"[{tier}] cost_breakdown.total={cb_total} but itinerary total is {it_total}",
                ))

    # --- tier ordering: budget < balanced < premium ---
    ordered = [totals.get(t) for t in ("budget", "balanced", "premium")]
    if all(t is not None for t in ordered):
        b, m, p = ordered
        if not (b <= m <= p):
            issues.append(Issue(
                code="tier_ordering",
                severity="warning",
                message=f"tier totals not ordered budget≤balanced≤premium: {b}/{m}/{p}",
            ))

    # --- matrix vs plan totals ---
    matrix = comparison.get("comparison_matrix")
    if isinstance(matrix, dict):
        matrix_costs = matrix.get("total_cost")
        if isinstance(matrix_costs, dict):
            for tier, total in totals.items():
                mc = _as_float(matrix_costs.get(tier))
                if mc is not None and abs(mc - total) / total > _TOLERANCE:
                    issues.append(Issue(
                        code="matrix_mismatch",
                        severity="error",
                        message=f"matrix total_cost[{tier}]={mc} but itinerary total is {total}",
                    ))

    return issues
