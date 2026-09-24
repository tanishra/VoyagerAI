from __future__ import annotations

import logging

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

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

    CHECKPOINTER_BACKEND: str = "postgres"  # "postgres", "redis", "sqlite", or "memory"
    CHECKPOINTER_DB_PATH: str = "./data/checkpoints.sqlite"
    STORE_BACKEND: str = "postgres"  # "postgres", "redis", or "memory"

    # Root dir for SQLite disaster-tier files. Empty = auto: explicit env value
    # wins, else /data when it exists and is writable (HF Spaces persistent
    # storage, k8s mounts), else ./data. Container redeploys wipe ./data —
    # mount a volume for durability when Postgres is not configured.
    DATA_DIR: str = ""

    # Postgres (Supabase) — durable tier for LangGraph state AND the fallback
    # tier of every app store. Empty string disables it entirely (stores then
    # use SQLite -> memory exactly as before). Use the session-mode/direct
    # connection string, NOT the transaction pooler (port 6543).
    DATABASE_URL: str = ""
    PG_POOL_MIN_SIZE: int = 1
    PG_POOL_MAX_SIZE: int = 10

    # SQLite fallback for all Redis-backed stores (threads, shares, sessions, etc.)
    # Used when Redis is unavailable — data persists across restarts.
    # Single-server only; multi-server production requires Redis.
    SQLITE_FALLBACK_DB_PATH: str = "./data/stores.sqlite"

    THREAD_TTL_DAYS: int = 30  # threads expire after N days of inactivity
    SHARE_TTL_DAYS: int = 7  # share links expire after N days

    # OAuth / session settings
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None
    OAUTH_REDIRECT_URI: str = "http://localhost:8000/auth/callback"
    SESSION_SECRET_KEY: str = "dev-only-insecure-key-change-in-production"

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

    # Image generation (Gemini 2.5 Flash Image)
    ENABLE_IMAGE_GENERATION: bool = True
    IMAGE_GENERATION_MODEL: str = "gemini-2.5-flash-image"
    MAX_IMAGES_PER_THREAD: int = 3
    IMAGE_GENERATION_COST_USD: float = 0.03

    # Prompt injection defense (Phase 6.30)
    ENABLE_INJECTION_GUARD: bool = True
    INJECTION_GUARD_MODEL: str = "gemini/gemini-2.5-flash-lite"
    INJECTION_STRIKE_THRESHOLD: int = 5
    INJECTION_STRIKE_WINDOW_MINUTES: int = 60
    INJECTION_COOLDOWN_MINUTES: int = 15

    # Per-user rate limiting (Phase 7.2)
    RATE_LIMIT_CHAT_PER_MIN: int = 10
    RATE_LIMIT_THREADS_PER_MIN: int = 30
    RATE_LIMIT_UPLOADS_PER_MIN: int = 5

    # Per-user daily cost cap (Phase 7.2)
    DAILY_COST_CAP_USD: float = 5.0

    # Global circuit breaker (Phase 7.2)
    HOURLY_PLATFORM_CAP_USD: float = 50.0
    CIRCUIT_BREAKER_ENABLED: bool = True

    # Observability (Phase 7.4)
    LOG_FORMAT: str = "json"  # "json" or "text"
    LOG_LEVEL: str = "INFO"
    PROMETHEUS_ENABLED: bool = True
    ALERT_DAILY_THRESHOLD_PCT: float = 0.8  # alert at 80% of daily cap

    @model_validator(mode="after")
    def _resolve_data_dir(self) -> "Settings":
        """Point default ./data paths at DATA_DIR when set, or at a writable
        /data mount (HF Spaces persistent storage) when not. Explicit
        CHECKPOINTER_DB_PATH/SQLITE_FALLBACK_DB_PATH env values win."""
        import os

        data_dir = self.DATA_DIR
        if not data_dir and os.path.isdir("/data") and os.access("/data", os.W_OK):
            data_dir = "/data"
        if not data_dir:
            return self
        for field, default_name in (
            ("CHECKPOINTER_DB_PATH", "checkpoints.sqlite"),
            ("SQLITE_FALLBACK_DB_PATH", "stores.sqlite"),
        ):
            if getattr(self, field) == f"./data/{default_name}":
                setattr(self, field, os.path.join(data_dir, default_name))
        return self


settings = Settings()

# Configure structured logging based on settings
from logging_config import configure_logging  # noqa: E402

configure_logging(fmt=settings.LOG_FORMAT, level=settings.LOG_LEVEL)
