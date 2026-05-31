"""Agent loop — manual function-calling with Gemini."""

from __future__ import annotations

import inspect
import json
import logging
import textwrap

from fastapi import HTTPException
from google.genai import types

from config import (
    MODEL_ID,
    MAX_AGENT_ITERATIONS,
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


async def _execute_tool_call(function_call: types.FunctionCall) -> str:
    """Dispatch a single function call to the matching tool implementation."""
    name = function_call.name
    args = dict(function_call.args) if function_call.args else {}

    logger.info("Executing tool: %s with args keys: %s", name, list(args.keys()))

    handler = TOOL_DISPATCH.get(name)
    if handler is None:
        logger.warning("Unknown tool requested: %s", name)
        return json.dumps({"error": f"Unknown tool requested: {name}"})

    try:
        if inspect.iscoroutinefunction(handler):
            result = await handler(**args)
        else:
            result = handler(**args)
        return json.dumps(result, default=str)
    except Exception as exc:
        logger.error("Tool %s raised: %s", name, exc)
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


async def run_agent(system_prompt: str, user_message: str) -> dict:
    """Run the manual function-calling agent loop.

    Sends the user message to Gemini with tool declarations, then loops:
    * If the response contains function calls → execute them → send results back.
    * If the response is pure text → parse as JSON and return.
    * Safety limit: ``MAX_AGENT_ITERATIONS`` iterations.

    Raises:
        HTTPException: On Gemini errors, parse failures, or iteration exhaustion.
    """
    logger.info("Agent loop starting. User message length: %d chars", len(user_message))

    contents: list[types.Content] = [
        types.Content(role="user", parts=[types.Part.from_text(text=user_message)]),
    ]

    validation_failures = 0
    max_validation_retries = 3

    for iteration in range(1, MAX_AGENT_ITERATIONS + 1):
        logger.info("Agent iteration %d/%d", iteration, MAX_AGENT_ITERATIONS)

        temperature = (
            VALIDATION_REGEN_TEMPERATURE if validation_failures > 0 else AGENT_TEMPERATURE
        )

        try:
            response = client.models.generate_content(
                model=MODEL_ID,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    tools=[AGENT_TOOLS],
                    temperature=temperature,
                ),
            )
        except Exception as exc:
            logger.error("Gemini API call failed on iteration %d: %s", iteration, exc)
            raise HTTPException(status_code=502, detail=f"Gemini API error: {exc}") from exc

        if not response.candidates:
            logger.error("Gemini returned no candidates on iteration %d", iteration)
            raise HTTPException(status_code=502, detail="Gemini returned no response candidates.")

        candidate = response.candidates[0]
        parts = candidate.content.parts if candidate.content else []
        function_calls = [p.function_call for p in parts if p.function_call]

        if function_calls:
            contents.append(candidate.content)

            function_response_parts: list[types.Part] = []
            for fc in function_calls:
                result_json = await _execute_tool_call(fc)
                result_data = json.loads(result_json)

                if fc.name == "validate_constraints" and isinstance(result_data, dict):
                    if not result_data.get("valid", True):
                        validation_failures += 1
                        if validation_failures > max_validation_retries:
                            logger.warning(
                                "Validation failed %d times — proceeding with best effort.",
                                validation_failures,
                            )

                function_response_parts.append(
                    types.Part.from_function_response(
                        name=fc.name,
                        response=result_data,
                    )
                )

            contents.append(
                types.Content(role="user", parts=function_response_parts),
            )
            continue

        text_parts = [p.text for p in parts if p.text]
        final_text = "".join(text_parts).strip()

        if not final_text:
            logger.warning("Empty text response on iteration %d; continuing.", iteration)
            continue

        logger.info("Agent returned text (%d chars) on iteration %d", len(final_text), iteration)

        cleaned = _strip_markdown_fences(final_text)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse agent response as JSON: %s", exc)
            raise HTTPException(
                status_code=502,
                detail="Agent returned non-JSON response. Please try again.",
            ) from exc

    logger.error("Agent loop exhausted %d iterations.", MAX_AGENT_ITERATIONS)
    raise HTTPException(
        status_code=500,
        detail="Agent could not produce a result within the iteration limit.",
    )
