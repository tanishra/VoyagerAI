"""Tests for TripConstraints schema + stated-days extraction."""

import pytest
from pydantic import ValidationError

from agents.constraints import TripConstraints, extract_stated_days


class TestTripConstraints:
    def _kwargs(self, **overrides):
        base = {
            "destination": "Delhi, India",
            "total_days": 5,
            "budget_amount": 50000,
            "budget_currency": "INR",
            "travel_style": "balanced",
            "group_type": "friends",
        }
        base.update(overrides)
        return base

    def test_valid_minimal(self):
        c = TripConstraints(**self._kwargs())
        assert c.total_days == 5
        assert c.dietary_restrictions == []
        assert c.accessibility_needs == []

    def test_valid_full(self):
        c = TripConstraints(**self._kwargs(
            dietary_restrictions=["vegetarian"], accessibility_needs=["wheelchair"]
        ))
        assert c.dietary_restrictions == ["vegetarian"]

    @pytest.mark.parametrize("field,value", [
        ("total_days", 0), ("total_days", 31), ("total_days", "x"),
        ("budget_amount", 0), ("budget_amount", -5),
        ("budget_currency", "BTC"), ("travel_style", "chill"),
        ("group_type", "party"), ("destination", ""),
    ])
    def test_invalid_fields_rejected(self, field, value):
        with pytest.raises(ValidationError):
            TripConstraints(**self._kwargs(**{field: value}))

    def test_missing_required_field_rejected(self):
        kwargs = self._kwargs()
        del kwargs["total_days"]
        with pytest.raises(ValidationError):
            TripConstraints(**kwargs)


class TestExtractStatedDays:
    def test_plain_days(self):
        assert extract_stated_days("plan a trip for 5 days to Delhi") == 5
        assert extract_stated_days("5 days in Tokyo") == 5

    def test_hyphenated(self):
        assert extract_stated_days("a 5-day trip to Delhi") == 5

    def test_weeks(self):
        assert extract_stated_days("a week in Paris") == 7
        assert extract_stated_days("2 weeks in Japan") == 14
        assert extract_stated_days("one week trip") == 7

    def test_none(self):
        assert extract_stated_days("plan a trip") is None
        assert extract_stated_days("") is None
        assert extract_stated_days(None) is None

    def test_out_of_range_rejected(self):
        assert extract_stated_days("45 days of travel") is None
        assert extract_stated_days("0 days") is None

    def test_never_raises(self):
        assert extract_stated_days("12345678901234567890 days") is None
