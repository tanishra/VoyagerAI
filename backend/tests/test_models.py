"""Tests for Pydantic models — validation, serialization, edge cases."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from models import (
    PlanRequest,
    Activity,
    DayPlan,
    Itinerary,
    PlanResponse,
    ReplanRequest,
    TravelStyle,
    GroupType,
)


class TestPlanRequest:
    def test_valid_request(self, valid_plan_payload):
        req = PlanRequest(**valid_plan_payload)
        assert req.destination == "Tokyo, Japan"
        assert req.days == 5
        assert req.budget_usd == 3000
        assert req.travel_style == TravelStyle.CULTURAL
        assert req.group_type == GroupType.SOLO
        assert req.dietary == "vegetarian"

    def test_minimal_request(self):
        req = PlanRequest(
            destination="Paris",
            days=1,
            budget_usd=100,
            travel_style="budget",
            group_type="solo",
        )
        assert req.days == 1
        assert req.dietary is None
        assert req.constraints is None

    @pytest.mark.parametrize("bad_dest", ["", "A", "123", "!!!"])
    def test_invalid_destination(self, bad_dest):
        with pytest.raises(ValidationError):
            PlanRequest(
                destination=bad_dest,
                days=3,
                budget_usd=500,
                travel_style="adventure",
                group_type="couple",
            )

    @pytest.mark.parametrize("bad_days", [0, -1, 31, 100])
    def test_invalid_days(self, bad_days):
        with pytest.raises(ValidationError):
            PlanRequest(
                destination="London",
                days=bad_days,
                budget_usd=500,
                travel_style="luxury",
                group_type="solo",
            )

    @pytest.mark.parametrize("bad_budget", [0, 10, 49])
    def test_budget_too_low(self, bad_budget):
        with pytest.raises(ValidationError):
            PlanRequest(
                destination="London",
                days=3,
                budget_usd=bad_budget,
                travel_style="budget",
                group_type="solo",
            )

    def test_budget_too_low_per_day(self):
        with pytest.raises(ValidationError, match="too low"):
            PlanRequest(
                destination="Mumbai",
                days=10,
                budget_usd=100,
                travel_style="budget",
                group_type="solo",
            )

    def test_optional_strings_trimmed(self):
        req = PlanRequest(
            destination="Berlin",
            days=3,
            budget_usd=500,
            travel_style="cultural",
            group_type="solo",
            dietary="  ",
            constraints="  ",
        )
        assert req.dietary is None
        assert req.constraints is None

    @pytest.mark.parametrize("style", ["adventure", "cultural", "luxury", "budget"])
    def test_valid_travel_styles(self, style):
        req = PlanRequest(
            destination="Rome",
            days=3,
            budget_usd=500,
            travel_style=style,
            group_type="solo",
        )
        assert req.travel_style.value == style

    def test_invalid_travel_style(self):
        with pytest.raises(ValidationError):
            PlanRequest(
                destination="Rome",
                days=3,
                budget_usd=500,
                travel_style="extreme",
                group_type="solo",
            )


class TestReplanRequest:
    def test_valid_replan(self, sample_itinerary_dict):
        from models import Itinerary
        itinerary = Itinerary.model_validate(sample_itinerary_dict)
        req = ReplanRequest(
            itinerary=itinerary,
            day_number=2,
            reason="Too expensive, find cheaper options",
        )
        assert req.day_number == 2
        assert "cheaper" in req.reason

    def test_day_number_too_low(self, sample_itinerary_dict):
        from models import Itinerary
        with pytest.raises(ValidationError):
            ReplanRequest(
                itinerary=Itinerary.model_validate(sample_itinerary_dict),
                day_number=0,
                reason="Change day",
            )

    def test_reason_too_short(self, sample_itinerary_dict):
        from models import Itinerary
        with pytest.raises(ValidationError):
            ReplanRequest(
                itinerary=Itinerary.model_validate(sample_itinerary_dict),
                day_number=1,
                reason="X",
            )


class TestModels:
    def test_activity_model(self, sample_activity_dict):
        activity = Activity(**sample_activity_dict)
        assert activity.activity == "Test"
        assert activity.cost_usd == 10

    def test_day_plan_model(self, sample_activity_dict):
        day = DayPlan(
            day=1,
            theme="Test Day",
            morning=Activity(**sample_activity_dict),
            afternoon=Activity(**sample_activity_dict),
            evening=Activity(**sample_activity_dict),
            transport="Bus",
            accommodation="Hostel",
            daily_cost_usd=50,
            tips=["Tip 1"],
        )
        assert day.day == 1
        assert len(day.tips) == 1
        assert day.daily_cost_usd == 50

    def test_itinerary_round_trip(self, sample_itinerary_dict):
        itinerary = Itinerary.model_validate(sample_itinerary_dict)
        assert itinerary.destination == "Paris"
        assert len(itinerary.days) == 3
        assert itinerary.budget_status == "within"
        restored = itinerary.model_dump()
        assert restored["destination"] == "Paris"
        assert len(restored["days"]) == 3

    def test_plan_response_success(self, sample_itinerary_dict):
        itinerary = Itinerary.model_validate(sample_itinerary_dict)
        resp = PlanResponse(success=True, itinerary=itinerary)
        assert resp.success is True
        assert resp.error is None
        assert resp.itinerary is not None
        assert resp.itinerary.destination == "Paris"

    def test_plan_response_error(self):
        resp = PlanResponse(success=False, error="Something failed")
        assert resp.success is False
        assert resp.error == "Something failed"
        assert resp.itinerary is None

    def test_itinerary_default_empty_lists(self):
        """Ensure warnings and packing_essentials default to empty lists."""
        itinerary = Itinerary(
            destination="Test",
            total_days=1,
            estimated_total_cost_usd=100,
            budget_status="within",
            visa_note="None",
            best_season_note="Anytime",
            days=[
                DayPlan(
                    day=1,
                    theme="Test",
                    morning=Activity(activity="A", location="L", cost_usd=10, duration="1h"),
                    afternoon=Activity(activity="A", location="L", cost_usd=10, duration="1h"),
                    evening=Activity(activity="A", location="L", cost_usd=10, duration="1h"),
                    transport="Walk",
                    accommodation="None",
                    daily_cost_usd=30,
                )
            ],
        )
        assert itinerary.warnings == []
        assert itinerary.packing_essentials == []
