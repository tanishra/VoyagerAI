from __future__ import annotations

import logging

from pydantic import Field
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

    GEMINI_API_KEY: str = Field(...)
    GOOGLE_GENAI_USE_VERTEXAI: bool = False

    TAVILY_API_KEY: str | None = None

    LANGSMITH_API_KEY: str | None = None
    LANGSMITH_PROJECT: str = "voyagerai"
    LANGCHAIN_TRACING_V2: bool = True

    AUTH_MODE: str = "development"
    API_AUTH_KEY: str | None = None

    CORS_ORIGINS: str = "http://localhost:3000"

    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL: int = 3600

    DATABASE_URL: str | None = None

    REQUEST_TIMEOUT: int = 300

    DAILY_TOKEN_LIMIT: int = 1_000_000

    CHECKPOINTER_BACKEND: str = "redis"  # "redis", "sqlite", or "memory"
    CHECKPOINTER_DB_PATH: str = "./data/checkpoints.sqlite"
    STORE_BACKEND: str = "redis"


settings = Settings()
