"""Pydantic models for request/response validation."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Activity(BaseModel):
    activity: str
    location: str
    cost_usd: int
    duration: str


class DayPlan(BaseModel):
    day: int
    theme: str
    morning: Activity
    afternoon: Activity
    evening: Activity
    transport: str
    accommodation: str
    daily_cost_usd: int
    tips: list[str] = Field(default_factory=list)


class Itinerary(BaseModel):
    destination: str
    total_days: int
    estimated_total_cost_usd: int
    budget_status: str
    visa_note: str
    best_season_note: str
    days: list[DayPlan]
    warnings: list[str] = Field(default_factory=list)
    packing_essentials: list[str] = Field(default_factory=list)


class ChatRequest(BaseModel):
    message: str = Field(
        ..., min_length=1, max_length=2000, description="User chat message."
    )
    thread_id: str | None = Field(
        None, max_length=200, description="Thread ID for resuming a previous conversation."
    )
    client_message_id: str | None = Field(
        None, max_length=100, description="Client-generated UUID for offline message dedup."
    )
    locale: str | None = Field(
        None, max_length=10, description="User's preferred locale (e.g. 'en', 'es', 'fr')."
    )


class ThreadUpdateRequest(BaseModel):
    pinned: bool | None = Field(
        None, description="Set to true/false to pin/unpin a thread."
    )
