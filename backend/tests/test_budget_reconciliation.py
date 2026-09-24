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
        reconcile(it)
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

    def test_missing_currency_defaults_to_usd(self):
        it = _itinerary(375000, [75000] * 5)
        assert reconcile(it)["currency"] == "USD"

    def test_existing_currency_preserved(self):
        it = _itinerary(375000, [75000] * 5)
        it["currency"] = "INR"
        assert reconcile(it)["currency"] == "INR"

    def test_stated_budget_over_flags_status(self):
        """Internally consistent (header == day sum) but 3x the user's stated
        budget — self-consistency alone can't catch this."""
        it = _itinerary(150000, [30000] * 5)
        it["currency"] = "INR"
        it["budget_status"] = "within"
        out = reconcile(it, stated_budget=(50000, "INR"))
        assert out["budget_status"] == "over"
        assert any("above your stated budget" in w for w in out["warnings"])

    def test_stated_budget_within_confirmed(self):
        it = _itinerary(48000, [9600] * 5)
        it["currency"] = "INR"
        it["budget_status"] = "over"  # model wrongly self-assessed
        out = reconcile(it, stated_budget=(50000, "INR"))
        assert out["budget_status"] == "within"

    def test_stated_budget_currency_mismatch_skipped(self):
        """Can't compare a JPY cap against a USD plan — don't touch status."""
        it = _itinerary(375000, [75000] * 5)
        it["budget_status"] = "within"
        out = reconcile(it, stated_budget=(50000, "JPY"))
        assert out["budget_status"] == "within"

    def test_stated_budget_none_is_noop(self):
        it = _itinerary(375000, [75000] * 5)
        it["budget_status"] = "within"
        out = reconcile(it, stated_budget=None)
        assert out["budget_status"] == "within"


class TestExtractStatedCurrencyAndBudget:
    def setup_method(self):
        from agents.prompts import extract_stated_budget, extract_stated_currency
        self.extract_stated_currency = extract_stated_currency
        self.extract_stated_budget = extract_stated_budget

    def test_extract_currency_symbol(self):
        assert self.extract_stated_currency("my budget is ₹3,75,000") == "INR"
        assert self.extract_stated_currency("I have $2000 to spend") == "USD"
        assert self.extract_stated_currency("around €1500") == "EUR"

    def test_extract_currency_code(self):
        assert self.extract_stated_currency("budget is 1500 EUR total") == "EUR"

    def test_extract_currency_none(self):
        assert self.extract_stated_currency("plan a trip to Tokyo") is None
        assert self.extract_stated_currency("") is None
        assert self.extract_stated_currency(None) is None

    def test_extract_budget_symbol(self):
        assert self.extract_stated_budget("₹3,75,000 total budget") == (375000.0, "INR")
        assert self.extract_stated_budget("$2000") == (2000.0, "USD")

    def test_extract_budget_code_suffix(self):
        assert self.extract_stated_budget("1500 EUR for the trip") == (1500.0, "EUR")

    def test_extract_budget_none(self):
        assert self.extract_stated_budget("no numbers here") is None


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

    def test_matrix_synced_to_reconciled_totals(self):
        """The production bug: matrix showed the model's original totals
        while card totals were reconciled to day sums — two contradictory
        numbers on one card."""
        comp = {
            "plans": [
                {"tier": "budget", "itinerary": _itinerary(40000, [8000, 8000])},
                {"tier": "balanced", "itinerary": _itinerary(50000, [10000, 10000])},
                {"tier": "premium", "itinerary": _itinerary(80000, [16000, 16000])},
            ],
            "comparison_matrix": {
                "total_cost": {"budget": 40000, "balanced": 50000, "premium": 80000}
            },
        }
        out = reconcile_comparison(comp)
        mc = out["comparison_matrix"]["total_cost"]
        assert mc == {"budget": 16000, "balanced": 20000, "premium": 32000}
        for p in out["plans"]:
            assert p["itinerary"]["estimated_total_cost_usd"] == mc[p["tier"]]

    def test_plan_breakdown_scaled_to_total(self):
        """Breakdown categories that don't sum to the total get scaled so
        the card never shows contradictory figures."""
        comp = {
            "plans": [{
                "tier": "budget",
                "itinerary": _itinerary(16000, [8000, 8000]),
                "cost_breakdown": {
                    "accommodation": 5000, "food": 5000,
                    "activities": 3000, "transport": 2000, "total": 40000,
                },
            }]
        }
        out = reconcile_comparison(comp)
        bd = out["plans"][0]["cost_breakdown"]
        assert bd["total"] == 16000
        cat_sum = bd["accommodation"] + bd["food"] + bd["activities"] + bd["transport"]
        assert abs(cat_sum - 16000) < 1  # rounding drift fixed on largest category

    def test_breakdown_total_updated_within_tolerance(self):
        comp = {
            "plans": [{
                "tier": "balanced",
                "itinerary": _itinerary(20000, [10000, 10000]),
                "cost_breakdown": {
                    "accommodation": 5000, "food": 6000,
                    "activities": 5000, "transport": 4000, "total": 20001,
                },
            }]
        }
        out = reconcile_comparison(comp)
        bd = out["plans"][0]["cost_breakdown"]
        # Within 5% — categories untouched, total normalized to itinerary total
        assert bd["accommodation"] == 5000
        assert bd["total"] == 20000

    def test_total_days_mismatch_flagged(self):
        it = _itinerary(16000, [8000, 8000])
        it["total_days"] = 5  # declared 5, only 2 day objects
        out = reconcile(it)
        assert any("2 of 5 days" in w for w in out["warnings"])

    def test_total_days_mismatch_flagged_in_comparison(self):
        comp = {
            "plans": [{
                "tier": "balanced",
                "itinerary": {**_itinerary(20000, [10000, 10000]), "total_days": 5},
            }]
        }
        out = reconcile_comparison(comp)
        assert any("2 of 5 days" in w for w in out["plans"][0]["itinerary"]["warnings"])
