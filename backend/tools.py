"""Tool functions for the travel planning agent: generate, validate, enrich."""

from __future__ import annotations

import json
import logging
import textwrap
from collections.abc import Callable
from functools import lru_cache

from google.genai import types

from config import (
    MODEL_ID,
    CREATION_TEMPERATURE,
    ENRICH_TEMPERATURE,
    CACHE_MAXSIZE,
    VALIDATION_COST_TOLERANCE_FLAT,
    VALIDATION_COST_TOLERANCE_PCT,
    VALIDATION_UNDER_BUDGET_THRESHOLD,
    client,
)

logger = logging.getLogger("travel_agent.tools")


async def tool_generate_itinerary(
    destination: str,
    days: int,
    budget_usd: int,
    travel_style: str,
    group_type: str,
    dietary: str | None = None,
    constraints: str | None = None,
) -> dict:
    """Generate a complete structured itinerary via a Gemini sub-call."""
    logger.info(
        "generate_itinerary — destination=%s, days=%d, budget=%d", destination, days, budget_usd
    )

    prompt = textwrap.dedent(f"""\
        You are an expert travel planner. Create a detailed {days}-day travel
        itinerary for {destination}.

        Requirements:
        - Budget: ${budget_usd} USD total
        - Travel style: {travel_style}
        - Group type: {group_type}
        - Dietary restrictions: {dietary or 'None'}
        - Additional constraints: {constraints or 'None'}

        Return a JSON object with EXACTLY this structure:
        {{
            "destination": "{destination}",
            "total_days": {days},
            "estimated_total_cost_usd": <int>,
            "budget_status": "within" | "over" | "under",
            "visa_note": "<visa information>",
            "best_season_note": "<best time to visit>",
            "days": [
                {{
                    "day": <int>,
                    "theme": "<day theme>",
                    "morning": {{"activity": "<str>", "location": "<str>", "cost_usd": <int>, "duration": "<str>"}},
                    "afternoon": {{"activity": "<str>", "location": "<str>", "cost_usd": <int>, "duration": "<str>"}},
                    "evening": {{"activity": "<str>", "location": "<str>", "cost_usd": <int>, "duration": "<str>"}},
                    "transport": "<transport for the day>",
                    "accommodation": "<accommodation>",
                    "daily_cost_usd": <int>,
                    "tips": ["<tip1>", "<tip2>"]
                }}
            ],
            "warnings": ["<warning1>"],
            "packing_essentials": ["<item1>", "<item2>"]
        }}

        Ensure daily_cost_usd equals the sum of morning + afternoon + evening costs
        plus reasonable transport and accommodation estimates.
        Ensure estimated_total_cost_usd equals the sum of all daily_cost_usd values.
        Keep the total within the budget of ${budget_usd}.
    """)

    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=CREATION_TEMPERATURE,
            ),
        )
        raw_text = response.text
        if not raw_text:
            raise RuntimeError("Gemini returned an empty response for itinerary generation.")
        return json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse itinerary JSON: %s", exc)
        raise RuntimeError(f"Gemini returned invalid JSON: {exc}") from exc
    except Exception as exc:
        logger.error("Gemini itinerary generation failed: %s", exc)
        raise RuntimeError(f"Itinerary generation error: {exc}") from exc


@lru_cache(maxsize=CACHE_MAXSIZE)
def _cached_validate(itinerary_json_str: str, budget_usd: int, dietary: str, constraints: str) -> str:
    """Cached validation core — accepts JSON string for hashability."""
    return json.dumps(_validate_impl(json.loads(itinerary_json_str), budget_usd, dietary or None, constraints or None))


def _validate_impl(
    itinerary_json: dict,
    budget_usd: int,
    dietary: str | None = None,
    constraints: str | None = None,
) -> dict:
    """Pure validation logic."""
    issues: list[str] = []
    warnings: list[str] = []

    expected_days = itinerary_json.get("total_days", 0)
    actual_days = len(itinerary_json.get("days", []))
    if actual_days != expected_days:
        issues.append(
            f"Day count mismatch: header says {expected_days} days but {actual_days} day(s) found."
        )

    calculated_total = 0
    for day_obj in itinerary_json.get("days", []):
        activity_sum = sum(
            day_obj.get(slot, {}).get("cost_usd", 0)
            for slot in ("morning", "afternoon", "evening")
        )
        daily_cost = day_obj.get("daily_cost_usd", 0)
        if activity_sum > daily_cost:
            warnings.append(
                f"Day {day_obj.get('day', '?')}: activity costs (${activity_sum}) "
                f"exceed reported daily cost (${daily_cost})."
            )
        calculated_total += daily_cost

    header_total = itinerary_json.get("estimated_total_cost_usd", 0)
    if abs(calculated_total - header_total) > max(VALIDATION_COST_TOLERANCE_FLAT, header_total * VALIDATION_COST_TOLERANCE_PCT):
        warnings.append(
            f"Header total (${header_total}) differs from sum of daily costs (${calculated_total})."
        )

    if calculated_total > budget_usd:
        budget_status = "over"
        issues.append(f"Calculated total ${calculated_total} exceeds budget of ${budget_usd}.")
    elif calculated_total < budget_usd * VALIDATION_UNDER_BUDGET_THRESHOLD:
        budget_status = "under"
        warnings.append(
            f"Calculated total ${calculated_total} uses less than 50% of budget ${budget_usd}."
        )
    else:
        budget_status = "within"

    if dietary:
        warnings.append(f"Dietary preference '{dietary}' noted — please verify meal suggestions manually.")
    if constraints:
        warnings.append(f"User constraint '{constraints}' noted — verify compliance in activities.")

    return {
        "valid": len(issues) == 0,
        "budget_status": budget_status,
        "calculated_total_cost": calculated_total,
        "issues": issues,
        "warnings": warnings,
    }


def tool_validate_constraints(
    itinerary_json: dict,
    budget_usd: int,
    dietary: str | None = None,
    constraints: str | None = None,
) -> dict:
    """Validate itinerary against budget, day-count, and cost consistency. Uses LRU cache."""
    logger.info("validate_constraints — budget=%d", budget_usd)
    serialized = json.dumps(itinerary_json, sort_keys=True)
    result_str = _cached_validate(serialized, budget_usd, dietary or "", constraints or "")
    return json.loads(result_str)


async def tool_enrich_day(
    day_json: dict,
    destination: str,
    day_number: int,
) -> dict:
    """Enrich a single day with practical tips via a Gemini sub-call."""
    logger.info("enrich_day — destination=%s, day=%d", destination, day_number)

    prompt = textwrap.dedent(f"""\
        You are a local travel expert for {destination}.
        Given this day plan (Day {day_number}):

        {json.dumps(day_json, indent=2)}

        Add practical, actionable information. Return ONLY a JSON object with
        the same structure as the input, but with an enriched "tips" array that
        includes:
        - Weather tips for this time of year
        - Local customs or etiquette relevant to the activities
        - Safety advice
        - Money-saving suggestions
        - Any logistical warnings (closures, peak hours, etc.)

        Keep existing fields unchanged; only enhance the "tips" list.
    """)

    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=ENRICH_TEMPERATURE,
            ),
        )
        raw_text = response.text
        if not raw_text:
            raise RuntimeError("Gemini returned an empty response for day enrichment.")
        return json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse enriched-day JSON: %s", exc)
        raise RuntimeError(f"Enrichment JSON parse error: {exc}") from exc
    except Exception as exc:
        logger.error("Day enrichment failed: %s", exc)
        raise RuntimeError(f"Day enrichment error: {exc}") from exc


TOOL_DISPATCH: dict[str, Callable] = {
    "generate_itinerary": tool_generate_itinerary,
    "validate_constraints": tool_validate_constraints,
    "enrich_day": tool_enrich_day,
}


_fn_generate_itinerary = types.FunctionDeclaration(
    name="generate_itinerary",
    description="Generate a complete multi-day travel itinerary as structured JSON.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "destination": types.Schema(type=types.Type.STRING, description="Travel destination."),
            "days": types.Schema(type=types.Type.INTEGER, description="Number of days."),
            "budget_usd": types.Schema(type=types.Type.INTEGER, description="Total budget in USD."),
            "travel_style": types.Schema(
                type=types.Type.STRING,
                description="Travel style: adventure/cultural/luxury/budget.",
            ),
            "group_type": types.Schema(
                type=types.Type.STRING, description="Group type: solo/couple/family."
            ),
            "dietary": types.Schema(
                type=types.Type.STRING, description="Dietary restrictions (optional)."
            ),
            "constraints": types.Schema(
                type=types.Type.STRING, description="Additional constraints (optional)."
            ),
        },
        required=["destination", "days", "budget_usd", "travel_style", "group_type"],
    ),
)

_fn_validate_constraints = types.FunctionDeclaration(
    name="validate_constraints",
    description="Validate itinerary against budget, day-count, and cost consistency. Pure computation, no AI call.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "itinerary_json": types.Schema(
                type=types.Type.OBJECT, description="The full itinerary JSON object to validate."
            ),
            "budget_usd": types.Schema(type=types.Type.INTEGER, description="Total budget in USD."),
            "dietary": types.Schema(
                type=types.Type.STRING, description="Dietary restrictions (optional)."
            ),
            "constraints": types.Schema(
                type=types.Type.STRING, description="Additional constraints (optional)."
            ),
        },
        required=["itinerary_json", "budget_usd"],
    ),
)

_fn_enrich_day = types.FunctionDeclaration(
    name="enrich_day",
    description="Enrich a single day of the itinerary with practical tips, weather context, and local customs.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "day_json": types.Schema(
                type=types.Type.OBJECT, description="The day plan JSON object to enrich."
            ),
            "destination": types.Schema(type=types.Type.STRING, description="Travel destination."),
            "day_number": types.Schema(type=types.Type.INTEGER, description="The day number being enriched."),
        },
        required=["day_json", "destination", "day_number"],
    ),
)

AGENT_TOOLS = types.Tool(
    function_declarations=[
        _fn_generate_itinerary,
        _fn_validate_constraints,
        _fn_enrich_day,
    ],
)
