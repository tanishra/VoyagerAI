"""API key authentication with environment-aware mode.

AUTH_MODE controls whether authentication is enforced:
  - "development" — auth dependency is a no-op (safe for local dev)
  - "production"  — X-API-Key header is required and validated against API_AUTH_KEY
"""

from __future__ import annotations

from fastapi import Header, HTTPException, status

from config import AUTH_MODE, API_AUTH_KEY, logger


async def verify_api_key(
    x_api_key: str | None = Header(default=None),
) -> str:
    """Verify the X-API-Key header or bypass in development mode."""
    if AUTH_MODE == "development":
        return "dev"

    if not API_AUTH_KEY:
        logger.critical("API_AUTH_KEY is not configured in production mode")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server authentication is misconfigured",
        )

    if not x_api_key or x_api_key != API_AUTH_KEY:
        logger.warning("Unauthorized request received")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return x_api_key
