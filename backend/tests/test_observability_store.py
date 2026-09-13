"""Tests for the observability store (observability_store.py).

Uses in-memory fallback by forcing Redis unavailable. Verifies:
- Session lifecycle (start, finalize)
- Event recording with PII redaction
- Error tracking
- Session queries with filters
- Usage aggregation
- Error summary aggregation
"""

import asyncio
import time
import pytest

from observability_store import ObservabilityStore, _hash_user_id, _redact_tool_input


@pytest.fixture
def store(monkeypatch):
    """Fresh ObservabilityStore with in-memory fallback (no Redis, no SQLite)."""
    # Force in-memory mode by making both Redis and SQLite unavailable
    monkeypatch.setattr("observability_store.get_sqlite_connection", _async_none)
    s = ObservabilityStore()
    s._redis = None
    return s


async def _async_none():
    """Async helper that returns None — used to mock out SQLite fallback."""
    return None


# --- PII redaction tests ---

def test_hash_user_id_consistent():
    h1 = _hash_user_id("user123")
    h2 = _hash_user_id("user123")
    assert h1 == h2
    assert len(h1) == 12


def test_hash_user_id_different_users():
    h1 = _hash_user_id("user123")
    h2 = _hash_user_id("user456")
    assert h1 != h2


def test_hash_user_id_no_raw_id():
    uid = "my-secret-user-id-123"
    h = _hash_user_id(uid)
    assert uid not in h


def test_redact_tool_input_string():
    result = _redact_tool_input("short text")
    assert result == "short text"


def test_redact_tool_input_long_string():
    long_text = "x" * 600
    result = _redact_tool_input(long_text)
    assert "..." in result
    assert len(result) <= 503


def test_redact_tool_input_pii_fields():
    tool_input = {"message": "What's the weather in Paris?", "name": "get_weather"}
    result = _redact_tool_input(tool_input)
    assert isinstance(result, dict)
    assert result["message"]["_redacted"] is True
    assert result["message"]["length"] == len("What's the weather in Paris?")
    assert "hash" in result["message"]
    assert result["name"] == "get_weather"  # non-PII field preserved


def test_redact_tool_input_nested():
    tool_input = {"query": "search term", "metadata": {"text": "nested content"}}
    result = _redact_tool_input(tool_input)
    assert result["query"]["_redacted"] is True
    assert result["metadata"]["text"]["_redacted"] is True


def test_redact_tool_input_list():
    tool_input = {"items": [{"message": "secret1"}, {"name": "keep"}]}
    result = _redact_tool_input(tool_input)
    assert isinstance(result["items"], list)
    assert result["items"][0]["message"]["_redacted"] is True
    assert result["items"][1]["name"] == "keep"


def test_redact_tool_input_none():
    assert _redact_tool_input(None) is None


def test_redact_tool_input_preserves_structure():
    tool_input = {
        "subagent_type": "weather",
        "description": "Get weather info",
        "url": "https://api.weather.com",
    }
    result = _redact_tool_input(tool_input)
    assert result["subagent_type"] == "weather"
    assert result["description"] == "Get weather info"
    assert result["url"] == "https://api.weather.com"


# --- Session lifecycle tests ---

@pytest.mark.asyncio
async def test_start_session(store):
    await store.start_session("thread1", "user1", locale="en", timezone="UTC")
    assert "thread1" in store._mem_sessions
    session = store._mem_sessions["thread1"]
    assert session["status"] == "running"
    assert session["user_hash"] == _hash_user_id("user1")
    assert session["locale"] == "en"


@pytest.mark.asyncio
async def test_finalize_session(store):
    await store.start_session("thread1", "user1")
    await store.finalize_session(
        "thread1", "completed",
        subagent_count=3,
        tool_call_count=5,
        total_tokens_in=1000,
        total_tokens_out=500,
        total_cost_usd=0.05,
        model_used="gpt-4o",
    )
    session = store._mem_sessions["thread1"]
    assert session["status"] == "completed"
    assert session["subagent_count"] == "3"
    assert session["tool_call_count"] == "5"
    assert session["total_tokens_in"] == "1000"
    assert session["total_tokens_out"] == "500"
    assert float(session["total_cost_usd"]) == 0.05
    assert session["model_used"] == "gpt-4o"
    assert float(session["duration_seconds"]) >= 0


# --- Event recording tests ---

@pytest.mark.asyncio
async def test_record_event(store):
    await store.start_session("thread1", "user1")
    await store.record_event(
        thread_id="thread1",
        event_type="tool_start",
        name="get_weather",
        input_data={"message": "What's the weather?", "location": "Paris"},
    )
    events = store._mem_events.get("thread1", [])
    assert len(events) == 1
    evt = events[0]
    assert evt["event_type"] == "tool_start"
    assert evt["name"] == "get_weather"
    # PII should be redacted
    assert isinstance(evt["input"], str)
    assert "_redacted" in evt["input"]


@pytest.mark.asyncio
async def test_record_error_event(store):
    await store.start_session("thread1", "user1")
    await store.record_event(
        thread_id="thread1",
        event_type="tool_error",
        name="get_weather",
        error="API timeout",
    )
    errors = store._mem_errors.get("thread1", [])
    assert len(errors) == 1
    assert errors[0]["error_message"] == "API timeout"
    assert errors[0]["tool_name"] == "get_weather"


@pytest.mark.asyncio
async def test_record_multiple_events(store):
    await store.start_session("thread1", "user1")
    for i in range(5):
        await store.record_event(
            thread_id="thread1",
            event_type="token",
            name=f"event_{i}",
        )
    events = store._mem_events.get("thread1", [])
    assert len(events) == 5


# --- Query tests ---

@pytest.mark.asyncio
async def test_get_sessions(store):
    await store.start_session("thread1", "user1")
    await store.start_session("thread2", "user2")
    await store.finalize_session("thread1", "completed")

    result = await store.get_sessions()
    assert result["total"] >= 2
    assert len(result["sessions"]) >= 2
    thread_ids = [s["thread_id"] for s in result["sessions"]]
    assert "thread1" in thread_ids
    assert "thread2" in thread_ids


@pytest.mark.asyncio
async def test_get_sessions_status_filter(store):
    await store.start_session("thread1", "user1")
    await store.start_session("thread2", "user2")
    await store.finalize_session("thread1", "completed")

    result = await store.get_sessions(status="completed")
    assert all(s["status"] == "completed" for s in result["sessions"])
    assert any(s["thread_id"] == "thread1" for s in result["sessions"])


@pytest.mark.asyncio
async def test_get_sessions_pagination(store):
    for i in range(5):
        await store.start_session(f"thread{i}", f"user{i}")

    result = await store.get_sessions(limit=2, offset=0)
    assert len(result["sessions"]) == 2
    assert result["total"] >= 5

    result2 = await store.get_sessions(limit=2, offset=2)
    assert len(result2["sessions"]) == 2


@pytest.mark.asyncio
async def test_get_session_events(store):
    await store.start_session("thread1", "user1")
    await store.record_event(thread_id="thread1", event_type="token", name="t1")
    await store.record_event(thread_id="thread1", event_type="tool_start", name="tool1")
    await store.record_event(thread_id="thread1", event_type="tool_end", name="tool1")

    events = await store.get_session_events("thread1")
    assert len(events) == 3
    assert events[0]["event_type"] == "token"
    assert events[1]["event_type"] == "tool_start"
    assert events[2]["event_type"] == "tool_end"


@pytest.mark.asyncio
async def test_get_session_events_empty(store):
    events = await store.get_session_events("nonexistent")
    assert events == []


# --- Error query tests ---

@pytest.mark.asyncio
async def test_get_errors(store):
    await store.start_session("thread1", "user1")
    await store.record_event(thread_id="thread1", event_type="tool_error", name="tool1", error="error1")
    await store.record_event(thread_id="thread1", event_type="tool_error", name="tool2", error="error2")

    errors = await store.get_errors()
    assert len(errors) == 2


@pytest.mark.asyncio
async def test_get_errors_with_filter(store):
    await store.start_session("thread1", "user1")
    await store.record_event(thread_id="thread1", event_type="tool_error", name="tool1", error="error1")
    await store.record_event(thread_id="thread1", event_type="tool_error", name="tool2", error="error2")

    errors = await store.get_errors(tool="tool1")
    assert len(errors) == 1
    assert errors[0]["tool_name"] == "tool1"


@pytest.mark.asyncio
async def test_get_error_summary(store):
    await store.start_session("thread1", "user1")
    await store.record_event(thread_id="thread1", event_type="tool_error", name="tool1", error="e1")
    await store.record_event(thread_id="thread1", event_type="tool_error", name="tool1", error="e2")
    await store.record_event(thread_id="thread1", event_type="tool_error", name="tool2", error="e3")

    summary = await store.get_error_summary()
    assert summary["total_errors"] == 3
    assert len(summary["by_subagent"]) >= 1
    assert len(summary["by_tool"]) >= 1


# --- Usage aggregation tests ---

@pytest.mark.asyncio
async def test_get_usage(store):
    await store.start_session("thread1", "user1")
    await store.finalize_session(
        "thread1", "completed",
        total_tokens_in=1000,
        total_tokens_out=500,
        total_cost_usd=0.03,
    )
    await store.start_session("thread2", "user2")
    await store.finalize_session(
        "thread2", "completed",
        total_tokens_in=2000,
        total_tokens_out=1000,
        total_cost_usd=0.06,
    )

    usage = await store.get_usage()
    assert usage["totals"]["tokens_in"] == 3000
    assert usage["totals"]["tokens_out"] == 1500
    assert abs(usage["totals"]["cost"] - 0.09) < 0.001
    assert usage["totals"]["sessions"] == 2
    assert len(usage["per_user"]) == 2


@pytest.mark.asyncio
async def test_get_usage_empty(store):
    usage = await store.get_usage()
    assert usage["totals"]["tokens_in"] == 0
    assert usage["totals"]["cost"] == 0.0
    assert usage["totals"]["sessions"] == 0
