"""Regression: header total must match the sum of daily costs.

The model occasionally confuses a per-day allowance with the trip total —
estimated_total_cost_usd can contradict sum(daily_cost_usd). The backend now
reconciles deterministically before yielding the itinerary event.
"""

import copy

import agents.deep_agent as deep_agent_module

reconcile = deep_agent_module._reconcile_itinerary_budget
reconcile_comparison = deep_agent_module._reconcile_comparison_budgets


def _itinerary(total: float, daily: list[float]) -> dict:
    return {
        "destination": "Tokyo",
        "total_days": len(daily),
        "estimated_total_cost_usd": total,
        "budget_status": "within",
        "days": [
            {"day": i + 1, "theme": f"Day {i + 1}", "daily_cost_usd": c}
            for i, c in enumerate(daily)
        ],
    }


class TestReconcileItineraryBudget:
    def test_matching_total_unchanged(self):
        it = _itinerary(375000, [75000, 75000, 75000, 75000, 75000])
        out = reconcile(it)
        assert out["estimated_total_cost_usd"] == 375000

    def test_wrong_header_corrected_to_day_sum(self):
        """The exact failure mode: model used per-day allowance (75000) as the
        header total while its own days summed to 375000."""
        it = _itinerary(75000, [75000, 75000, 75000, 75000, 75000])
        out = reconcile(it)
        assert out["estimated_total_cost_usd"] == 375000

    def test_within_5pct_tolerance_unchanged(self):
        it = _itinerary(355000, [75000, 75000, 75000, 75000, 75000])
        out = reconcile(it)
        # 355000 vs 375000 = 5.33% off — actually over tolerance; use exact 5%:
        it2 = _itinerary(375000 * 0.95 + 1, [75000] * 5)
        assert reconcile(it2)["estimated_total_cost_usd"] == it2["estimated_total_cost_usd"]

    def test_missing_header_filled_from_day_sum(self):
        it = _itinerary(0, [100, 200, 300])
        out = reconcile(it)
        assert out["estimated_total_cost_usd"] == 600

    def test_no_days_returns_unchanged(self):
        it = {"destination": "Tokyo", "estimated_total_cost_usd": 500}
        assert reconcile(it) is it

    def test_zero_day_sum_returns_unchanged(self):
        it = _itinerary(500, [0, 0, 0])
        assert reconcile(it)["estimated_total_cost_usd"] == 500

    def test_does_not_mutate_input(self):
        it = _itinerary(75000, [75000] * 5)
        snapshot = copy.deepcopy(it)
        reconcile(it)
        assert it == snapshot

    def test_never_raises_on_bad_types(self):
        bad = {"days": [{"daily_cost_usd": "abc"}], "estimated_total_cost_usd": "x"}
        out = reconcile(bad)
        assert isinstance(out, dict)


class TestReconcileComparisonBudgets:
    def test_each_plan_reconciled(self):
        comp = {
            "plans": [
                {"tier": "budget", "itinerary": _itinerary(500, [250, 250])},
                {"tier": "balanced", "itinerary": _itinerary(100, [250, 250])},
                {"tier": "premium", "itinerary": _itinerary(1500, [750, 750])},
            ]
        }
        out = reconcile_comparison(comp)
        totals = [p["itinerary"]["estimated_total_cost_usd"] for p in out["plans"]]
        assert totals == [500, 500, 1500]

    def test_none_passthrough(self):
        assert reconcile_comparison(None) is None

    def test_non_dict_passthrough(self):
        assert reconcile_comparison("text") == "text"
