"""Tests for the deterministic plan validators.

Encodes the exact failure seen in production: a 5-day request produced
2-day plans whose matrix total, card total, and breakdown total all
disagreed.
"""

from agents.constraints import TripConstraints
from agents.validation import validate_comparison, validate_itinerary


def _constraints(**overrides):
    base = {
        "destination": "Delhi, India",
        "total_days": 5,
        "budget_amount": 50000,
        "budget_currency": "INR",
        "travel_style": "balanced",
        "group_type": "friends",
    }
    base.update(overrides)
    return TripConstraints(**base)


def _days(n: int, cost: float) -> list[dict]:
    return [{"day": i + 1, "daily_cost_usd": cost} for i in range(n)]


def _itinerary(**overrides):
    base = {
        "destination": "Delhi, India",
        "total_days": 5,
        "currency": "INR",
        "estimated_total_cost_usd": 40000,
        "days": _days(5, 8000),
    }
    base.update(overrides)
    return base


class TestValidateItinerary:
    def test_clean_itinerary_passes(self):
        assert validate_itinerary(_itinerary(), _constraints()) == []

    def test_wrong_day_count_is_error(self):
        """The production bug: 5-day request, 2-day plan."""
        it = _itinerary(total_days=2, days=_days(2, 8000), estimated_total_cost_usd=16000)
        issues = validate_itinerary(it, _constraints())
        assert any(i.code == "wrong_trip_length" and i.severity == "error" for i in issues)

    def test_total_days_field_mismatch_warns(self):
        it = _itinerary(total_days=5, days=_days(2, 8000), estimated_total_cost_usd=16000)
        issues = validate_itinerary(it, None)
        assert any(i.code == "total_days_mismatch" for i in issues)

    def test_header_vs_day_sum_mismatch(self):
        it = _itinerary(estimated_total_cost_usd=40000, days=_days(5, 8000))
        assert validate_itinerary(it, None) == []
        it2 = _itinerary(estimated_total_cost_usd=90000, days=_days(5, 8000))
        assert any(i.code == "total_mismatch" for i in validate_itinerary(it2, None))

    def test_breakdown_sum_mismatch(self):
        """Categories sum to 15000 while breakdown.total says 40000 —
        the production bug's exact shape."""
        it = _itinerary(cost_breakdown={
            "accommodation": 5000, "food": 5000,
            "activities": 3000, "transport": 2000, "total": 40000,
        })
        issues = validate_itinerary(it, None)
        assert any(i.code == "breakdown_sum_mismatch" for i in issues)
        assert not any(i.code == "breakdown_total_mismatch" for i in issues)

    def test_breakdown_total_mismatch(self):
        it = _itinerary(cost_breakdown={
            "accommodation": 9000, "food": 9000,
            "activities": 6000, "transport": 6000, "total": 25000,
        })
        issues = validate_itinerary(it, None)
        assert any(i.code == "breakdown_total_mismatch" for i in issues)

    def test_over_budget_flagged(self):
        it = _itinerary(estimated_total_cost_usd=80000, days=_days(5, 16000))
        issues = validate_itinerary(it, _constraints())
        assert any(i.code == "over_budget" and i.severity == "error" for i in issues)

    def test_currency_mismatch_flagged(self):
        it = _itinerary(currency="USD")
        issues = validate_itinerary(it, _constraints())
        assert any(i.code == "currency_mismatch" for i in issues)

    def test_no_constraints_still_checks_consistency(self):
        it = _itinerary(estimated_total_cost_usd=99999, days=_days(5, 8000))
        issues = validate_itinerary(it, None)
        assert any(i.code == "total_mismatch" for i in issues)

    def test_never_raises_on_garbage(self):
        assert validate_itinerary("junk", _constraints())
        assert validate_itinerary({}, _constraints())
        assert validate_itinerary({"days": [{"daily_cost_usd": "x"}]}, None)


class TestValidateComparison:
    def _comparison(self, totals=(16000, 20000, 32000), days_each=2, matrix=None):
        tiers = ("budget", "balanced", "premium")
        plans = [
            {
                "tier": t,
                "itinerary": _itinerary(
                    total_days=days_each,
                    days=_days(days_each, total / days_each),
                    estimated_total_cost_usd=total,
                ),
                "cost_breakdown": {"total": total},
                "tradeoffs": [],
            }
            for t, total in zip(tiers, totals)
        ]
        comp = {"plans": plans}
        if matrix is not None:
            comp["comparison_matrix"] = {"total_cost": matrix}
        return comp

    def test_clean_comparison_passes(self):
        comp = self._comparison(totals=(30000, 50000, 75000), days_each=5)
        assert validate_comparison(comp, _constraints()) == []

    def test_missing_tier_flagged(self):
        comp = self._comparison()
        comp["plans"] = comp["plans"][:2]  # drop premium
        issues = validate_comparison(comp, _constraints())
        assert any(i.code == "missing_tier" for i in issues)

    def test_matrix_mismatch_flagged(self):
        """The production bug: matrix says 40000, itinerary says 16000."""
        comp = self._comparison(
            totals=(16000, 20000, 32000), days_each=2,
            matrix={"budget": 40000, "balanced": 50000, "premium": 80000},
        )
        issues = validate_comparison(comp, _constraints())
        codes = {i.code for i in issues}
        assert "matrix_mismatch" in codes
        assert "wrong_trip_length" in codes

    def test_tier_ordering_flagged(self):
        comp = self._comparison(totals=(90000, 20000, 32000), days_each=5)
        comp["plans"][0]["itinerary"]["days"] = _days(5, 18000)  # sum matches 90000
        issues = validate_comparison(comp, _constraints())
        assert any(i.code == "tier_ordering" for i in issues)

    def test_never_raises_on_garbage(self):
        assert validate_comparison(None, _constraints())
        assert validate_comparison({"plans": "x"}, None)


class TestScheduleClashes:
    def _day(self, n, **slots):
        return {"day": n, **slots}

    def test_overlap_flagged(self):
        from agents.validation import detect_schedule_clashes
        it = {"days": [self._day(
            1,
            morning={"activity": "Museum", "time": "09:00", "duration": "4h"},
            afternoon={"activity": "Lunch", "time": "12:00", "duration": "1h"},
        )]}
        msgs = detect_schedule_clashes(it)
        assert len(msgs) == 1
        assert "Day 1" in msgs[0] and "Museum" in msgs[0] and "Lunch" in msgs[0]

    def test_no_overlap_no_message(self):
        from agents.validation import detect_schedule_clashes
        it = {"days": [self._day(
            1,
            morning={"activity": "Museum", "time": "09:00", "duration": "2h"},
            afternoon={"activity": "Lunch", "time": "13:00", "duration": "1h"},
        )]}
        assert detect_schedule_clashes(it) == []

    def test_missing_times_use_defaults(self):
        from agents.validation import detect_schedule_clashes
        it = {"days": [self._day(
            1,
            morning={"activity": "Long tour", "duration": "6h"},
            afternoon={"activity": "Lunch", "duration": "1h"},
        )]}
        # 9:00 + 6h = 15:00 vs afternoon default 13:00 → overlap
        assert len(detect_schedule_clashes(it)) == 1

    def test_days_are_independent(self):
        from agents.validation import detect_schedule_clashes
        it = {"days": [
            self._day(1, evening={"activity": "Late show", "time": "22:00", "duration": "4h"}),
            self._day(2, morning={"activity": "Early start", "time": "06:00", "duration": "1h"}),
        ]}
        assert detect_schedule_clashes(it) == []

    def test_never_raises_on_garbage(self):
        from agents.validation import detect_schedule_clashes
        assert detect_schedule_clashes({"days": "not-a-list"}) == []
        assert detect_schedule_clashes({}) == []
        assert detect_schedule_clashes({"days": [{"day": 1, "morning": "x"}]}) == []
