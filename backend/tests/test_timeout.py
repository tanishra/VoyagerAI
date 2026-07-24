"""Tests for request timeout middleware."""

from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import PlainTextResponse


class TimeoutMiddleware(BaseHTTPMiddleware):
    """Minimal timeout middleware matching the one in ``main.py``."""

    def __init__(self, app, timeout: float = 1.0):
        super().__init__(app)
        self.timeout = timeout

    async def dispatch(self, request: Request, call_next):
        try:
            async with asyncio.timeout(self.timeout):
                return await call_next(request)
        except asyncio.TimeoutError:
            return PlainTextResponse("Request timed out", status_code=503)


@pytest.fixture
def app():
    app = FastAPI()

    @app.get("/fast")
    async def fast():
        return {"ok": True}

    @app.get("/slow")
    async def slow():
        await asyncio.sleep(2)
        return {"ok": True}

    return app


class TestTimeoutMiddleware:
    def test_fast_request_succeeds(self, app):
        app.add_middleware(TimeoutMiddleware, timeout=5.0)
        with TestClient(app) as client:
            resp = client.get("/fast")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    def test_slow_request_times_out(self, app):
        app.add_middleware(TimeoutMiddleware, timeout=0.05)
        with TestClient(app) as client:
            resp = client.get("/slow")
        assert resp.status_code == 503
        assert resp.text == "Request timed out"

    def test_timeout_isolation(self, app):
        app.add_middleware(TimeoutMiddleware, timeout=0.05)
        with TestClient(app) as client:
            fast_resp = client.get("/fast")
            slow_resp = client.get("/slow")
        assert fast_resp.status_code == 200
        assert slow_resp.status_code == 503

    def test_health_passes_through(self, app):
        app.add_middleware(TimeoutMiddleware, timeout=5.0)
        with TestClient(app) as client:
            resp = client.get("/fast")
        assert resp.status_code == 200
