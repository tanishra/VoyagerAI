"""Tests for Pydantic models — validation, serialization, edge cases."""

from __future__ import annotations

from models import (
    Activity,
    AuthLogoutResponse,
    AuthMeResponse,
    CacheInvalidateResponse,
    ChatCancelResponse,
    CooldownItem,
    CooldownListResponse,
    CooldownRemoveResponse,
    CostAnalyticsResponse,
    DayPlan,
    FeedbackSubmitResponse,
    HealthResponse,
    Itinerary,
    PreferencesSaveResponse,
    ShareCreateResponse,
    ShareRevokeResponse,
    ThreadDeleteResponse,
    ThreadInfo,
    ThreadListResponse,
    ThreadUpdateResponse,
    UploadResponse,
)


class TestModels:
    def test_activity_model(self, sample_activity_dict):
        activity = Activity(**sample_activity_dict)
        assert activity.activity == "Test"
        assert activity.cost_usd == 10

    def test_day_plan_model(self, sample_activity_dict):
        day = DayPlan(
            day=1,
            theme="Test Day",
            morning=Activity(**sample_activity_dict),
            afternoon=Activity(**sample_activity_dict),
            evening=Activity(**sample_activity_dict),
            transport="Bus",
            accommodation="Hostel",
            daily_cost_usd=50,
            tips=["Tip 1"],
        )
        assert day.day == 1
        assert len(day.tips) == 1
        assert day.daily_cost_usd == 50

    def test_itinerary_round_trip(self, sample_itinerary_dict):
        itinerary = Itinerary.model_validate(sample_itinerary_dict)
        assert itinerary.destination == "Paris"
        assert len(itinerary.days) == 3
        assert itinerary.budget_status == "within"
        restored = itinerary.model_dump()
        assert restored["destination"] == "Paris"
        assert len(restored["days"]) == 3

    def test_itinerary_default_empty_lists(self):
        """Ensure warnings and packing_essentials default to empty lists."""
        itinerary = Itinerary(
            destination="Test",
            total_days=1,
            estimated_total_cost_usd=100,
            budget_status="within",
            visa_note="None",
            best_season_note="Anytime",
            days=[
                DayPlan(
                    day=1,
                    theme="Test",
                    morning=Activity(activity="A", location="L", cost_usd=10, duration="1h"),
                    afternoon=Activity(activity="A", location="L", cost_usd=10, duration="1h"),
                    evening=Activity(activity="A", location="L", cost_usd=10, duration="1h"),
                    transport="Walk",
                    accommodation="None",
                    daily_cost_usd=30,
                )
            ],
        )
        assert itinerary.warnings == []
        assert itinerary.packing_essentials == []


class TestResponseModels:
    """Tests for Phase 6.31 response models — validation, serialization, defaults."""

    def test_health_response(self):
        m = HealthResponse(status="ok", redis="connected", agent="deepagent")
        assert m.status == "ok"
        assert m.redis == "connected"
        assert m.agent == "deepagent"

    def test_cost_analytics_response(self):
        m = CostAnalyticsResponse(
            total_cost=12.34,
            total_conversations=42,
            avg_cost_per_conversation=0.29,
            total_input_tokens=150000,
            total_output_tokens=80000,
        )
        assert m.total_cost == 12.34
        assert m.per_day == []
        assert m.per_subagent == []
        assert m.top_users == []
        assert m.poor_efficiency_sessions == []

    def test_feedback_submit_response(self):
        m = FeedbackSubmitResponse(status="ok", rating="up")
        assert m.status == "ok"
        assert m.rating == "up"

    def test_preferences_save_response(self):
        m = PreferencesSaveResponse(status="ok", user_id="user@example.com")
        assert m.status == "ok"
        assert m.user_id == "user@example.com"
        assert m.error is None

    def test_preferences_save_response_with_error(self):
        m = PreferencesSaveResponse(
            status="error", user_id="user@example.com", error="Store unavailable"
        )
        assert m.status == "error"
        assert m.error == "Store unavailable"

    def test_upload_response(self):
        m = UploadResponse(
            file_id="abc-123",
            data_url="data:image/jpeg;base64,/9j/...",
            filename="photo.jpg",
            content_type="image/jpeg",
            size=102400,
        )
        assert m.file_id == "abc-123"
        assert m.size == 102400

    def test_chat_cancel_response(self):
        m = ChatCancelResponse(cancelled=True)
        assert m.cancelled is True

    def test_thread_info_defaults(self):
        m = ThreadInfo(
            thread_id="chat:abc:def",
            summary="Paris trip",
            created_at=1735689600,
            updated_at=1735693200,
            status="idle",
            message_count=4,
        )
        assert m.pinned is False
        assert m.pinned_at == 0.0
        assert m.search_text == ""

    def test_thread_list_response(self):
        m = ThreadListResponse(threads=[], has_more=False)
        assert m.threads == []
        assert m.has_more is False

    def test_thread_delete_response(self):
        m = ThreadDeleteResponse(status="ok", thread_id="chat:abc:def")
        assert m.status == "ok"
        assert m.thread_id == "chat:abc:def"

    def test_thread_update_response(self):
        m = ThreadUpdateResponse(status="ok", thread_id="chat:abc:def")
        assert m.status == "ok"

    def test_auth_me_response(self):
        m = AuthMeResponse(
            user_id="user@example.com",
            display_name="Jane",
            avatar_url=None,
            email="user@example.com",
        )
        assert m.user_id == "user@example.com"
        assert m.avatar_url is None

    def test_auth_logout_response(self):
        m = AuthLogoutResponse(status="ok")
        assert m.status == "ok"

    def test_share_create_response(self):
        m = ShareCreateResponse(
            share_url="http://localhost:3000/en/share/abc",
            expires_at=1736294400,
            destination="Paris",
        )
        assert m.destination == "Paris"

    def test_share_revoke_response(self):
        m = ShareRevokeResponse(status="ok")
        assert m.status == "ok"

    def test_cache_invalidate_response(self):
        m = CacheInvalidateResponse(status="ok", cleared=42)
        assert m.cleared == 42

    def test_cooldown_item(self):
        m = CooldownItem(
            user_hash="abc123def456",
            until=1736294400,
            remaining_seconds=3600,
        )
        assert m.remaining_seconds == 3600

    def test_cooldown_list_response(self):
        m = CooldownListResponse(cooldowns=[], count=0)
        assert m.count == 0
        assert m.cooldowns == []

    def test_cooldown_remove_response(self):
        m = CooldownRemoveResponse(status="ok", user_hash="abc123def456")
        assert m.status == "ok"

    def test_response_models_have_field_descriptions(self):
        """All response model fields should have descriptions for OpenAPI docs."""
        models = [
            HealthResponse,
            CostAnalyticsResponse,
            FeedbackSubmitResponse,
            PreferencesSaveResponse,
            UploadResponse,
            ChatCancelResponse,
            ThreadInfo,
            ThreadListResponse,
            ThreadDeleteResponse,
            ThreadUpdateResponse,
            AuthMeResponse,
            AuthLogoutResponse,
            ShareCreateResponse,
            ShareRevokeResponse,
            CacheInvalidateResponse,
            CooldownListResponse,
            CooldownRemoveResponse,
        ]
        for model in models:
            for field_name, field_info in model.model_fields.items():
                assert field_info.description, (
                    f"{model.__name__}.{field_name} missing description"
                )


class TestEnrichmentFields:
    """Optional enrichment fields — emitted by the pipeline when grounded."""

    def test_activity_enrichment_optional(self, sample_activity_dict):
        activity = Activity(**sample_activity_dict)
        assert activity.time is None
        assert activity.why is None
        assert activity.book is None
        assert activity.food is None

    def test_activity_accepts_enrichment(self, sample_activity_dict):
        activity = Activity(
            **sample_activity_dict,
            time="09:30",
            why="Beat crowds",
            book="Book ahead",
            food="Croissant nearby",
        )
        assert activity.time == "09:30"
        assert activity.food == "Croissant nearby"

    def test_day_plan_enrichment_optional(self, sample_activity_dict):
        day = DayPlan(
            day=1,
            theme="T",
            morning=Activity(**sample_activity_dict),
            afternoon=Activity(**sample_activity_dict),
            evening=Activity(**sample_activity_dict),
            transport="Bus",
            accommodation="Hotel",
            daily_cost_usd=100,
        )
        assert day.weather is None
        assert day.walking_km is None

    def test_day_plan_accepts_enrichment(self, sample_activity_dict):
        day = DayPlan(
            day=1,
            theme="T",
            morning=Activity(**sample_activity_dict),
            afternoon=Activity(**sample_activity_dict),
            evening=Activity(**sample_activity_dict),
            transport="Bus",
            accommodation="Hotel",
            daily_cost_usd=100,
            weather="28°C sunny",
            walking_km=5.5,
        )
        assert day.weather == "28°C sunny"
        assert day.walking_km == 5.5

    def test_day_plan_date_optional(self, sample_activity_dict):
        day = DayPlan(
            day=1,
            theme="T",
            morning=Activity(**sample_activity_dict),
            afternoon=Activity(**sample_activity_dict),
            evening=Activity(**sample_activity_dict),
            transport="Bus",
            accommodation="Hotel",
            daily_cost_usd=100,
            date="2026-03-10",
        )
        assert day.date == "2026-03-10"
        day2 = DayPlan(
            day=1, theme="T",
            morning=Activity(**sample_activity_dict),
            afternoon=Activity(**sample_activity_dict),
            evening=Activity(**sample_activity_dict),
            transport="Bus", accommodation="Hotel", daily_cost_usd=100,
        )
        assert day2.date is None
