"""Tests for ical_generator — pure function tests, no Redis/auth needed."""

from __future__ import annotations

from ical_generator import (
    _escape_ical,
    _fold_line,
    _guess_timezone,
    _parse_duration,
    _parse_slot_time,
    generate_ics,
)


def _make_itinerary(destination="Paris, France", days=3):
    day_list = []
    for i in range(1, days + 1):
        day_list.append({
            "day": i,
            "theme": f"Day {i}",
            "morning": {"activity": f"Morning Activity {i}", "location": f"Location M{i}", "cost_usd": 10, "duration": "2h"},
            "afternoon": {"activity": f"Afternoon Activity {i}", "location": f"Location A{i}", "cost_usd": 20, "duration": "3h"},
            "evening": {"activity": f"Evening Activity {i}", "location": f"Location E{i}", "cost_usd": 30, "duration": "1.5h"},
            "transport": "Metro",
            "accommodation": "3-star hotel",
            "daily_cost_usd": 400,
            "tips": ["Book tickets online"],
        })
    return {
        "destination": destination,
        "total_days": days,
        "estimated_total_cost_usd": 1200,
        "budget_status": "within",
        "visa_note": "Schengen visa required",
        "best_season_note": "April-June",
        "days": day_list,
        "warnings": ["Pickpockets near tourist spots"],
        "packing_essentials": ["Comfortable shoes"],
    }


class TestIcalBasicStructure:
    def test_generate_ics_basic_structure(self):
        ics = generate_ics(_make_itinerary())
        assert ics.startswith("BEGIN:VCALENDAR")
        assert ics.rstrip().endswith("END:VCALENDAR")
        assert "VERSION:2.0" in ics
        assert "PRODID:" in ics

    def test_generate_ics_creates_event_per_slot(self):
        ics = generate_ics(_make_itinerary(days=3))
        vevent_count = ics.count("BEGIN:VEVENT")
        assert vevent_count == 9  # 3 days × 3 slots

    def test_generate_ics_skips_empty_slots(self):
        itinerary = _make_itinerary(days=1)
        itinerary["days"][0]["morning"]["activity"] = ""
        itinerary["days"][0]["afternoon"] = None
        ics = generate_ics(itinerary)
        vevent_count = ics.count("BEGIN:VEVENT")
        assert vevent_count == 1  # only evening

    def test_generate_ics_includes_location(self):
        ics = generate_ics(_make_itinerary(days=1))
        assert "LOCATION:Location M1" in ics
        assert "LOCATION:Location A1" in ics

    def test_generate_ics_includes_description(self):
        ics = generate_ics(_make_itinerary(days=1))
        assert "DESCRIPTION:" in ics
        assert "Cost:" in ics
        assert "Transport:" in ics
        assert "Tips:" in ics


class TestIcalTimezone:
    def test_generate_ics_timezone_tokyo(self):
        ics = generate_ics(_make_itinerary(destination="Tokyo, Japan"))
        assert "TZID:Asia/Tokyo" in ics

    def test_generate_ics_timezone_unknown_falls_back_to_utc(self):
        ics = generate_ics(_make_itinerary(destination="Mars Colony"))
        assert "TZID:UTC" in ics

    def test_guess_timezone_paris(self):
        assert _guess_timezone("Paris, France") == "Europe/Paris"

    def test_guess_timezone_new_york(self):
        assert _guess_timezone("New York, USA") == "America/New_York"

    def test_guess_timezone_unknown(self):
        assert _guess_timezone("Atlantis") == "UTC"


class TestDurationParsing:
    def test_parse_duration_hours(self):
        assert _parse_duration("3h") == 180

    def test_parse_duration_decimal_hours(self):
        assert _parse_duration("1.5h") == 90

    def test_parse_duration_minutes(self):
        assert _parse_duration("30m") == 30

    def test_parse_duration_hours_word(self):
        assert _parse_duration("2 hours") == 120

    def test_parse_duration_fallback(self):
        assert _parse_duration("unknown") == 120

    def test_parse_duration_empty(self):
        assert _parse_duration("") == 120


class TestEscapingAndFolding:
    def test_escape_ical_special_chars(self):
        assert _escape_ical("Hello, World;") == "Hello\\, World\\;"
        assert _escape_ical("Line1\nLine2") == "Line1\\nLine2"
        assert _escape_ical("Back\\Slash") == "Back\\\\Slash"

    def test_fold_line_short(self):
        assert _fold_line("SHORT") == "SHORT"

    def test_fold_line_long(self):
        long_line = "A" * 100
        folded = _fold_line(long_line)
        lines = folded.split("\r\n")
        assert len(lines) == 2
        assert len(lines[0]) == 75
        assert lines[1].startswith(" ")


class TestSlotTime:
    """Phase 2: slot.time drives event start times when present."""

    def test_parse_slot_time_24h(self):
        assert _parse_slot_time("09:30") == (9, 30)
        assert _parse_slot_time("14:00") == (14, 0)
        assert _parse_slot_time("8:15") == (8, 15)

    def test_parse_slot_time_ampm(self):
        assert _parse_slot_time("9:30 AM") == (9, 30)
        assert _parse_slot_time("2:00 PM") == (14, 0)
        assert _parse_slot_time("2pm") == (14, 0)

    def test_parse_slot_time_noon_midnight_edges(self):
        assert _parse_slot_time("12:00 PM") == (12, 0)
        assert _parse_slot_time("12:00 AM") == (0, 0)

    def test_parse_slot_time_invalid(self):
        assert _parse_slot_time("25:00") is None
        assert _parse_slot_time("13pm") is None
        assert _parse_slot_time("garbage") is None
        assert _parse_slot_time(None) is None
        assert _parse_slot_time("") is None

    def test_generate_ics_uses_slot_time(self):
        itinerary = _make_itinerary(days=1)
        itinerary["days"][0]["morning"]["time"] = "09:30"
        itinerary["days"][0]["afternoon"]["time"] = "14:45"
        ics = generate_ics(itinerary)
        assert "T093000" in ics
        assert "T144500" in ics
        # Evening has no time → 19:00 default
        assert "T190000" in ics

    def test_generate_ics_falls_back_to_slot_defaults(self):
        ics = generate_ics(_make_itinerary(days=1))
        assert "T090000" in ics   # morning
        assert "T130000" in ics   # afternoon
        assert "T190000" in ics   # evening

    def test_description_includes_why_and_book(self):
        itinerary = _make_itinerary(days=1)
        itinerary["days"][0]["morning"]["why"] = "Beat the crowds"
        itinerary["days"][0]["morning"]["book"] = "Entry 10 EUR, book ahead"
        ics = generate_ics(itinerary)
        assert "Note: Beat the crowds" in ics
        assert "Booking: Entry 10 EUR" in ics
