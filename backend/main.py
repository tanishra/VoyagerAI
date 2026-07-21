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

import asyncio
import json
import os
import time

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from auth import verify_api_key
from config import logger
from models import Itinerary, PlanRequest, PlanResponse, ReplanRequest
from agent import run_agent, AGENT_SYSTEM_PROMPT, REPLAN_SYSTEM_PROMPT
from tools import tool_enrich_day

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
# Rate Limiting
# ---------------------------------------------------------------------------

limiter = Limiter(key_func=get_remote_address, default_limits=["30/hour"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ---------------------------------------------------------------------------
# Parallel Day Enrichment
# ---------------------------------------------------------------------------


async def enrich_all_days_parallel(itinerary: dict) -> dict:
    """Enrich all days in the itinerary in parallel via asyncio.gather()."""
    days = itinerary.get("days", [])
    if not days:
        return itinerary

    destination = itinerary.get("destination", "")
    t0 = time.perf_counter()

    logger.info(
        "=== STEP 2/3: Enriching %d days in parallel via Gemini Flash ===",
        len(days),
    )

    tasks = [
        tool_enrich_day(day, destination, day["day"])
        for day in days
    ]
    enriched = await asyncio.gather(*tasks, return_exceptions=True)

    success_count = 0
    for i, result in enumerate(enriched):
        if isinstance(result, Exception):
            logger.error("Day %d enrichment failed after retries: %s", days[i]["day"], result)
        else:
            days[i] = result
            success_count += 1

    itinerary["days"] = days
    elapsed = time.perf_counter() - t0
    logger.info(
        "✓ Enrichment done: %d/%d days succeeded in %.1fs",
        success_count, len(days), elapsed,
    )
    return itinerary


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health", summary="Health check", tags=["ops"])
async def health() -> dict[str, str]:
    """Return a simple health-check response."""
    return {"status": "ok"}


@app.post(
    "/plan",
    response_model=PlanResponse,
    summary="Generate travel plan",
    tags=["planning"],
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("5/minute")
async def plan(plan_req: PlanRequest, request: Request) -> PlanResponse:
    """Generate a validated, multi-day travel itinerary.

    Orchestrates a Gemini agent that:
    1. Generates an itinerary via ``generate_itinerary``.
    2. Validates it via ``validate_constraints``.
    3. Enriches each day via ``enrich_day``.
    4. Returns the final JSON.
    """
    logger.info(
        "POST /plan — destination=%s, days=%d, budget=%d, style=%s, group=%s",
        plan_req.destination,
        plan_req.days,
        plan_req.budget_usd,
        plan_req.travel_style.value,
        plan_req.group_type.value,
    )

    user_message = (
        f"Plan a {plan_req.days}-day trip to {plan_req.destination}. "
        f"Budget: ${plan_req.budget_usd} USD. "
        f"Style: {plan_req.travel_style.value}. "
        f"Group: {plan_req.group_type.value}. "
        f"Dietary: {plan_req.dietary or 'None'}. "
        f"Constraints: {plan_req.constraints or 'None'}."
    )

    total_t0 = time.perf_counter()

    try:
        logger.info("=== STEP 1/3: Agent loop started — Gemini Pro generates & validates itinerary ===")
        t0 = time.perf_counter()
        raw_itinerary = await run_agent(AGENT_SYSTEM_PROMPT, user_message)
        logger.info("✓ Step 1/3 done: Agent loop completed in %.1fs", time.perf_counter() - t0)

        enriched = await enrich_all_days_parallel(raw_itinerary)

        itinerary = Itinerary.model_validate(enriched)
        logger.info(
            "✓ Total request completed in %.1fs",
            time.perf_counter() - total_t0,
        )
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
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("10/minute")
async def replan_day(replan_req: ReplanRequest, request: Request) -> PlanResponse:
    """Replan a specific day within an existing itinerary.

    The agent receives the full current itinerary plus the user's reason
    for replanning and produces an updated itinerary.
    """
    logger.info(
        "POST /replan-day — day=%d, reason=%s",
        replan_req.day_number,
        replan_req.reason[:80],
    )

    if replan_req.day_number > replan_req.itinerary.total_days or replan_req.day_number < 1:
        raise HTTPException(
            status_code=400,
            detail=f"Day {replan_req.day_number} is out of range. "
                   f"Itinerary has {replan_req.itinerary.total_days} days.",
        )

    itinerary_dict = replan_req.itinerary.model_dump()

    user_message = (
        f"Here is the current itinerary:\n"
        f"{json.dumps(itinerary_dict, indent=2)}\n\n"
        f"Please replan Day {replan_req.day_number}.\n"
        f"Reason: {replan_req.reason}\n\n"
        f"Return the COMPLETE updated itinerary (all days) as JSON."
    )

    total_t0 = time.perf_counter()

    try:
        logger.info("=== STEP 1/3: Replan agent loop started ===")
        t0 = time.perf_counter()
        raw_itinerary = await run_agent(REPLAN_SYSTEM_PROMPT, user_message)
        logger.info("✓ Step 1/3 done: Replan agent loop completed in %.1fs", time.perf_counter() - t0)

        enriched = await enrich_all_days_parallel(raw_itinerary)

        itinerary = Itinerary.model_validate(enriched)
        logger.info(
            "✓ Total replan request completed in %.1fs",
            time.perf_counter() - total_t0,
        )
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
