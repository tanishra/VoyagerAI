"""Travel Planning AI Agent — FastAPI Backend.

A single-file production backend that orchestrates a Gemini 2.5 Pro agent
through a **manual** function-calling loop to generate, validate, and enrich
multi-day travel itineraries.

Architecture
~~~~~~~~~~~~
* **Agent pattern**: one Gemini chat with three declared tool functions.
* **Tools**:
    1. ``generate_itinerary`` — sub-calls Gemini for structured JSON output.
    2. ``validate_constraints`` — pure-Python budget & consistency checks.
    3. ``enrich_day`` — sub-calls Gemini for practical travel tips.
* **Endpoints**: ``GET /health``, ``POST /plan``, ``POST /replan-day``.

Security: all inputs are validated through Pydantic with field_validators;
the API key is loaded from ``.env`` and never exposed in responses.
"""

from __future__ import annotations

import inspect
import json
import logging
import os
import textwrap
from enum import Enum
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types
from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Configuration & Logging
# ---------------------------------------------------------------------------

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("travel_agent")

GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not set in the environment.")

MODEL_ID: str = "gemini-2.5-pro"
MAX_AGENT_ITERATIONS: int = 10

# ---------------------------------------------------------------------------
# Google GenAI Client
# ---------------------------------------------------------------------------

client = genai.Client(api_key=GEMINI_API_KEY)

# ---------------------------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Travel Planning AI Agent",
    version="1.0.0",
    description="Generates, validates, and enriches multi-day travel itineraries using Gemini 2.5 Pro.",
)

ALLOWED_ORIGINS: list[str] = [
    orig.strip()
    for orig in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if orig.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TravelStyle(str, Enum):
    """Supported travel styles."""

    ADVENTURE = "adventure"
    CULTURAL = "cultural"
    LUXURY = "luxury"
    BUDGET = "budget"


class GroupType(str, Enum):
    """Supported group compositions."""

    SOLO = "solo"
    COUPLE = "couple"
    FAMILY = "family"


# ---------------------------------------------------------------------------
# Pydantic Models — Request
# ---------------------------------------------------------------------------


class PlanRequest(BaseModel):
    """Incoming request for a new travel plan."""

    destination: str = Field(..., min_length=1, max_length=200, description="Travel destination city or region.")
    days: int = Field(..., ge=1, le=30, description="Number of travel days (1–30).")
    budget_usd: int = Field(..., ge=50, description="Total trip budget in USD (minimum $50).")
    travel_style: TravelStyle = Field(..., description="Preferred travel style.")
    group_type: GroupType = Field(..., description="Group composition.")
    dietary: Optional[str] = Field(None, max_length=500, description="Dietary restrictions or preferences.")
    constraints: Optional[str] = Field(None, max_length=1000, description="Additional constraints or requests.")

    @field_validator("destination")
    @classmethod
    def destination_must_be_meaningful(cls, v: str) -> str:
        """Reject trivially short or numeric-only destinations."""
        stripped = v.strip()
        if len(stripped) < 2:
            raise ValueError("Destination must be at least 2 characters long.")
        if stripped.isdigit():
            raise ValueError("Destination cannot be purely numeric.")
        return stripped

    @field_validator("dietary", "constraints", mode="before")
    @classmethod
    def strip_optional_strings(cls, v: str | None) -> str | None:
        """Strip whitespace from optional string fields; treat empty as None."""
        if v is None:
            return None
        stripped = v.strip()
        return stripped if stripped else None


# ---------------------------------------------------------------------------
# Pydantic Models — Itinerary (Output / ReplanRequest payload)
# ---------------------------------------------------------------------------


class Activity(BaseModel):
    """A single time-slot activity within a day."""

    activity: str
    location: str
    cost_usd: int
    duration: str


class DayPlan(BaseModel):
    """One day of the itinerary."""

    day: int
    theme: str
    morning: Activity
    afternoon: Activity
    evening: Activity
    transport: str
    accommodation: str
    daily_cost_usd: int
    tips: list[str] = Field(default_factory=list)


class Itinerary(BaseModel):
    """Complete travel itinerary returned to the client."""

    destination: str
    total_days: int
    estimated_total_cost_usd: int
    budget_status: str
    visa_note: str
    best_season_note: str
    days: list[DayPlan]
    warnings: list[str] = Field(default_factory=list)
    packing_essentials: list[str] = Field(default_factory=list)


class PlanResponse(BaseModel):
    """Wrapper returned by ``POST /plan`` and ``POST /replan-day``."""

    success: bool = True
    itinerary: Optional[Itinerary] = None
    error: Optional[str] = None


class ReplanRequest(BaseModel):
    """Request to replan a specific day in an existing itinerary."""

    itinerary: Itinerary
    day_number: int = Field(..., ge=1, description="Day number to replan.")
    reason: str = Field(..., min_length=1, max_length=1000, description="Reason for replanning.")

    @field_validator("reason")
    @classmethod
    def reason_must_be_meaningful(cls, v: str) -> str:
        """Reject empty replan reasons."""
        stripped = v.strip()
        if len(stripped) < 2:
            raise ValueError("Please provide a meaningful reason for replanning.")
        return stripped


# ---------------------------------------------------------------------------
# Tool Function Implementations
# ---------------------------------------------------------------------------


async def _tool_generate_itinerary(
    destination: str,
    days: int,
    budget_usd: int,
    travel_style: str,
    group_type: str,
    dietary: str | None = None,
    constraints: str | None = None,
) -> dict:
    """Generate a complete structured itinerary via a Gemini sub-call.

    Uses ``response_mime_type='application/json'`` so Gemini returns valid JSON
    that matches the Itinerary schema.

    Returns:
        dict: The parsed itinerary dictionary.

    Raises:
        RuntimeError: If the Gemini call fails or returns unparseable output.
    """
    logger.info("Tool:generate_itinerary — destination=%s, days=%d, budget=%d", destination, days, budget_usd)

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
                temperature=0.7,
            ),
        )
        raw_text = response.text
        if not raw_text:
            raise RuntimeError("Gemini returned an empty response for itinerary generation.")
        return json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse itinerary JSON from Gemini: %s", exc)
        raise RuntimeError(f"Gemini returned invalid JSON: {exc}") from exc
    except Exception as exc:
        logger.error("Gemini itinerary generation failed: %s", exc)
        raise RuntimeError(f"Itinerary generation error: {exc}") from exc


def _tool_validate_constraints(
    itinerary_json: dict,
    budget_usd: int,
    dietary: str | None = None,
    constraints: str | None = None,
) -> dict:
    """Validate the itinerary against budget, day-count, and cost consistency.

    This is a **pure Python** function — no Gemini calls.

    Returns:
        dict: Validation report with ``valid``, ``budget_status``,
              ``calculated_total_cost``, ``issues``, and ``warnings``.
    """
    logger.info("Tool:validate_constraints — budget=%d", budget_usd)

    issues: list[str] = []
    warnings: list[str] = []

    # --- Day count consistency ---
    expected_days: int = itinerary_json.get("total_days", 0)
    actual_days: int = len(itinerary_json.get("days", []))
    if actual_days != expected_days:
        issues.append(
            f"Day count mismatch: header says {expected_days} days but {actual_days} day(s) found."
        )

    # --- Cost calculations ---
    calculated_total: int = 0
    for day_obj in itinerary_json.get("days", []):
        activity_sum = sum(
            day_obj.get(slot, {}).get("cost_usd", 0)
            for slot in ("morning", "afternoon", "evening")
        )
        daily_cost: int = day_obj.get("daily_cost_usd", 0)

        # Activity costs should not exceed the daily cost (which includes
        # transport + accommodation).  Flag only if activities alone exceed it.
        if activity_sum > daily_cost:
            warnings.append(
                f"Day {day_obj.get('day', '?')}: activity costs (${activity_sum}) "
                f"exceed reported daily cost (${daily_cost})."
            )

        calculated_total += daily_cost

    # --- Budget comparison ---
    header_total: int = itinerary_json.get("estimated_total_cost_usd", 0)
    if abs(calculated_total - header_total) > max(50, header_total * 0.05):
        warnings.append(
            f"Header total (${header_total}) differs from sum of daily costs (${calculated_total})."
        )

    if calculated_total > budget_usd:
        budget_status = "over"
        issues.append(
            f"Calculated total ${calculated_total} exceeds budget of ${budget_usd}."
        )
    elif calculated_total < budget_usd * 0.5:
        budget_status = "under"
        warnings.append(
            f"Calculated total ${calculated_total} uses less than 50% of budget ${budget_usd}."
        )
    else:
        budget_status = "within"

    # --- Dietary / constraints sanity (soft warnings) ---
    if dietary:
        warnings.append(f"Dietary preference '{dietary}' noted — please verify meal suggestions manually.")
    if constraints:
        warnings.append(f"User constraint '{constraints}' noted — verify compliance in activities.")

    valid = len(issues) == 0

    return {
        "valid": valid,
        "budget_status": budget_status,
        "calculated_total_cost": calculated_total,
        "issues": issues,
        "warnings": warnings,
    }


async def _tool_enrich_day(
    day_json: dict,
    destination: str,
    day_number: int,
) -> dict:
    """Enrich a single day with practical tips via a Gemini sub-call.

    Adds weather context, local customs, and logistical advice to the
    existing day object.

    Returns:
        dict: The enriched day dictionary (original fields plus extra tips/warnings).

    Raises:
        RuntimeError: If the Gemini call fails.
    """
    logger.info("Tool:enrich_day — destination=%s, day=%d", destination, day_number)

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
                temperature=0.6,
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


# ---------------------------------------------------------------------------
# Tool Dispatch Map
# ---------------------------------------------------------------------------

TOOL_DISPATCH: dict[str, callable] = {
    "generate_itinerary": _tool_generate_itinerary,
    "validate_constraints": _tool_validate_constraints,
    "enrich_day": _tool_enrich_day,
}

# ---------------------------------------------------------------------------
# Gemini Function Declarations (for the agent)
# ---------------------------------------------------------------------------

_fn_generate_itinerary = types.FunctionDeclaration(
    name="generate_itinerary",
    description="Generate a complete multi-day travel itinerary as structured JSON.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "destination": types.Schema(type=types.Type.STRING, description="Travel destination."),
            "days": types.Schema(type=types.Type.INTEGER, description="Number of days."),
            "budget_usd": types.Schema(type=types.Type.INTEGER, description="Total budget in USD."),
            "travel_style": types.Schema(type=types.Type.STRING, description="Travel style: adventure/cultural/luxury/budget."),
            "group_type": types.Schema(type=types.Type.STRING, description="Group type: solo/couple/family."),
            "dietary": types.Schema(type=types.Type.STRING, description="Dietary restrictions (optional)."),
            "constraints": types.Schema(type=types.Type.STRING, description="Additional constraints (optional)."),
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
            "itinerary_json": types.Schema(type=types.Type.OBJECT, description="The full itinerary JSON object to validate."),
            "budget_usd": types.Schema(type=types.Type.INTEGER, description="Total budget in USD."),
            "dietary": types.Schema(type=types.Type.STRING, description="Dietary restrictions (optional)."),
            "constraints": types.Schema(type=types.Type.STRING, description="Additional constraints (optional)."),
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
            "day_json": types.Schema(type=types.Type.OBJECT, description="The day plan JSON object to enrich."),
            "destination": types.Schema(type=types.Type.STRING, description="Travel destination."),
            "day_number": types.Schema(type=types.Type.INTEGER, description="The day number being enriched."),
        },
        required=["day_json", "destination", "day_number"],
    ),
)

AGENT_TOOLS = types.Tool(
    function_declarations=[_fn_generate_itinerary, _fn_validate_constraints, _fn_enrich_day],
)

# ---------------------------------------------------------------------------
# Agent System Prompt
# ---------------------------------------------------------------------------

AGENT_SYSTEM_PROMPT = textwrap.dedent("""\
    You are a meticulous Travel Planning Agent. Your job is to create high-quality,
    validated travel itineraries.

    **Workflow — follow this order strictly:**
    1. Call `generate_itinerary` with the user's parameters to produce the initial plan.
    2. Call `validate_constraints` with the generated itinerary and budget to verify
       budget compliance and internal consistency.
    3. If validation fails, adjust the itinerary mentally and call `generate_itinerary`
       again with tighter budget guidance, then re-validate. Repeat until valid.
    4. Once the itinerary is valid, call `enrich_day` for EACH day in the itinerary
       (call it separately for every day[0], day[1], ..., day[N]) to add practical tips,
       weather context, and local custom advice.
    5. Return the fully enriched itinerary JSON as plain text
       (no markdown fences, no commentary — just the JSON object).

    **Rules:**
    - Always call generate_itinerary FIRST.
    - Always call validate_constraints AFTER generating.
    - Call enrich_day ONCE PER DAY after validation passes.
    - If the validation shows issues, regenerate with corrections.
    - Your final text response must be ONLY the valid JSON itinerary object — nothing else.
""")

REPLAN_SYSTEM_PROMPT = textwrap.dedent("""\
    You are a meticulous Travel Planning Agent. The user has an existing itinerary
    and wants to replan a specific day.

    **Workflow:**
    1. Review the existing itinerary and the user's reason for replanning.
    2. Call `generate_itinerary` to produce an updated itinerary that addresses
       the user's concerns while keeping other days intact.
    3. Call `validate_constraints` to verify the updated itinerary is still valid.
    4. If validation fails, regenerate with corrections.
    5. Once valid, call `enrich_day` for the replanned day to add practical tips.
    6. Return the COMPLETE updated itinerary (all days, not just the changed day)
       as plain JSON text — no markdown fences, no commentary.

    **Rules:**
    - Keep all other days unchanged unless the budget rebalance requires it.
    - Call enrich_day on at least the replanned day.
    - Your final text response must be ONLY the valid JSON itinerary object.
""")


# ---------------------------------------------------------------------------
# Agent Loop — Manual Function Calling
# ---------------------------------------------------------------------------


async def _execute_tool_call(function_call: types.FunctionCall) -> str:
    """Dispatch a single function call to the matching tool implementation.

    Args:
        function_call: The ``FunctionCall`` object from Gemini's response.

    Returns:
        str: JSON-serialised result to feed back to the model.
    """
    name: str = function_call.name
    args: dict = dict(function_call.args) if function_call.args else {}

    logger.info("Executing tool: %s with args keys: %s", name, list(args.keys()))

    handler = TOOL_DISPATCH.get(name)
    if handler is None:
        error_msg = f"Unknown tool requested: {name}"
        logger.warning(error_msg)
        return json.dumps({"error": error_msg})

    try:
        if inspect.iscoroutinefunction(handler):
            result = await handler(**args)
        else:
            result = handler(**args)
        return json.dumps(result, default=str)
    except Exception as exc:  # noqa: BLE001
        logger.error("Tool %s raised: %s", name, exc)
        return json.dumps({"error": str(exc)})


async def run_agent(system_prompt: str, user_message: str) -> dict:
    """Run the manual function-calling agent loop.

    Sends the user message to Gemini with tool declarations, then loops:
    * If the response contains function calls → execute them → send results back.
    * If the response is pure text → parse as JSON and return.
    * Safety limit: ``MAX_AGENT_ITERATIONS`` iterations.

    Args:
        system_prompt: The system instruction for the agent.
        user_message: The initial user prompt.

    Returns:
        dict: The parsed itinerary JSON.

    Raises:
        HTTPException: On Gemini errors, parse failures, or iteration exhaustion.
    """
    logger.info("Agent loop starting. User message length: %d chars", len(user_message))

    # Build the initial conversation history.
    contents: list[types.Content] = [
        types.Content(role="user", parts=[types.Part.from_text(text=user_message)]),
    ]

    for iteration in range(1, MAX_AGENT_ITERATIONS + 1):
        logger.info("Agent iteration %d/%d", iteration, MAX_AGENT_ITERATIONS)

        try:
            response = client.models.generate_content(
                model=MODEL_ID,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    tools=[AGENT_TOOLS],
                    temperature=0.4,
                ),
            )
        except Exception as exc:
            logger.error("Gemini API call failed on iteration %d: %s", iteration, exc)
            raise HTTPException(
                status_code=502,
                detail=f"Gemini API error: {exc}",
            ) from exc

        # Check if we got any candidates at all.
        if not response.candidates:
            logger.error("Gemini returned no candidates on iteration %d", iteration)
            raise HTTPException(status_code=502, detail="Gemini returned no response candidates.")

        candidate = response.candidates[0]
        parts = candidate.content.parts if candidate.content else []

        # Collect function calls from all parts.
        function_calls = [p.function_call for p in parts if p.function_call]

        if function_calls:
            # --- Execute each function call and build function-response parts ---
            # Append the model's response (with the function_call parts) first.
            contents.append(candidate.content)

            function_response_parts: list[types.Part] = []
            for fc in function_calls:
                result_json = await _execute_tool_call(fc)
                function_response_parts.append(
                    types.Part.from_function_response(
                        name=fc.name,
                        response=json.loads(result_json),
                    )
                )

            contents.append(
                types.Content(role="user", parts=function_response_parts),
            )
            continue  # Next iteration — let the model process results.

        # --- No function calls → model returned final text ---
        text_parts = [p.text for p in parts if p.text]
        final_text = "\n".join(text_parts).strip()

        if not final_text:
            logger.warning("Empty text response on iteration %d; continuing.", iteration)
            continue

        logger.info("Agent returned final text (%d chars) on iteration %d", len(final_text), iteration)

        # Strip markdown code fences if the model wrapped output.
        cleaned = final_text
        if cleaned.startswith("```"):
            # Remove opening fence (possibly ```json)
            first_newline = cleaned.index("\n") if "\n" in cleaned else len(cleaned)
            cleaned = cleaned[first_newline + 1 :]
        if cleaned.endswith("```"):
            cleaned = cleaned[: -3]
        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse agent final response as JSON: %s", exc)
            raise HTTPException(
                status_code=502,
                detail="Agent returned non-JSON response. Please try again.",
            ) from exc

    # Exhausted iterations without a text answer.
    logger.error("Agent loop exhausted %d iterations without final response.", MAX_AGENT_ITERATIONS)
    raise HTTPException(
        status_code=500,
        detail="Agent could not produce a result within the iteration limit.",
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health", summary="Health check", tags=["ops"])
async def health() -> dict[str, str]:
    """Return a simple health-check response.

    Returns:
        dict: ``{"status": "ok"}``
    """
    return {"status": "ok"}


@app.post("/plan", response_model=PlanResponse, summary="Generate travel plan", tags=["planning"])
async def plan(request: PlanRequest) -> PlanResponse:
    """Generate a validated, multi-day travel itinerary.

    The endpoint orchestrates a Gemini agent that:
    1. Generates an itinerary via ``generate_itinerary``.
    2. Validates it via ``validate_constraints``.
    3. Returns the final JSON.

    Args:
        request: The travel planning parameters.

    Returns:
        PlanResponse: Wrapper containing the complete ``Itinerary``.

    Raises:
        HTTPException 400: Invalid input (Pydantic catches most).
        HTTPException 500: Internal processing error.
        HTTPException 502: Upstream Gemini failure.
    """
    logger.info(
        "POST /plan — destination=%s, days=%d, budget=%d, style=%s, group=%s",
        request.destination,
        request.days,
        request.budget_usd,
        request.travel_style.value,
        request.group_type.value,
    )

    user_message = (
        f"Plan a {request.days}-day trip to {request.destination}. "
        f"Budget: ${request.budget_usd} USD. "
        f"Style: {request.travel_style.value}. "
        f"Group: {request.group_type.value}. "
        f"Dietary: {request.dietary or 'None'}. "
        f"Constraints: {request.constraints or 'None'}."
    )

    try:
        raw_itinerary = await run_agent(AGENT_SYSTEM_PROMPT, user_message)
        itinerary = Itinerary.model_validate(raw_itinerary)
        return PlanResponse(success=True, itinerary=itinerary)
    except HTTPException:
        raise  # Already well-formed; re-raise.
    except Exception as exc:
        logger.error("Unexpected error in /plan: %s", exc)
        return PlanResponse(success=False, error=f"Planning failed: {exc}")


@app.post("/replan-day", response_model=PlanResponse, summary="Replan a specific day", tags=["planning"])
async def replan_day(request: ReplanRequest) -> PlanResponse:
    """Replan a specific day within an existing itinerary.

    The agent receives the full current itinerary plus the user's reason
    for replanning and produces an updated itinerary.

    Args:
        request: Contains the current itinerary, day number, and reason.

    Returns:
        PlanResponse: Wrapper containing the updated ``Itinerary``.

    Raises:
        HTTPException 400: Day number out of range.
        HTTPException 500: Internal processing error.
        HTTPException 502: Upstream Gemini failure.
    """
    logger.info(
        "POST /replan-day — day=%d, reason=%s",
        request.day_number,
        request.reason[:80],
    )

    # Validate that day_number exists in the itinerary.
    if request.day_number > request.itinerary.total_days or request.day_number < 1:
        raise HTTPException(
            status_code=400,
            detail=f"Day {request.day_number} is out of range. Itinerary has {request.itinerary.total_days} days.",
        )

    itinerary_dict = request.itinerary.model_dump()

    user_message = (
        f"Here is the current itinerary:\n"
        f"{json.dumps(itinerary_dict, indent=2)}\n\n"
        f"Please replan Day {request.day_number}.\n"
        f"Reason: {request.reason}\n\n"
        f"Return the COMPLETE updated itinerary (all days) as JSON."
    )

    try:
        raw_itinerary = await run_agent(REPLAN_SYSTEM_PROMPT, user_message)
        itinerary = Itinerary.model_validate(raw_itinerary)
        return PlanResponse(success=True, itinerary=itinerary)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Unexpected error in /replan-day: %s", exc)
        return PlanResponse(success=False, error=f"Replanning failed: {exc}")


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
