"""Travel Planning AI Agent — FastAPI Backend.

Endpoints:
    GET  /health        — Health check.
    POST /plan          — Generate validated multi-day itinerary.
    POST /replan-day    — Replan a specific day in an existing itinerary.

Architecture:
    config.py   — Environment, client, constants.
    models.py   — Pydantic request/response schemas.
    tools.py    — Three function-calling tools (generate, validate, enrich).
    agent.py    — Manual function-calling loop over Gemini 2.5 Pro.
"""

from __future__ import annotations

import json
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from config import logger
from models import Itinerary, PlanRequest, PlanResponse, ReplanRequest
from agent import run_agent, AGENT_SYSTEM_PROMPT, REPLAN_SYSTEM_PROMPT

# ---------------------------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Travel Planning AI Agent",
    version="2.0.0",
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
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health", summary="Health check", tags=["ops"])
async def health() -> dict[str, str]:
    """Return a simple health-check response."""
    return {"status": "ok"}


@app.post("/plan", response_model=PlanResponse, summary="Generate travel plan", tags=["planning"])
async def plan(request: PlanRequest) -> PlanResponse:
    """Generate a validated, multi-day travel itinerary.

    Orchestrates a Gemini agent that:
    1. Generates an itinerary via ``generate_itinerary``.
    2. Validates it via ``validate_constraints``.
    3. Enriches each day via ``enrich_day``.
    4. Returns the final JSON.
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
        raise
    except Exception as exc:
        logger.error("Unexpected error in /plan: %s", exc)
        return PlanResponse(success=False, error=f"Planning failed: {exc}")


@app.post(
    "/replan-day",
    response_model=PlanResponse,
    summary="Replan a specific day",
    tags=["planning"],
)
async def replan_day(request: ReplanRequest) -> PlanResponse:
    """Replan a specific day within an existing itinerary.

    The agent receives the full current itinerary plus the user's reason
    for replanning and produces an updated itinerary.
    """
    logger.info(
        "POST /replan-day — day=%d, reason=%s",
        request.day_number,
        request.reason[:80],
    )

    if request.day_number > request.itinerary.total_days or request.day_number < 1:
        raise HTTPException(
            status_code=400,
            detail=f"Day {request.day_number} is out of range. "
                   f"Itinerary has {request.itinerary.total_days} days.",
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
