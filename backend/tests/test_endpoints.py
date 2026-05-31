"""Tests for FastAPI endpoints — health, plan, replan-day.

Requires GEMINI_API_KEY to be set in environment for live /plan testing.
If not set, those tests are skipped.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from models import Itinerary, PlanRequest, PlanResponse

pytestmark = pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY not set — skipping live endpoint tests",
)


class TestHealth:
    def test_health_returns_ok(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_health_method_not_allowed(self, client: TestClient):
        resp = client.post("/health")
        assert resp.status_code == 405


class TestPlanEndpoint:
    def test_plan_basic_itinerary(self, client: TestClient, valid_plan_payload):
        resp = client.post("/plan", json=valid_plan_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["error"] is None

        itinerary = data["itinerary"]
        assert itinerary["destination"] == "Tokyo, Japan"
        assert itinerary["total_days"] == 5
        assert len(itinerary["days"]) == 5
        assert itinerary["budget_status"] in ("within", "under", "over")
        assert itinerary["visa_note"]
        assert itinerary["best_season_note"]

        for day in itinerary["days"]:
            assert "day" in day
            assert "theme" in day
            assert "morning" in day
            assert "afternoon" in day
            assert "evening" in day
            assert "transport" in day
            assert "accommodation" in day
            assert "daily_cost_usd" in day
            for slot in ("morning", "afternoon", "evening"):
                assert "activity" in day[slot]
                assert "location" in day[slot]
                assert "cost_usd" in day[slot]
                assert "duration" in day[slot]

    def test_plan_budget_style(self, client: TestClient):
        payload = {
            "destination": "Bali, Indonesia",
            "days": 4,
            "budget_usd": 1500,
            "travel_style": "adventure",
            "group_type": "couple",
        }
        resp = client.post("/plan", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["itinerary"]["destination"] == "Bali, Indonesia"

    def test_plan_low_budget(self, client: TestClient):
        payload = {
            "destination": "Delhi",
            "days": 3,
            "budget_usd": 200,
            "travel_style": "budget",
            "group_type": "solo",
        }
        resp = client.post("/plan", json=payload)
        assert resp.status_code == 200

    def test_plan_family_trip(self, client: TestClient):
        payload = {
            "destination": "Orlando, Florida",
            "days": 7,
            "budget_usd": 5000,
            "travel_style": "adventure",
            "group_type": "family",
            "dietary": "kid-friendly meals",
            "constraints": "need breaks for young children",
        }
        resp = client.post("/plan", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["itinerary"]["total_days"] == 7

    def test_plan_invalid_payload(self, client: TestClient):
        resp = client.post("/plan", json={"destination": ""})
        assert resp.status_code == 422

    def test_plan_response_model_valid(self, client: TestClient, valid_plan_payload):
        resp = client.post("/plan", json=valid_plan_payload)
        data = resp.json()
        PlanResponse(**data)
        if data["itinerary"]:
            Itinerary.model_validate(data["itinerary"])


class TestReplanEndpoint:
    def _create_itinerary(self, client: TestClient) -> dict:
        payload = {
            "destination": "Rome, Italy",
            "days": 3,
            "budget_usd": 2000,
            "travel_style": "cultural",
            "group_type": "couple",
        }
        resp = client.post("/plan", json=payload)
        return resp.json()["itinerary"]

    def test_replan_day(self, client: TestClient):
        itinerary = self._create_itinerary(client)
        resp = client.post(
            "/replan-day",
            json={
                "itinerary": itinerary,
                "day_number": 1,
                "reason": "Need more outdoor activities instead of museums",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["itinerary"]["total_days"] == 3
        assert len(data["itinerary"]["days"]) == 3

    def test_replan_out_of_range(self, client: TestClient):
        itinerary = self._create_itinerary(client)
        resp = client.post(
            "/replan-day",
            json={
                "itinerary": itinerary,
                "day_number": 99,
                "reason": "Testing out of range",
            },
        )
        assert resp.status_code == 400
        assert "out of range" in resp.json()["detail"].lower()

    def test_replan_invalid_reason(self, client: TestClient):
        itinerary = self._create_itinerary(client)
        resp = client.post(
            "/replan-day",
            json={
                "itinerary": itinerary,
                "day_number": 1,
                "reason": "OK",
            },
        )
        assert resp.status_code == 200
