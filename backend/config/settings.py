from __future__ import annotations

import logging

from pydantic_settings import BaseSettings, SettingsConfigDict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("travel_agent")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    GEMINI_API_KEY: str | None = None
    GOOGLE_GENAI_USE_VERTEXAI: bool = False

    TAVILY_API_KEY: str | None = None

    # LLM provider config — LiteLLM model strings
    # Format: "provider/model-name" (e.g. "gemini/gemini-2.5-pro", "openai/gpt-4o")
    LLM_ORCHESTRATOR_MODEL: str = "gemini/gemini-3.7-flash"
    LLM_ORCHESTRATOR_FALLBACK: str | None = None
    LLM_SUBAGENT_MODEL: str = "gemini/gemini-3.5-flash-lite"
    LLM_SUBAGENT_FALLBACK: str | None = None
    LLM_TEMPERATURE_ORCHESTRATOR: float = 1.0
    LLM_TEMPERATURE_SUBAGENT: float = 1.0

    LANGSMITH_API_KEY: str | None = None
    LANGSMITH_PROJECT: str = "voyagerai"
    LANGCHAIN_TRACING_V2: bool = True

    AUTH_MODE: str = "development"
    API_AUTH_KEY: str | None = None

    CORS_ORIGINS: str = "http://localhost:3000"

    REDIS_URL: str = "redis://localhost:6379/0"
    REQUEST_TIMEOUT_SECONDS: int = 300

    CHECKPOINTER_BACKEND: str = "redis"  # "redis", "sqlite", or "memory"
    CHECKPOINTER_DB_PATH: str = "./data/checkpoints.sqlite"
    STORE_BACKEND: str = "redis"

    THREAD_TTL_DAYS: int = 30  # threads expire after N days of inactivity
    SHARE_TTL_DAYS: int = 7  # share links expire after N days

    # OAuth / session settings
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None
    OAUTH_REDIRECT_URI: str = "http://localhost:8000/auth/callback"
    SESSION_SECRET_KEY: str = "dev-only-insecure-key-change-in-production"
    AUTH_DEV_BYPASS: bool = False

    # Cost tracking
    SESSION_BUDGET_LIMIT_USD: float = 0.50
    BUDGET_WARNING_THRESHOLD: float = 0.80
    ADMIN_EMAILS: str = ""  # comma-separated admin emails

    # Model routing tiers
    MODEL_TIER_CHEAP: str = "gemini/gemini-3.5-flash-lite"
    MODEL_TIER_STANDARD: str = "gemini/gemini-3.7-flash"
    MODEL_TIER_PREMIUM: str = "gemini/gemini-2.5-pro"

    # Subagent model overrides (JSON string: {"researcher": "gemini/gemini-2.5-pro", ...})
    SUBAGENT_MODEL_OVERRIDES: str = ""

    # Research result caching
    RESEARCH_CACHE_TTL_HOURS: int = 24
    RESEARCH_CACHE_ENABLED: bool = True


settings = Settings()
