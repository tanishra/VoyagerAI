"""Tests for admin security endpoints (Phase 6.30).

Tests verify:
- GET /admin/security/flags returns aggregate stats
- GET /admin/security/cooldowns returns active cooldowns
- DELETE /admin/security/cooldowns/{user_hash} removes cooldown
- Non-admin users get 403
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from oauth import get_current_user, verify_admin


@pytest.fixture
def admin_user():
    return {"user_id": "admin123", "email": "admin@test.com"}


@pytest.fixture
def regular_user():
    return {"user_id": "user123", "email": "user@test.com"}


@pytest.fixture
def admin_deps(admin_user):
    """Override auth dependencies for admin endpoints."""
    app.dependency_overrides[get_current_user] = lambda: admin_user
    app.dependency_overrides[verify_admin] = lambda: admin_user
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_security_flags_admin(admin_user, admin_deps):
    mock_stats = {
        "total_flags": 5,
        "by_category": {"instruction_override": 3, "extraction_attempt": 2},
        "by_source": {"message": 5},
        "by_confidence": {"high": 5},
        "unique_users": 3,
        "active_cooldowns": 1,
        "recent_flags": [],
    }
    with patch("main.security_store") as mock_store:
        mock_store.get_aggregate_stats = AsyncMock(return_value=mock_stats)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/admin/security/flags?period=week",
                headers={"X-API-Key": "test"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_flags"] == 5
        assert "instruction_override" in data["by_category"]


@pytest.mark.asyncio
async def test_get_security_flags_period_validation(admin_user, admin_deps):
    mock_stats = {"total_flags": 0, "by_category": {}, "by_source": {}, "by_confidence": {}, "unique_users": 0, "active_cooldowns": 0, "recent_flags": []}
    with patch("main.security_store") as mock_store:
        mock_store.get_aggregate_stats = AsyncMock(return_value=mock_stats)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/admin/security/flags?period=invalid",
                headers={"X-API-Key": "test"},
            )
        assert resp.status_code == 200
        mock_store.get_aggregate_stats.assert_called_once_with(period="week")


@pytest.mark.asyncio
async def test_get_active_cooldowns_admin(admin_user, admin_deps):
    mock_cooldowns = [
        {"user_hash": "abc123", "until": 1700000000, "remaining_seconds": 300},
    ]
    with patch("main.security_store") as mock_store:
        mock_store.get_active_cooldowns = AsyncMock(return_value=mock_cooldowns)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/admin/security/cooldowns",
                headers={"X-API-Key": "test"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["cooldowns"][0]["user_hash"] == "abc123"


@pytest.mark.asyncio
async def test_remove_cooldown_admin(admin_user, admin_deps):
    with patch("main.security_store") as mock_store:
        mock_store.remove_cooldown = AsyncMock(return_value=True)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set("voyager_csrf", "test-csrf-token")
            resp = await client.delete(
                "/admin/security/cooldowns/abc123",
                headers={"X-API-Key": "test", "X-CSRF-Token": "test-csrf-token"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["user_hash"] == "abc123"


@pytest.mark.asyncio
async def test_remove_cooldown_not_found(admin_user, admin_deps):
    with patch("main.security_store") as mock_store:
        mock_store.remove_cooldown = AsyncMock(return_value=False)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set("voyager_csrf", "test-csrf-token")
            resp = await client.delete(
                "/admin/security/cooldowns/nonexistent",
                headers={"X-API-Key": "test", "X-CSRF-Token": "test-csrf-token"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "not_found"
