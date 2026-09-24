"""Tests for single-tier comparison regeneration (U6).

Covers the pipeline helper (regenerate_tier_plan) and the
POST /chat/regenerate-tier endpoint.
"""

from __future__ import annotations

import asyncio
import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from agents.constraints import TripConstraints


def _constraints() -> TripConstraints:
    return TripConstraints(
        destination="Delhi, India",
        total_days=5,
        budget_amount=50000,
        budget_currency="INR",
        travel_style="balanced",
        group_type="friends",
    )


def _plan(tier: str, total: float) -> dict:
    return {
        "tier": tier,
        "itinerary": {
            "destination": "Delhi, India",
            "total_days": 5,
            "currency": "INR",
            "estimated_total_cost_usd": total,
            "budget_status": "within",
        },
        "cost_breakdown": {
            "accommodation": total * 0.4,
            "food": total * 0.25,
            "activities": total * 0.2,
            "transport": total * 0.15,
            "total": total,
        },
        "highlights": [f"{tier} highlight"],
        "tradeoffs": [f"{tier} tradeoff"],
    }


def _comparison() -> dict:
    return {
        "plans": [_plan("budget", 30000), _plan("balanced", 48000), _plan("premium", 75000)],
        "comparison_matrix": {
            "total_cost": {"budget": 30000, "balanced": 48000, "premium": 75000},
            "accommodation_type": {"budget": "hostel", "balanced": "3-star", "premium": "5-star"},
        },
    }


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestRegenerateTierPlan:
    """pipeline.regenerate_tier_plan — single-call regen with enforcement."""

    def test_patches_only_target_tier_and_syncs_matrix(self, monkeypatch):
        from agents import pipeline

        new_plan = _plan("premium", 72000)
        new_plan["highlights"] = ["fresh premium option"]

        async def fake_gen(model, prompt, task, stage):
            # Rejected plan + siblings must reach the prompt for differentiation
            assert "rejected_plan" in task
            assert "sibling_plans" in task
            assert "75000" in task  # rejected premium total
            return new_plan, {"input_tokens": 10, "output_tokens": 20}

        monkeypatch.setattr(pipeline, "_generate_structured", fake_gen)
        monkeypatch.setattr(pipeline, "validate_comparison", lambda c, k: [])

        original = _comparison()
        result = _run(
            pipeline.regenerate_tier_plan(_constraints(), "premium", original)
        )

        assert result is not None
        tiers = [p["tier"] for p in result["plans"]]
        assert tiers == ["budget", "balanced", "premium"]  # order preserved
        assert result["plans"][0]["itinerary"]["estimated_total_cost_usd"] == 30000
        assert result["plans"][1]["itinerary"]["estimated_total_cost_usd"] == 48000
        assert result["plans"][2]["highlights"] == ["fresh premium option"]
        # Matrix synced by _reconcile_comparison_budgets
        assert result["comparison_matrix"]["total_cost"]["premium"] == 72000
        # Original dict untouched (deep copy)
        assert original["plans"][2]["itinerary"]["estimated_total_cost_usd"] == 75000

    def test_enforces_constraints_on_model_output(self, monkeypatch):
        from agents import pipeline

        bad_plan = _plan("budget", 31000)
        bad_plan["itinerary"]["currency"] = "USD"
        bad_plan["itinerary"]["total_days"] = 3
        bad_plan["itinerary"]["destination"] = "Paris"

        async def fake_gen(model, prompt, task, stage):
            return bad_plan, {}

        monkeypatch.setattr(pipeline, "_generate_structured", fake_gen)
        monkeypatch.setattr(pipeline, "validate_comparison", lambda c, k: [])

        result = _run(pipeline.regenerate_tier_plan(_constraints(), "budget", _comparison()))
        it = result["plans"][0]["itinerary"]
        assert it["currency"] == "INR"
        assert it["total_days"] == 5
        assert it["destination"] == "Delhi, India"

    def test_missing_tier_returns_none(self, monkeypatch):
        from agents import pipeline

        async def fake_gen(model, prompt, task, stage):
            pytest.fail("should not generate for a missing tier")

        monkeypatch.setattr(pipeline, "_generate_structured", fake_gen)
        result = _run(pipeline.regenerate_tier_plan(_constraints(), "luxury", _comparison()))
        assert result is None

    def test_validation_failure_retries_then_fails(self, monkeypatch):
        from agents import pipeline
        from agents.validation import Issue

        calls = []

        async def fake_gen(model, prompt, task, stage):
            calls.append(task)
            return _plan("balanced", 48000), {}

        monkeypatch.setattr(pipeline, "_generate_structured", fake_gen)
        monkeypatch.setattr(
            pipeline,
            "validate_comparison",
            lambda c, k: [Issue(code="x", severity="error", message="bad total")],
        )

        result = _run(pipeline.regenerate_tier_plan(_constraints(), "balanced", _comparison()))
        assert result is None
        assert len(calls) == pipeline._MAX_GENERATION_ATTEMPTS
        assert "issues_to_fix" in calls[-1]  # feedback loop engaged

    def test_cancel_and_budget_guards(self, monkeypatch):
        from agents import pipeline

        async def fake_gen(model, prompt, task, stage):
            pytest.fail("guards must short-circuit before generation")

        monkeypatch.setattr(pipeline, "_generate_structured", fake_gen)

        class _Ev:
            def is_set(self):
                return True

        assert _run(
            pipeline.regenerate_tier_plan(_constraints(), "budget", _comparison(), cancel_event=_Ev())
        ) is None
        assert _run(
            pipeline.regenerate_tier_plan(
                _constraints(), "budget", _comparison(), budget_check=lambda: True
            )
        ) is None


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------


def _create_dev_session():
    import asyncio

    from oauth import DEV_USER, create_session
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(create_session(DEV_USER))
    finally:
        loop.close()


@pytest.fixture
def client(monkeypatch):
    import main as main_module

    mock_thread_store = MagicMock()
    mock_thread_store.list_threads = AsyncMock(return_value=[])
    mock_thread_store.count_threads = AsyncMock(return_value=0)
    mock_thread_store.update_status = AsyncMock()
    mock_thread_store.upsert_thread = AsyncMock()

    session_id = _create_dev_session()

    with (
        patch.object(main_module, "thread_store", mock_thread_store),
        TestClient(main_module.app) as c,
    ):
        c.cookies.set("voyager_session", session_id)
        c.cookies.set("voyager_csrf", "test-csrf-token")
        yield c


def _scoped_thread_id(raw: str = "tier-test") -> str:
    user_tag = hashlib.sha256(b"dev@localhost").hexdigest()[:12]
    return f"chat:{user_tag}:{raw}"


def _wire_stores(monkeypatch, *, constraints=None, comparison=None):
    """Point payload_store thread-state reads at fixtures."""
    import agents.pipeline as pipeline_module
    import payload_store as ps_module

    async def fake_get_state(tid, key):
        return {
            "constraints": constraints,
            "latest_comparison": comparison,
            "latest_comparison_id": "pc1",
        }.get(key)

    captured = {}

    async def fake_set_state(tid, key, data):
        captured[key] = data

    monkeypatch.setattr(ps_module.payload_store, "get_thread_state", fake_get_state)
    monkeypatch.setattr(ps_module.payload_store, "set_thread_state", fake_set_state)
    monkeypatch.setattr(pipeline_module, "get_latest_comparison", AsyncMock(return_value=comparison))
    return captured


class TestRegenerateTierEndpoint:
    def test_requires_thread_id_and_valid_tier(self, client):
        assert client.post("/chat/regenerate-tier", json={}).status_code == 400
        assert (
            client.post(
                "/chat/regenerate-tier",
                json={"thread_id": "x", "tier": "luxury"},
            ).status_code
            == 422
        )

    def test_missing_constraints_returns_409(self, client, monkeypatch):
        _wire_stores(monkeypatch, constraints=None, comparison=_comparison())
        resp = client.post(
            "/chat/regenerate-tier",
            json={"thread_id": _scoped_thread_id(), "tier": "premium"},
        )
        assert resp.status_code == 409
        detail = resp.json()["detail"]
        # Structured error: {"code", "message"} — legacy string detail also accepted
        if isinstance(detail, dict):
            assert detail["code"] == "constraints_expired"
        else:
            assert "constraints_expired" in detail

    def test_missing_comparison_returns_404(self, client, monkeypatch):
        _wire_stores(monkeypatch, constraints=_constraints().model_dump(), comparison=None)
        resp = client.post(
            "/chat/regenerate-tier",
            json={"thread_id": _scoped_thread_id(), "tier": "budget"},
        )
        assert resp.status_code == 404

    def test_pipeline_failure_returns_502_and_keeps_card(self, client, monkeypatch):
        import agents.pipeline as pipeline_module

        _wire_stores(monkeypatch, constraints=_constraints().model_dump(), comparison=_comparison())
        monkeypatch.setattr(
            pipeline_module, "regenerate_tier_plan", AsyncMock(return_value=None)
        )
        resp = client.post(
            "/chat/regenerate-tier",
            json={"thread_id": _scoped_thread_id(), "tier": "balanced"},
        )
        assert resp.status_code == 502

    def test_success_returns_updated_comparison_and_persists(self, client, monkeypatch):
        import agents.pipeline as pipeline_module

        updated = _comparison()
        updated["plans"][1] = _plan("balanced", 46000)
        updated["comparison_matrix"]["total_cost"]["balanced"] = 46000

        captured = _wire_stores(
            monkeypatch, constraints=_constraints().model_dump(), comparison=_comparison()
        )
        fake_regen = AsyncMock(return_value=updated)
        monkeypatch.setattr(pipeline_module, "regenerate_tier_plan", fake_regen)

        resp = client.post(
            "/chat/regenerate-tier",
            json={"thread_id": _scoped_thread_id(), "tier": "balanced"},
        )
        assert resp.status_code == 200
        body = resp.json()["comparison"]
        assert body["plans"][1]["itinerary"]["estimated_total_cost_usd"] == 46000
        assert captured["latest_comparison"] == updated
        # Replayable record updated so reload shows the regenerated card
        assert captured["payload:pc1"] == {"kind": "comparison", "data": updated}

        # Scoped thread id + tier reached the pipeline call
        args, _kwargs = fake_regen.call_args
        assert args[1] == "balanced"

    def test_requires_auth(self, monkeypatch):
        import main as main_module

        with TestClient(main_module.app) as c:
            resp = c.post(
                "/chat/regenerate-tier",
                json={"thread_id": "x", "tier": "budget"},
            )
        assert resp.status_code in (401, 403)
