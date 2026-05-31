"""Agent loop — manual function-calling with Gemini."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import textwrap
import time

from fastapi import HTTPException
from google.genai import types

from config import (
    MODEL_ID,
    MAX_AGENT_ITERATIONS,
    MAX_VALIDATION_RETRIES,
    AGENT_TEMPERATURE,
    VALIDATION_REGEN_TEMPERATURE,
    client,
)
from tools import TOOL_DISPATCH, AGENT_TOOLS

logger = logging.getLogger("travel_agent.agent")


AGENT_SYSTEM_PROMPT = textwrap.dedent("""\
    You are a meticulous Travel Planning Agent. Your job is to create high-quality,
    validated travel itineraries.

    **Workflow — follow this order strictly:**
    1. Call `generate_itinerary` with the user's parameters to produce the initial plan.
    2. Call `validate_constraints` with the generated itinerary and budget to verify
       budget compliance and internal consistency.
    3. If validation shows any issues, adjust the itinerary mentally and call
       `generate_itinerary` again with tighter budget guidance, then re-validate.
       Repeat until valid (max 3 attempts).
    4. Once the itinerary is valid, return the itinerary JSON as plain text
       immediately. Do NOT call enrich_day — enrichment happens in a separate
       parallel step outside this loop.
    5. Your final response must be ONLY the valid JSON itinerary object — nothing else.

    **Rules:**
    - Always call generate_itinerary FIRST.
    - Always call validate_constraints AFTER generating.
    - Do NOT call enrich_day — it is handled externally.
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
    5. Once valid, return the COMPLETE updated itinerary (all days, not just the
       changed day) as plain JSON text immediately. Do NOT call enrich_day —
       enrichment happens in a separate parallel step.

    **Rules:**
    - Keep all other days unchanged unless the budget rebalance requires it.
    - Do NOT call enrich_day — it is handled externally.
    - Your final text response must be ONLY the valid JSON itinerary object.
""")


async def _execute_tool_call(function_call: types.FunctionCall) -> str:
    """Dispatch a single function call to the matching tool implementation."""
    name = function_call.name
    args = dict(function_call.args) if function_call.args else {}

    handler = TOOL_DISPATCH.get(name)
    if handler is None:
        logger.warning("Unknown tool requested: %s", name)
        return json.dumps({"error": f"Unknown tool requested: {name}"})

    t0 = time.perf_counter()
    tool_desc = {
        "generate_itinerary": "Generating full itinerary (this is the slowest step, ~40-60s)...",
        "validate_constraints": "Validating budget & cost consistency...",
    }.get(name, f"Running {name}...")

    logger.info("  → Tool: %s — %s", name, tool_desc)

    try:
        if inspect.iscoroutinefunction(handler):
            result = await handler(**args)
        else:
            result = handler(**args)
        elapsed = time.perf_counter() - t0
        logger.info("  ← Tool: %s completed in %.1fs", name, elapsed)
        return json.dumps(result, default=str)
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        logger.error("  ✗ Tool: %s failed after %.1fs: %s", name, elapsed, exc)
        return json.dumps({"error": str(exc)})


def _strip_markdown_fences(text: str) -> str:
    """Remove markdown code fences from model output."""
    cleaned = text
    if cleaned.startswith("```"):
        first_newline = cleaned.index("\n") if "\n" in cleaned else len(cleaned)
        cleaned = cleaned[first_newline + 1:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()


async def _execute_function_calls(
    function_calls: list[types.FunctionCall],
    candidate_content: types.Content,
    contents: list[types.Content],
    validation_failures: int,
) -> tuple[list[types.Content], int]:
    """Execute function calls and append responses to contents."""
    contents.append(candidate_content)

    function_response_parts: list[types.Part] = []
    for fc_call in function_calls:

        result_json = await _execute_tool_call(fc_call)
        result_data = json.loads(result_json)

        if fc_call.name == "validate_constraints" and isinstance(result_data, dict):
            if not result_data.get("valid", True):
                validation_failures += 1
                if validation_failures > MAX_VALIDATION_RETRIES:
                    logger.warning(
                        "Validation failed %d times — proceeding with best effort.",
                        validation_failures,
                    )

        function_response_parts.append(
            types.Part.from_function_response(
                name=fc_call.name,
                response=result_data,
            )
        )

    contents.append(
        types.Content(role="user", parts=function_response_parts),
    )
    return contents, validation_failures


TIMEOUT_AGENT: int = 30


async def _make_gemini_call(
    contents: list[types.Content],
    system_prompt: str,
    temperature: float,
) -> types.GenerateContentResponse:
    """Make a single Gemini API call with the given contents and config."""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(
                lambda: client.models.generate_content(
                    model=MODEL_ID,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        tools=[AGENT_TOOLS],
                        temperature=temperature,
                    ),
                )
            ),
            timeout=TIMEOUT_AGENT,
        )
    except Exception as exc:
        logger.error("Gemini API call failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Gemini API error: {exc}") from exc


def _parse_text_response(parts: list[types.Part]) -> dict | None:
    """Extract and parse JSON from text parts of a response. Returns None if no text."""
    text_parts = [p.text for p in parts if p.text]
    final_text = "".join(text_parts).strip()

    if not final_text:
        return None

    cleaned = _strip_markdown_fences(final_text)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse agent response as JSON: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="Agent returned non-JSON response. Please try again.",
        ) from exc


async def run_agent(system_prompt: str, user_message: str) -> dict:
    """Run the manual function-calling agent loop.

    Sends the user message to Gemini with tool declarations, then loops:
    * If the response contains function calls → execute them → send results back.
    * If the response is pure text → parse as JSON and return.
    * Safety limit: ``MAX_AGENT_ITERATIONS`` iterations.

    Raises:
        HTTPException: On Gemini errors, parse failures, or iteration exhaustion.
    """
    t_loop_start = time.perf_counter()
    logger.info("Agent loop starting. User message length: %d chars", len(user_message))

    contents: list[types.Content] = [
        types.Content(role="user", parts=[types.Part.from_text(text=user_message)]),
    ]

    validation_failures = 0

    for iteration in range(1, MAX_AGENT_ITERATIONS + 1):
        logger.info("Agent iteration %d/%d — asking Gemini Pro to respond...", iteration, MAX_AGENT_ITERATIONS)

        temperature = (
            VALIDATION_REGEN_TEMPERATURE if validation_failures > 0 else AGENT_TEMPERATURE
        )

        t0 = time.perf_counter()
        response = await _make_gemini_call(contents, system_prompt, temperature)
        gemini_elapsed = time.perf_counter() - t0

        if not response.candidates:
            logger.error("Gemini returned no candidates on iteration %d", iteration)
            raise HTTPException(status_code=502, detail="Gemini returned no response candidates.")

        candidate = response.candidates[0]
        parts = candidate.content.parts if candidate.content else []
        function_calls = [p.function_call for p in parts if p.function_call]

        if function_calls:
            tool_names = [fc.name for fc in function_calls]
            logger.info(
                "  Gemini responded in %.1fs → calling tool(s): %s",
                gemini_elapsed, tool_names,
            )
            contents, validation_failures = await _execute_function_calls(
                function_calls, candidate.content, contents, validation_failures
            )
            continue

        parsed = _parse_text_response(parts)
        if parsed is not None:
            logger.info(
                "  Gemini responded in %.1fs → returning final itinerary JSON ✓",
                gemini_elapsed,
            )
            logger.info(
                "Agent loop completed in %d iterations (%.1fs total)",
                iteration, time.perf_counter() - t_loop_start,
            )
            return parsed

        logger.warning("Empty text response on iteration %d; continuing.", iteration)

    logger.error("Agent loop exhausted %d iterations.", MAX_AGENT_ITERATIONS)
    raise HTTPException(
        status_code=500,
        detail="Agent could not produce a result within the iteration limit.",
    )
