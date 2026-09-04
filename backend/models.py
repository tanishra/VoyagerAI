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


class AttachmentInfo(BaseModel):
    file_id: str = Field(..., description="Unique file ID from POST /upload.")
    filename: str = Field(..., max_length=200, description="Original filename.")
    content_type: str = Field(..., max_length=100, description="MIME type (e.g. image/jpeg).")
    data_url: str = Field(..., description="Base64 data URL for frontend rendering.")


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
    timezone: str | None = Field(
        None, max_length=50, description="User's IANA timezone (e.g. 'Asia/Kolkata', 'America/New_York')."
    )
    attachments: list[AttachmentInfo] = Field(
        default_factory=list, description="File attachments (images, PDFs)."
    )


class ThreadUpdateRequest(BaseModel):
    pinned: bool | None = Field(
        None, description="Set to true/false to pin/unpin a thread."
    )


class FeedbackRequest(BaseModel):
    thread_id: str = Field(..., max_length=200, description="Thread ID.")
    message_id: str = Field(..., max_length=200, description="Message ID being rated.")
    rating: str = Field(..., pattern="^(up|down)$", description="Rating: 'up' or 'down'.")
    comment: str | None = Field(
        None, max_length=1000, description="Optional feedback comment."
    )
