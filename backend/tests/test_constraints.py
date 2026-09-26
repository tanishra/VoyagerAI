"""Tests for TripConstraints schema + stated-days extraction."""

import pytest
from pydantic import ValidationError

from agents.constraints import TripConstraints, extract_stated_days, normalize_digits


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

    def test_spanish(self):
        assert extract_stated_days("2 semanas en Delhi") == 14
        assert extract_stated_days("tres días") == 3
        assert extract_stated_days("una semana") == 7

    def test_french(self):
        assert extract_stated_days("3 semaines à Paris") == 21
        assert extract_stated_days("une semaine") == 7
        assert extract_stated_days("deux jours") == 2

    def test_german(self):
        assert extract_stated_days("2 Wochen in Japan") == 14
        assert extract_stated_days("eine Woche") == 7
        assert extract_stated_days("fünf Tage") == 5

    def test_hindi(self):
        assert extract_stated_days("एक हफ्ता") == 7
        assert extract_stated_days("२ सप्ताह") == 14
        assert extract_stated_days("५ दिन") == 5
        assert extract_stated_days("दस दिन") == 10

    def test_japanese(self):
        assert extract_stated_days("7日間") == 7
        assert extract_stated_days("一週間") == 7
        assert extract_stated_days("３日間") == 3  # full-width digit

    def test_english_slang(self):
        assert extract_stated_days("a fortnight") == 14
        assert extract_stated_days("fortnight") == 14
        assert extract_stated_days("a weekend") == 2
        assert extract_stated_days("seven days") == 7

    def test_months(self):
        assert extract_stated_days("1 month") == 30
        assert extract_stated_days("un mes") == 30

    def test_bare_weekend_not_a_duration(self):
        """Bare 'weekend' is timing, not duration — LLM decides instead."""
        assert extract_stated_days("every weekend") is None
        assert extract_stated_days("weekend getaway") is None

    def test_normalize_digits(self):
        assert normalize_digits("५०,०००") == "50,000"
        assert normalize_digits("５０００") == "5000"
        assert normalize_digits("١٠٠") == "100"
        assert normalize_digits("abc") == "abc"

    def test_native_digit_budget(self):
        from agents.constraints import parse_budget_range
        assert parse_budget_range("₹५०,०००") == (None, 50000.0)
        assert parse_budget_range("５０００ EUR") == (None, 5000.0)


class TestClarifyAnswers:
    """extract_clarify_answers / parse_budget_range / strip_clarify_answers."""

    def test_parses_json_block(self):
        from agents.constraints import extract_clarify_answers
        text = 'A: x\n<clarify_answers>{"a": "1", "b": ["x", "y"]}</clarify_answers>'
        assert extract_clarify_answers(text) == {"a": "1", "b": ["x", "y"]}

    def test_garbage_returns_empty(self):
        from agents.constraints import extract_clarify_answers
        assert extract_clarify_answers("<clarify_answers>{oops</clarify_answers>") == {}
        assert extract_clarify_answers("no tag") == {}
        assert extract_clarify_answers(None) == {}

    def test_budget_range_two_numbers(self):
        from agents.constraints import parse_budget_range
        assert parse_budget_range("₹25,000–₹60,000") == (25000, 60000)

    def test_budget_cap_single_number(self):
        from agents.constraints import parse_budget_range
        assert parse_budget_range("Under ₹25,000") == (None, 25000)
        assert parse_budget_range("abc") == (None, None)

    def test_strip_removes_block(self):
        from agents.constraints import strip_clarify_answers
        text = 'Trip budget: ₹25,000\n<clarify_answers>{"budget_amount": "999"}</clarify_answers>'
        out = strip_clarify_answers(text)
        assert "999" not in out and "clarify_answers" not in out
