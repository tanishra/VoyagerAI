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
ENRICH_MODEL_ID: str = "gemini-2.5-flash"

MAX_AGENT_ITERATIONS: int = 5

# Lower temperature on regen to encourage strict budget adherence and
# minimal deviation from the feedback. The agent should correct issues,
# not introduce new creative variation.
VALIDATION_REGEN_TEMPERATURE: float = 0.2

# Higher temperature on initial creation for diverse activity choices,
# thematic day structure, and creative routing across destinations.
CREATION_TEMPERATURE: float = 0.7
# Moderate temperature for day enrichment — factual, practical tips
# without hallucinated recommendations.
ENRICH_TEMPERATURE: float = 0.6
# Moderate temperature for the agent loop's function-calling decisions.
# Balances deterministic tool selection with routing flexibility.
AGENT_TEMPERATURE: float = 0.4

CACHE_MAXSIZE: int = 32
VALIDATION_COST_TOLERANCE_FLAT: int = 50
VALIDATION_COST_TOLERANCE_PCT: float = 0.05
VALIDATION_UNDER_BUDGET_THRESHOLD: float = 0.5
MAX_VALIDATION_RETRIES: int = 3

# "development" — auth dependency is bypassed (safe for local dev)
# "production"  — X-API-Key header is required and validated
AUTH_MODE: str = os.getenv("AUTH_MODE", "development").lower()
API_AUTH_KEY: str | None = os.getenv("API_AUTH_KEY")

if AUTH_MODE == "production" and not API_AUTH_KEY:
    raise RuntimeError("API_AUTH_KEY must be set when AUTH_MODE=production")

REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHE_TTL_SECONDS: int = int(os.getenv("CACHE_TTL", "3600"))

REQUEST_TIMEOUT_SECONDS: int = int(os.getenv("REQUEST_TIMEOUT", "120"))

client = genai.Client(api_key=GEMINI_API_KEY)
