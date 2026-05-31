"""Configuration, client, and constants."""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from google import genai

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

MAX_AGENT_ITERATIONS: int = 5

VALIDATION_REGEN_TEMPERATURE: float = 0.2

CREATION_TEMPERATURE: float = 0.7
ENRICH_TEMPERATURE: float = 0.6
AGENT_TEMPERATURE: float = 0.4

client = genai.Client(api_key=GEMINI_API_KEY)
