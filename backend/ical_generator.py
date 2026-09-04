"""iCalendar (.ics) file generator — converts itinerary dicts to RFC 5545 compliant .ics strings.

No external dependencies. Pure string formatting.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

_DESTINATION_TZ_MAP = {
    "tokyo": "Asia/Tokyo",
    "paris": "Europe/Paris",
    "london": "Europe/London",
    "new york": "America/New_York",
    "bali": "Asia/Makassar",
    "bangkok": "Asia/Bangkok",
    "dubai": "Asia/Dubai",
    "singapore": "Asia/Singapore",
    "sydney": "Australia/Sydney",
    "rome": "Europe/Rome",
    "barcelona": "Europe/Madrid",
    "amsterdam": "Europe/Amsterdam",
    "berlin": "Europe/Berlin",
    "istanbul": "Europe/Istanbul",
    "seoul": "Asia/Seoul",
    "hong kong": "Asia/Hong_Kong",
    "mumbai": "Asia/Kolkata",
    "delhi": "Asia/Kolkata",
    "goa": "Asia/Kolkata",
    "jaipur": "Asia/Kolkata",
    "kerala": "Asia/Kolkata",
    "los angeles": "America/Los_Angeles",
    "san francisco": "America/Los_Angeles",
    "las vegas": "America/Los_Angeles",
    "miami": "America/New_York",
    "chicago": "America/Chicago",
    "toronto": "America/Toronto",
    "mexico city": "America/Mexico_City",
    "rio de janeiro": "America/Sao_Paulo",
    "cape town": "Africa/Johannesburg",
    "cairo": "Africa/Cairo",
    "marrakech": "Africa/Casablanca",
}

_SLOT_TIMES = {
    "morning": 9,
    "afternoon": 13,
    "evening": 19,
}

_DEFAULT_DURATION_MINUTES = 120


def _guess_timezone(destination: str) -> str:
    """Match destination against known city names. Returns TZID or 'UTC'."""
    dest_lower = destination.lower()
    for city, tz in _DESTINATION_TZ_MAP.items():
        if city in dest_lower:
            return tz
    return "UTC"


def _parse_duration(duration_str: str) -> int:
    """Parse duration string like '3h', '1.5h', '30m', '2 hours' -> minutes.

    Returns 120 (2 hours) as fallback for unparseable strings.
    """
    if not duration_str:
        return _DEFAULT_DURATION_MINUTES

    s = duration_str.strip().lower()

    # "3h", "1.5h", "2hrs", "3 hrs"
    m = re.match(r"^(\d+(?:\.\d+)?)\s*h", s)
    if m:
        return int(float(m.group(1)) * 60)

    # "30m", "90 min", "45 minutes"
    m = re.match(r"^(\d+)\s*m", s)
    if m:
        return int(m.group(1))

    # "2 hours"
    m = re.match(r"^(\d+)\s*hour", s)
    if m:
        return int(m.group(1)) * 60

    return _DEFAULT_DURATION_MINUTES


def _escape_ical(text: str) -> str:
    """Escape special characters per RFC 5545."""
    if not text:
        return ""
    text = text.replace("\\", "\\\\")
    text = text.replace(";", "\\;")
    text = text.replace(",", "\\,")
    text = text.replace("\n", "\\n")
    text = text.replace("\r", "")
    return text


def _fold_line(line: str) -> str:
    """Fold long lines at 75 chars per RFC 5545 (with space continuation)."""
    if len(line) <= 75:
        return line
    parts = []
    while len(line) > 75:
        parts.append(line[:75])
        line = " " + line[75:]
    parts.append(line)
    return "\r\n".join(parts)


def _format_ical_datetime(dt: datetime) -> str:
    """Format datetime as YYYYMMDDTHHMMSS (local time, no Z suffix)."""
    return dt.strftime("%Y%m%dT%H%M%S")


def _format_ical_utc(dt: datetime) -> str:
    """Format datetime as YYYYMMDDTHHMMSSZ (UTC)."""
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def generate_ics(itinerary: dict, thread_id: str = "voyagerai") -> str:
    """Convert an itinerary dict to a complete .ics file string.

    - Day 1 = today's date
    - Each day's morning/afternoon/evening -> one VEVENT each
    - Includes VTIMEZONE block for the destination timezone
    - Each event has: UID, DTSTAMP, DTSTART (with TZID), DTEND, SUMMARY, LOCATION, DESCRIPTION
    """
    destination = itinerary.get("destination", "Untitled Trip")
    tzid = _guess_timezone(destination)
    days = itinerary.get("days", [])
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    now_utc = datetime.now(timezone.utc)

    lines: list[str] = []
    lines.append("BEGIN:VCALENDAR")
    lines.append("VERSION:2.0")
    lines.append("PRODID:-//VoyagerAI//Itinerary Export//EN")
    lines.append("CALSCALE:GREGORIAN")
    lines.append("METHOD:PUBLISH")

    # VTIMEZONE block
    lines.append(f"BEGIN:VTIMEZONE")
    lines.append(f"TZID:{tzid}")
    lines.append(f"BEGIN:STANDARD")
    lines.append(f"DTSTART:19700101T000000")
    lines.append(f"TZNAME:{tzid.split('/')[-1].replace('_', ' ')}")
    lines.append(f"END:STANDARD")
    lines.append(f"END:VTIMEZONE")

    for day in days:
        day_num = day.get("day", 1)
        day_date = today + timedelta(days=day_num - 1)
        transport = day.get("transport", "")
        accommodation = day.get("accommodation", "")
        tips = day.get("tips", [])

        for slot_name in ("morning", "afternoon", "evening"):
            slot = day.get(slot_name)
            if not slot or not slot.get("activity"):
                continue

            activity = slot.get("activity", "")
            location = slot.get("location", "")
            cost = slot.get("cost_usd")
            duration_str = slot.get("duration", "")

            start_hour = _SLOT_TIMES.get(slot_name, 9)
            start_dt = day_date.replace(hour=start_hour, minute=0, second=0, microsecond=0)
            duration_min = _parse_duration(duration_str)
            end_dt = start_dt + timedelta(minutes=duration_min)

            # Build description
            desc_parts = []
            if cost is not None:
                desc_parts.append(f"Cost: ${cost}")
            if transport:
                desc_parts.append(f"Transport: {transport}")
            if accommodation:
                desc_parts.append(f"Stay: {accommodation}")
            if tips:
                desc_parts.append("Tips: " + "; ".join(tips))
            description = "\\n".join(desc_parts) if desc_parts else ""

            uid = f"{thread_id}-day{day_num}-{slot_name}@voyagerai"

            lines.append("BEGIN:VEVENT")
            lines.append(f"UID:{uid}")
            lines.append(f"DTSTAMP:{_format_ical_utc(now_utc)}")
            lines.append(f"DTSTART;TZID={tzid}:{_format_ical_datetime(start_dt)}")
            lines.append(f"DTEND;TZID={tzid}:{_format_ical_datetime(end_dt)}")
            lines.append(f"SUMMARY:{_escape_ical(activity)}")
            if location:
                lines.append(f"LOCATION:{_escape_ical(location)}")
            if description:
                lines.append(f"DESCRIPTION:{description}")
            lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")

    # Fold all lines and join with CRLF (RFC 5545 requirement)
    folded = [_fold_line(line) for line in lines]
    return "\r\n".join(folded) + "\r\n"
