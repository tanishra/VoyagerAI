"""Tests for Pydantic models — validation, serialization, edge cases."""

from __future__ import annotations

from models import (
    Activity,
    DayPlan,
    Itinerary,
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
