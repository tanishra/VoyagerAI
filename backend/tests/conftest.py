from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    has_provider_key = any(
        os.getenv(key)
        for key in ("GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY")
    )
    if not has_provider_key:
        pytest.skip("No LLM provider API key set — required for app startup")
    from main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_activity_dict() -> dict:
    return {"activity": "Test", "location": "Test", "cost_usd": 10, "duration": "1h"}


@pytest.fixture
def sample_itinerary_dict() -> dict:
    return {
        "destination": "Paris",
        "total_days": 3,
        "estimated_total_cost_usd": 750,
        "budget_status": "within",
        "visa_note": "Schengen visa required",
        "best_season_note": "Spring (April-June)",
        "days": [
            {
                "day": 1,
                "theme": "Arrival & City Orientation",
                "morning": {"activity": "Visit Eiffel Tower", "location": "Champ de Mars", "cost_usd": 25, "duration": "2h"},
                "afternoon": {"activity": "Louvre Museum", "location": "Rue de Rivoli", "cost_usd": 17, "duration": "3h"},
                "evening": {"activity": "Seine River Cruise", "location": "Port de la Bourdonnais", "cost_usd": 15, "duration": "1.5h"},
                "transport": "Metro",
                "accommodation": "Hotel in Le Marais ($150)",
                "daily_cost_usd": 250,
                "tips": ["Book Eiffel Tower tickets in advance"],
            },
            {
                "day": 2,
                "theme": "Art & Culture",
                "morning": {"activity": "Musée d'Orsay", "location": "Rue de Lille", "cost_usd": 16, "duration": "2.5h"},
                "afternoon": {"activity": "Montmartre Walk", "location": "Butte Montmartre", "cost_usd": 0, "duration": "2h"},
                "evening": {"activity": "Moulin Rouge Show", "location": "Place Blanche", "cost_usd": 120, "duration": "3h"},
                "transport": "Metro + Walk",
                "accommodation": "Hotel in Le Marais ($150)",
                "daily_cost_usd": 320,
                "tips": ["Visit Sacré-Cœur at sunset"],
            },
            {
                "day": 3,
                "theme": "Departure",
                "morning": {"activity": "Notre-Dame Cathedral", "location": "Île de la Cité", "cost_usd": 0, "duration": "1h"},
                "afternoon": {"activity": "Luxembourg Gardens", "location": "Rue de Médicis", "cost_usd": 0, "duration": "1.5h"},
                "evening": {"activity": "Departure", "location": "CDG Airport", "cost_usd": 0, "duration": "—"},
                "transport": "Taxi to airport ($40)",
                "accommodation": "N/A",
                "daily_cost_usd": 180,
                "tips": ["Arrive 3h before flight"],
            },
        ],
        "warnings": ["Watch for pickpockets in tourist areas"],
        "packing_essentials": ["Umbrella", "Comfortable walking shoes", "Adapter"],
    }
