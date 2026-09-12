"""Visual generation tools — Gemini 2.5 Flash Image + recharts chart data.

Provides two tools for the orchestrator:
- generate_travel_image: AI-generated destination photos via Gemini
- generate_chart: structured chart data (bar/pie) for frontend recharts rendering

Image generation is capped per-thread (default 3) and uses a pending-visuals
dict so the full base64 image data never enters the LLM context window —
only a short reference string is returned to the model.
"""

from __future__ import annotations

import base64
import contextvars
import json
import logging
import uuid
from typing import Literal

from langchain_core.tools import tool

from config.settings import settings

logger = logging.getLogger("travel_agent.tools.visuals")

# Context variable for current thread_id (set by stream_chat_agent etc.)
_current_thread_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "visuals_thread_id", default=""
)

# Per-thread image generation count (persists across turns within a thread)
_image_counts: dict[str, int] = {}

# Pending visual results keyed by visual_id — retrieved by the event handler
# to emit full SSE payloads without sending base64 through the LLM context.
_pending_visuals: dict[str, dict] = {}

_VISUAL_TOOL_NAMES = frozenset({"generate_travel_image", "generate_chart"})


def set_current_thread_id(thread_id: str) -> None:
    """Set the current thread_id for per-thread image cap tracking."""
    _current_thread_id.set(thread_id)


def get_pending_visual(visual_id: str) -> dict | None:
    """Retrieve and remove a pending visual result by its ID."""
    return _pending_visuals.pop(visual_id, None)


def is_visual_tool(name: str) -> bool:
    """Check if a tool name is a visual generation tool."""
    return name in _VISUAL_TOOL_NAMES


@tool
async def generate_travel_image(
    prompt: str,
    alt_text: str = "",
) -> str:
    """Generate a travel destination image using Gemini 2.5 Flash Image.

    Use this tool ONLY when the user explicitly asks to see, visualize, or
    generate an image of a destination, landmark, or travel scene.

    Examples of when to use:
    - "Show me what Kyoto looks like"
    - "Generate a picture of the Eiffel Tower"
    - "Can you create an image of a Bali beach?"

    Do NOT use this tool proactively — only on explicit user request.
    Maximum 3 images per conversation thread.

    Args:
        prompt: Descriptive prompt for the image (e.g. "A scenic view of Kyoto's Fushimi Inari shrine with thousands of vermilion torii gates at sunset")
        alt_text: Short alt-text description for accessibility (e.g. "Fushimi Inari shrine, Kyoto")

    Returns:
        Short JSON string confirming image generation. The actual image data
        is delivered to the frontend via a separate SSE event.
    """
    if not settings.ENABLE_IMAGE_GENERATION:
        return "Image generation is disabled."

    if not prompt or not prompt.strip():
        return "Image prompt must not be empty."

    thread_id = _current_thread_id.get("")
    count = _image_counts.get(thread_id, 0)

    if count >= settings.MAX_IMAGES_PER_THREAD:
        return (
            f"Image generation limit reached ({settings.MAX_IMAGES_PER_THREAD} per conversation). "
            "Please let the user know they've used all their image generations for this thread."
        )

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.GEMINI_API_KEY)

        response = client.models.generate_content(
            model=settings.IMAGE_GENERATION_MODEL,
            contents=prompt.strip(),
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
            ),
        )

        image_bytes = None
        for candidate in response.candidates:
            if candidate.content is None:
                continue
            for part in candidate.content.parts:
                if part.inline_data is not None and part.inline_data.data:
                    image_bytes = part.inline_data.data
                    break
            if image_bytes:
                break

        if image_bytes is None:
            logger.warning("Gemini image generation returned no image data for prompt: %s", prompt[:100])
            return "Image generation failed: no image data returned. Please try a different prompt."

        b64_data = base64.b64encode(image_bytes).decode("ascii")
        data_url = f"data:image/png;base64,{b64_data}"

        visual_id = str(uuid.uuid4())
        _pending_visuals[visual_id] = {
            "type": "image",
            "data_url": data_url,
            "alt": alt_text or prompt[:100],
            "prompt": prompt.strip(),
        }

        _image_counts[thread_id] = count + 1

        result = json.dumps({
            "_visual_id": visual_id,
            "type": "image",
            "alt": alt_text or prompt[:100],
            "remaining": settings.MAX_IMAGES_PER_THREAD - (count + 1),
        })
        return result

    except Exception as exc:
        logger.warning("Image generation failed: %s", exc, exc_info=True)
        return f"Image generation failed: {exc}. Please try again with a simpler prompt."


@tool
def generate_chart(
    chart_type: Literal["bar", "pie"],
    title: str,
    labels: list[str],
    series: dict[str, list[float]],
) -> str:
    """Generate a chart visualization for cost or data breakdowns.

    Use this tool when the user asks to visualize, chart, or graph data
    from their itinerary — especially cost breakdowns.

    Examples of when to use:
    - "Show me my budget as a chart"
    - "Break down my costs visually"
    - "Chart my daily spending"

    Args:
        chart_type: "bar" for comparing values across categories, "pie" for showing proportions of a whole
        title: Chart title (e.g. "Cost Breakdown by Category" or "Daily Spending")
        labels: Category labels for each data point (e.g. ["Flights", "Hotels", "Food", "Activities"])
        series: Named data series mapping to values. For single-series charts, use one key.
                Example: {"Cost (USD)": [450, 800, 300, 250]} — values must align with labels by index.

    Returns:
        JSON string with chart data in recharts-friendly format. The frontend
        renders this as an inline chart card.
    """
    if chart_type not in ("bar", "pie"):
        return "Invalid chart_type. Must be 'bar' or 'pie'."

    if not labels or not series:
        return "Chart data must include labels and at least one series."

    for series_name, values in series.items():
        if len(values) != len(labels):
            return (
                f"Series '{series_name}' has {len(values)} values but there are "
                f"{len(labels)} labels. They must match."
            )

    data = []
    for i, label in enumerate(labels):
        point: dict[str, str | float] = {"label": label}
        for series_name, values in series.items():
            point[series_name] = values[i]
        data.append(point)

    result = {
        "type": "chart",
        "chart_type": chart_type,
        "title": title,
        "data": data,
        "series_keys": list(series.keys()),
    }

    return json.dumps(result)


def get_visual_tools() -> list:
    """Return visual generation tools available to the orchestrator."""
    tools = [generate_chart]
    if settings.ENABLE_IMAGE_GENERATION:
        tools.append(generate_travel_image)
    return tools


async def generate_destination_image(destination: str) -> str | None:
    """Generate a destination image for share cards.

    Returns base64-encoded PNG string, or None if generation fails or is disabled.
    """
    if not settings.ENABLE_IMAGE_GENERATION:
        return None

    if not settings.GEMINI_API_KEY:
        logger.warning("Cannot generate destination image: GEMINI_API_KEY not set")
        return None

    prompt = (
        f"A beautiful, editorial travel photograph of {destination}. "
        "Magazine quality, warm tones, no text overlay, no people in foreground. "
        "Landscape orientation, cinematic lighting."
    )

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.GEMINI_API_KEY)

        response = client.models.generate_content(
            model=settings.IMAGE_GENERATION_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
            ),
        )

        image_bytes = None
        for candidate in response.candidates:
            if candidate.content is None:
                continue
            for part in candidate.content.parts:
                if part.inline_data is not None and part.inline_data.data:
                    image_bytes = part.inline_data.data
                    break
            if image_bytes:
                break

        if image_bytes is None:
            logger.warning("Destination image generation returned no data for: %s", destination)
            return None

        return base64.b64encode(image_bytes).decode("ascii")

    except Exception as exc:
        logger.warning("Destination image generation failed: %s", exc, exc_info=True)
        return None
