from __future__ import annotations

import asyncio
import json
import os

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sse_starlette.sse import EventSourceResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import PlainTextResponse

from auth import verify_api_key
from cache import cache_client
from config import settings, logger, REQUEST_TIMEOUT_SECONDS
from sanitize import sanitize_prompt_input
from models import Itinerary, PlanRequest, PlanResponse, ReplanRequest
from agents import run_travel_agent, stream_travel_agent

ALLOWED_ORIGINS: list[str] = [
    orig.strip()
    for orig in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if orig.strip()
]

if settings.AUTH_MODE == "production" and not ALLOWED_ORIGINS:
    raise RuntimeError(
        "CORS_ORIGINS must be set to an explicit allowlist when AUTH_MODE=production"
    )

app = FastAPI(
    title="Travel Planning AI Agent",
    version="2.1.0",
    description="Generates, validates, and enriches multi-day travel itineraries using DeepAgent.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TimeoutMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT_SECONDS):
                return await call_next(request)
        except asyncio.TimeoutError:
            return PlainTextResponse("Request timed out", status_code=503)


app.add_middleware(TimeoutMiddleware)

limiter = Limiter(key_func=get_remote_address, default_limits=["30/hour"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.get("/health", summary="Health check", tags=["ops"])
async def health() -> dict[str, str]:
    redis_ok = await cache_client.ping()
    return {
        "status": "ok" if redis_ok else "degraded",
        "redis": "connected" if redis_ok else "unavailable",
        "agent": "deepagent",
    }


@app.post(
    "/plan",
    response_model=PlanResponse,
    summary="Generate travel plan",
    tags=["planning"],
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("5/minute")
async def plan(plan_req: PlanRequest, request: Request) -> PlanResponse:
    logger.info(
        "POST /plan — destination=%s, days=%d, budget=%d, style=%s, group=%s",
        plan_req.destination,
        plan_req.days,
        plan_req.budget_usd,
        plan_req.travel_style.value,
        plan_req.group_type.value,
    )

    cached = await cache_client.get(plan_req)
    if cached is not None:
        logger.info("Cache HIT for %s", plan_req.destination)
        itinerary = Itinerary.model_validate(cached)
        return PlanResponse(success=True, itinerary=itinerary)

    _dest_safe = sanitize_prompt_input(plan_req.destination, "destination")
    _diet_safe = sanitize_prompt_input(plan_req.dietary, "dietary")
    _constr_safe = sanitize_prompt_input(plan_req.constraints, "constraints")

    user_message = (
        f"Plan a {plan_req.days}-day trip to {_dest_safe}. "
        f"Budget: ${plan_req.budget_usd} USD. "
        f"Style: {plan_req.travel_style.value}. "
        f"Group: {plan_req.group_type.value}. "
        f"Dietary: {_diet_safe or 'None'}. "
        f"Constraints: {_constr_safe or 'None'}."
    )

    try:
        thread_id = f"plan:{plan_req.destination}:{plan_req.days}:{plan_req.budget_usd}"

        raw_itinerary = await run_travel_agent(
            user_message=user_message,
            thread_id=thread_id,
        )

        itinerary = Itinerary.model_validate(raw_itinerary)
        await cache_client.set(plan_req, itinerary.model_dump())

        return PlanResponse(success=True, itinerary=itinerary)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Unexpected error in /plan: %s", exc)
        return PlanResponse(success=False, error=f"Planning failed: {exc}")


@app.post(
    "/plan/stream",
    summary="Stream travel plan generation",
    tags=["planning"],
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("5/minute")
async def plan_stream(plan_req: PlanRequest, request: Request) -> EventSourceResponse:
    _dest_safe = sanitize_prompt_input(plan_req.destination, "destination")
    _diet_safe = sanitize_prompt_input(plan_req.dietary, "dietary")
    _constr_safe = sanitize_prompt_input(plan_req.constraints, "constraints")

    user_message = (
        f"Plan a {plan_req.days}-day trip to {_dest_safe}. "
        f"Budget: ${plan_req.budget_usd} USD. "
        f"Style: {plan_req.travel_style.value}. "
        f"Group: {plan_req.group_type.value}. "
        f"Dietary: {_diet_safe or 'None'}. "
        f"Constraints: {_constr_safe or 'None'}."
    )

    thread_id = f"plan:{plan_req.destination}:{plan_req.days}:{plan_req.budget_usd}"

    async def event_generator():
        async for event in stream_travel_agent(
            user_message=user_message,
            thread_id=thread_id,
        ):
            yield {
                "event": event.get("event", "data"),
                "data": json.dumps(event),
            }

    return EventSourceResponse(event_generator())


@app.post(
    "/replan-day",
    response_model=PlanResponse,
    summary="Replan a specific day",
    tags=["planning"],
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("10/minute")
async def replan_day(replan_req: ReplanRequest, request: Request) -> PlanResponse:
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
    _reason_safe = sanitize_prompt_input(replan_req.reason, "reason")

    user_message = (
        f"Here is the current itinerary:\n"
        f"{json.dumps(itinerary_dict, indent=2)}\n\n"
        f"Please replan Day {replan_req.day_number}.\n"
        f"Reason: {_reason_safe}\n\n"
        f"Return the COMPLETE updated itinerary (all days) as JSON."
    )

    try:
        thread_id = f"replan:{replan_req.day_number}:{hash(json.dumps(itinerary_dict, sort_keys=True))}"

        raw_itinerary = await run_travel_agent(
            user_message=user_message,
            thread_id=thread_id,
        )

        itinerary = Itinerary.model_validate(raw_itinerary)
        return PlanResponse(success=True, itinerary=itinerary)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Unexpected error in /replan-day: %s", exc)
        return PlanResponse(success=False, error=f"Replanning failed: {exc}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
