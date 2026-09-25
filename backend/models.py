"""Pydantic models for request/response validation."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Activity(BaseModel):
    activity: str
    location: str
    cost_usd: int
    duration: str
    # Optional enrichments — emitted by the itinerary pipeline when grounded
    # (local start time, why-this-slot note, booking hint, meal suggestion).
    time: str | None = None
    why: str | None = None
    book: str | None = None
    food: str | None = None


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
    # Optional enrichments — day weather chip + total walking estimate.
    weather: str | None = None
    walking_km: float | None = None


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
    file_id: str = Field(..., max_length=100, description="Unique file ID from POST /upload.")
    filename: str = Field(..., max_length=200, description="Original filename.")
    content_type: str = Field(..., max_length=100, description="MIME type (e.g. image/jpeg).")
    data_url: str | None = Field(
        None,
        max_length=14_000_000,
        description="Base64 data URL — optional; the server resolves stored bytes via file_id when available.",
    )


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
    currency: str | None = Field(
        None, max_length=10, description="User's preferred currency code (e.g. 'USD', 'INR', 'EUR')."
    )
    attachments: list[AttachmentInfo] = Field(
        default_factory=list, max_length=5, description="File attachments (images, PDFs)."
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


# ---------------------------------------------------------------------------
# Response models — typed return shapes for OpenAPI documentation
# ---------------------------------------------------------------------------

# --- Ops ---

class HealthResponse(BaseModel):
    status: str = Field(..., description='"ok" if Redis is connected, "degraded" otherwise.')
    redis: str = Field(..., description='"connected" or "unavailable".')
    agent: str = Field(..., description='Always "deepagent" (identifies the agent framework).')


# --- Admin ---

class PerDayItem(BaseModel):
    date: str = Field(..., description="Date in YYYY-MM-DD format.")
    cost: float = Field(..., description="Total cost on that date (USD).")


class PerSubagentItem(BaseModel):
    name: str = Field(..., description="Subagent name (e.g. 'research', 'weather').")
    cost: float = Field(..., description="Total cost for this subagent (USD).")
    input_tokens: int = Field(..., description="Total input tokens consumed.")
    output_tokens: int = Field(..., description="Total output tokens consumed.")


class TopUserItem(BaseModel):
    user_id: str = Field(..., description="User identifier (email or hashed ID).")
    cost: float = Field(..., description="Total cost for this user (USD).")


class PoorEfficiencyItem(BaseModel):
    thread_id: str = Field(..., description="Thread ID with poor efficiency.")
    user_id: str = Field(..., description="User ID for this thread.")
    efficiency_ratio: float = Field(..., description="Token-to-cost ratio (>50 is poor).")
    cost: float = Field(..., description="Total cost for this thread (USD).")


class CostAnalyticsResponse(BaseModel):
    total_cost: float = Field(..., description="Total cost across all sessions (USD).")
    total_conversations: int = Field(..., description="Number of conversations in the period.")
    avg_cost_per_conversation: float = Field(..., description="Average cost per conversation (USD).")
    total_input_tokens: int = Field(..., description="Total input tokens consumed.")
    total_output_tokens: int = Field(..., description="Total output tokens consumed.")
    per_day: list[PerDayItem] = Field(default_factory=list, description="Cost breakdown by day.")
    per_subagent: list[PerSubagentItem] = Field(default_factory=list, description="Cost breakdown by subagent.")
    top_users: list[TopUserItem] = Field(default_factory=list, description="Top 10 users by spend.")
    poor_efficiency_sessions: list[PoorEfficiencyItem] = Field(default_factory=list, description="Sessions with >50:1 efficiency ratio.")


class ThreadCostBreakdownResponse(BaseModel):
    session: dict = Field(..., description="Per-session cost data (thread_id, user_id, tokens, cost, etc.).")
    subagents: dict = Field(..., description="Per-subagent cost breakdown for this thread.")


class FeedbackCommentItem(BaseModel):
    comment: str = Field(..., description="Feedback comment text.")
    thread_id: str = Field(..., description="Thread ID the feedback belongs to.")
    created_at: float = Field(..., description="Unix timestamp of feedback creation.")


class FeedbackStatsResponse(BaseModel):
    total_up: int = Field(..., description="Number of thumbs-up ratings.")
    total_down: int = Field(..., description="Number of thumbs-down ratings.")
    total_ratings: int = Field(..., description="Total number of ratings.")
    satisfaction_ratio: float = Field(..., description="Ratio of up ratings to total (0.0–1.0).")
    recent_comments: list[FeedbackCommentItem] = Field(default_factory=list, description="Last 20 thumbs-down comments.")


class SecurityFlagsResponse(BaseModel):
    total_flags: int = Field(..., description="Total injection flags in the period.")
    by_category: dict[str, int] = Field(default_factory=dict, description="Flags grouped by category (instruction_override, extraction_attempt, etc.).")
    by_source: dict[str, int] = Field(default_factory=dict, description="Flags grouped by source (message, pdf, web).")
    by_confidence: dict[str, int] = Field(default_factory=dict, description="Flags grouped by confidence level (low, high).")
    unique_users: int = Field(..., description="Number of unique users flagged.")
    active_cooldowns: int = Field(..., description="Number of currently active cooldowns.")
    recent_flags: list[dict] = Field(default_factory=list, description="Recent flag entries with details.")


class CooldownItem(BaseModel):
    user_hash: str = Field(..., description="Hashed user ID (12-char SHA256 prefix).")
    until: float = Field(..., description="Unix timestamp when cooldown expires.")
    remaining_seconds: int = Field(..., description="Seconds remaining in cooldown.")


class CooldownListResponse(BaseModel):
    cooldowns: list[CooldownItem] = Field(default_factory=list, description="Active cooldowns.")
    count: int = Field(..., description="Number of active cooldowns.")


class CooldownRemoveResponse(BaseModel):
    status: str = Field(..., description='"ok" if removed, "not_found" if no cooldown existed.')
    user_hash: str = Field(..., description="Hashed user ID that was targeted.")


class CacheInvalidateResponse(BaseModel):
    status: str = Field(..., description='Always "ok".')
    cleared: int = Field(..., description="Number of cache entries cleared.")


# --- Feedback ---

class FeedbackSubmitResponse(BaseModel):
    status: str = Field(..., description='Always "ok".')
    rating: str = Field(..., description="The rating that was submitted ('up' or 'down').")


# --- Preferences ---

class PreferencesSaveResponse(BaseModel):
    status: str = Field(..., description='"ok" or "error".')
    user_id: str = Field(..., description="User ID.")
    error: str | None = Field(None, description="Error message if status is 'error'.")


# --- Upload ---

class UploadResponse(BaseModel):
    file_id: str = Field(..., description="Unique file ID (UUID).")
    data_url: str = Field(..., description="Base64 data URL for frontend rendering.")
    filename: str = Field(..., description="Original filename.")
    content_type: str = Field(..., description="MIME type (e.g. image/jpeg).")
    size: int = Field(..., description="File size in bytes.")


# --- Chat ---

class ChatCancelResponse(BaseModel):
    cancelled: bool = Field(..., description="True if the stream was cancelled, False if no active stream found.")


# --- Threads ---

class ThreadInfo(BaseModel):
    thread_id: str = Field(..., description="Unique thread identifier.")
    summary: str = Field(..., description="AI-generated summary of the conversation.")
    created_at: float = Field(..., description="Unix timestamp of thread creation.")
    updated_at: float = Field(..., description="Unix timestamp of last update.")
    status: str = Field(..., description='Thread status: "idle", "busy", or "error".')
    message_count: int = Field(..., description="Number of messages in the thread.")
    search_text: str = Field("", description="Searchable text content.")
    pinned: bool = Field(False, description="Whether the thread is pinned.")
    pinned_at: float = Field(0.0, description="Unix timestamp when pinned.")


class ThreadListResponse(BaseModel):
    threads: list[ThreadInfo] = Field(default_factory=list, description="List of threads.")
    has_more: bool = Field(..., description="True if more threads are available via pagination.")


class ThreadSearchResult(BaseModel):
    thread_id: str = Field(..., description="Thread ID.")
    summary: str = Field(..., description="Thread summary.")
    snippet: str = Field(..., description="Matching text snippet.")
    created_at: float = Field(..., description="Unix timestamp of thread creation.")


class ThreadSearchResponse(BaseModel):
    results: list[ThreadSearchResult] = Field(default_factory=list, description="Search results.")
    total: int = Field(..., description="Total number of matching results.")
    has_more: bool = Field(..., description="True if more results are available.")


class ThreadMessage(BaseModel):
    role: str = Field(..., description='Message role: "user" or "assistant".')
    content: str = Field(..., description="Message text content.")
    itinerary: dict | None = Field(None, description="Structured itinerary data (assistant messages only).")
    comparison: dict | None = Field(None, description="Comparison data (assistant messages only).")
    activity: dict | None = Field(None, description="Activity metadata (maps, charts, images).")
    images: list[str] | None = Field(None, description="List of image URLs from activity metadata.")
    charts: list[dict] | None = Field(None, description="List of chart data from activity metadata.")


class BranchInfo(BaseModel):
    checkpoint_id: str = Field(..., description="Checkpoint ID for this branch.")
    is_current: bool = Field(..., description="True if this is the currently active branch.")
    preview: str = Field(..., description="First 200 characters of the branch's last message.")


class ThreadBranchesResponse(BaseModel):
    branches: list[BranchInfo] = Field(default_factory=list, description="List of branches from the fork point.")


class ThreadDeleteResponse(BaseModel):
    status: str = Field(..., description='Always "ok".')
    thread_id: str = Field(..., description="ID of the deleted thread.")


class ThreadUpdateResponse(BaseModel):
    status: str = Field(..., description='Always "ok".')
    thread_id: str = Field(..., description="ID of the updated thread.")


# --- Auth ---

class AuthMeResponse(BaseModel):
    user_id: str = Field(..., description="User identifier (email).")
    display_name: str = Field(..., description="User's display name.")
    avatar_url: str | None = Field(None, description="URL to user's avatar image.")
    email: str = Field(..., description="User's email address.")
    is_admin: bool = Field(False, description="Whether the user has admin privileges.")


class AuthLogoutResponse(BaseModel):
    status: str = Field(..., description='Always "ok".')


# --- Share ---

class ShareCreateResponse(BaseModel):
    share_url: str = Field(..., description="Full URL to view the shared itinerary.")
    expires_at: float = Field(..., description="Unix timestamp when the share link expires.")
    destination: str = Field(..., description="Destination name for the itinerary.")


class ShareGetResponse(BaseModel):
    itinerary: dict = Field(..., description="Full itinerary data (Itinerary model as JSON).")
    destination: str = Field(..., description="Destination name.")
    created_at: float = Field(..., description="Unix timestamp of share creation.")
    expires_at: float = Field(..., description="Unix timestamp when share expires.")
    image_base64: str | None = Field(None, description="Base64-encoded destination image PNG, if generated.")


class ShareRevokeResponse(BaseModel):
    status: str = Field(..., description='Always "ok".')


class ShareListItem(BaseModel):
    token: str = Field(..., description="Share token (used in URL).")
    thread_id: str = Field(..., description="Thread ID the share belongs to.")
    destination: str = Field(..., description="Destination name.")
    created_at: float = Field(..., description="Unix timestamp of share creation.")
    expires_at: float = Field(..., description="Unix timestamp when share expires.")
    share_url: str = Field(..., description="Full URL to view the shared itinerary.")
