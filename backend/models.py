"""Pydantic models for request/response validation."""

from __future__ import annotations

import re
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, ValidationInfo, field_validator


class TravelStyle(str, Enum):
    ADVENTURE = "adventure"
    CULTURAL = "cultural"
    LUXURY = "luxury"
    BUDGET = "budget"


class GroupType(str, Enum):
    SOLO = "solo"
    COUPLE = "couple"
    FAMILY = "family"


class PlanRequest(BaseModel):
    destination: str = Field(
        ..., min_length=1, max_length=200, description="Travel destination city or region."
    )
    days: int = Field(..., ge=1, le=30, description="Number of travel days (1–30).")
    budget_usd: int = Field(..., ge=50, description="Total trip budget in USD (minimum $50).")
    travel_style: TravelStyle = Field(..., description="Preferred travel style.")
    group_type: GroupType = Field(..., description="Group composition.")
    dietary: Optional[str] = Field(
        None, max_length=500, description="Dietary restrictions or preferences."
    )
    constraints: Optional[str] = Field(
        None, max_length=1000, description="Additional constraints or requests."
    )

    @field_validator("destination")
    @classmethod
    def destination_must_be_meaningful(cls, v: str) -> str:
        stripped = v.strip()
        if len(stripped) < 2:
            raise ValueError("Destination must be at least 2 characters long.")
        if stripped.isdigit():
            raise ValueError("Destination cannot be purely numeric.")
        if re.match(r"^[^a-zA-Z]*$", stripped):
            raise ValueError("Destination must contain at least one letter.")
        return stripped

    @field_validator("budget_usd")
    @classmethod
    def budget_must_be_reasonable(cls, v: int, info: ValidationInfo) -> int:
        days = info.data.get("days", 1)
        per_day = v // days
        if per_day < 20:
            raise ValueError(
                f"Budget of ${v} for {days} days (${per_day}/day) is too low. "
                f"Minimum recommended is ${20 * days}."
            )
        return v

    @field_validator("dietary", "constraints", mode="before")
    @classmethod
    def strip_optional_strings(cls, v: str | None) -> str | None:
        if v is None:
            return None
        stripped = v.strip()
        return stripped if stripped else None


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


class PlanResponse(BaseModel):
    success: bool = True
    itinerary: Optional[Itinerary] = None
    error: Optional[str] = None


class ReplanRequest(BaseModel):
    itinerary: Itinerary
    day_number: int = Field(..., ge=1, description="Day number to replan.")
    reason: str = Field(
        ..., min_length=1, max_length=1000, description="Reason for replanning."
    )

    @field_validator("reason")
    @classmethod
    def reason_must_be_meaningful(cls, v: str) -> str:
        stripped = v.strip()
        if len(stripped) < 2:
            raise ValueError("Please provide a meaningful reason for replanning.")
        return stripped
