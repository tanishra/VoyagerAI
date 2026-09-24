"""API key authentication with environment-aware mode.

AUTH_MODE controls whether authentication is enforced:
  - "development" — auth dependency is a no-op (safe for local dev)
  - "production"  — X-API-Key header is required and validated against API_AUTH_KEY
"""

from __future__ import annotations

import hmac

from fastapi import Header, HTTPException, Request, status

from config import API_AUTH_KEY, AUTH_MODE, logger


async def verify_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None),
) -> str:
    """Verify the X-API-Key header, or the api_key query param, or bypass in dev mode.

    The query param fallback avoids triggering a CORS preflight (custom headers
    force a preflight OPTIONS request, which some hosting proxies mishandle).
    """
    if AUTH_MODE == "development":
        return "dev"

    if not API_AUTH_KEY:
        logger.critical("API_AUTH_KEY is not configured in production mode")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server authentication is misconfigured",
        )

    if x_api_key is None:
        # Query-param fallback exists because custom headers force a CORS
        # preflight that some hosting proxies mishandle. Query strings land in
        # access logs/proxies, so prefer the header and flag the fallback.
        x_api_key = request.query_params.get("api_key")
        if x_api_key:
            logger.warning(
                "api_key query-param auth used from %s — prefer X-API-Key header",
                request.client.host if request.client else "unknown",
            )
    if not x_api_key or not hmac.compare_digest(x_api_key, API_AUTH_KEY):
        logger.warning("Unauthorized request received")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return x_api_key
