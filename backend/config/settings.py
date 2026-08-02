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
    LLM_ORCHESTRATOR_MODEL: str = "gemini/gemini-2.5-pro"
    LLM_ORCHESTRATOR_FALLBACK: str | None = None
    LLM_SUBAGENT_MODEL: str = "gemini/gemini-3.5-flash"
    LLM_SUBAGENT_FALLBACK: str | None = None
    LLM_TEMPERATURE_ORCHESTRATOR: float = 0.2
    LLM_TEMPERATURE_SUBAGENT: float = 0.3

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


settings = Settings()
