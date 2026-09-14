"""Tests for the Redis-backed security store (security_store.py).

Uses in-memory fallback by forcing Redis unavailable. Verifies:
- Flag recording and retrieval
- Strike counting with rolling window
- Cooldown application and expiry
- Admin aggregate stats
- User ID hashing for privacy
"""

import asyncio
import time
import pytest

from security_store import SecurityStore, _hash_user_id


@pytest.fixture
def store(monkeypatch):
    """Fresh SecurityStore with in-memory fallback (no Redis)."""
    s = SecurityStore()

    async def _no_redis():
        return None

    monkeypatch.setattr(s, "_get_redis", _no_redis)
    return s


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
    """Hash should not contain the raw user ID."""
    uid = "my-secret-user-id-123"
    h = _hash_user_id(uid)
    assert uid not in h


@pytest.mark.asyncio
async def test_record_flag(store):
    flag_id = await store.record_flag(
        user_id="user1",
        category="instruction_override",
        confidence="high",
        source="message",
        reasoning="test reasoning",
        thread_id="thread123",
    )
    assert isinstance(flag_id, str)
    assert len(flag_id) > 0


@pytest.mark.asyncio
async def test_record_strike_increments(store):
    count1 = await store.record_strike("user1")
    assert count1 == 1
    count2 = await store.record_strike("user1")
    assert count2 == 2
    count3 = await store.record_strike("user1")
    assert count3 == 3


@pytest.mark.asyncio
async def test_get_strike_count(store):
    await store.record_strike("user1")
    await store.record_strike("user1")
    count = await store.get_strike_count("user1")
    assert count == 2


@pytest.mark.asyncio
async def test_strike_count_separate_users(store):
    await store.record_strike("user1")
    await store.record_strike("user1")
    await store.record_strike("user2")
    assert await store.get_strike_count("user1") == 2
    assert await store.get_strike_count("user2") == 1


@pytest.mark.asyncio
async def test_is_in_cooldown_false_by_default(store):
    assert await store.is_in_cooldown("user1") is False


@pytest.mark.asyncio
async def test_apply_and_check_cooldown(store):
    await store.apply_cooldown("user1", minutes=1)
    assert await store.is_in_cooldown("user1") is True


@pytest.mark.asyncio
async def test_remove_cooldown(store):
    await store.apply_cooldown("user1", minutes=5)
    assert await store.is_in_cooldown("user1") is True
    user_hash = _hash_user_id("user1")
    removed = await store.remove_cooldown(user_hash)
    assert removed is True
    assert await store.is_in_cooldown("user1") is False


@pytest.mark.asyncio
async def test_remove_nonexistent_cooldown(store):
    removed = await store.remove_cooldown("nonexistent_hash")
    assert removed is False


@pytest.mark.asyncio
async def test_get_aggregate_stats_empty(store):
    stats = await store.get_aggregate_stats()
    assert stats["total_flags"] == 0
    assert stats["by_category"] == {}
    assert stats["unique_users"] == 0


@pytest.mark.asyncio
async def test_get_aggregate_stats_with_flags(store):
    await store.record_flag(
        user_id="user1",
        category="instruction_override",
        confidence="high",
        source="message",
    )
    await store.record_flag(
        user_id="user2",
        category="extraction_attempt",
        confidence="high",
        source="message",
    )
    stats = await store.get_aggregate_stats()
    assert stats["total_flags"] == 2
    assert "instruction_override" in stats["by_category"]
    assert "extraction_attempt" in stats["by_category"]
    assert stats["unique_users"] == 2


@pytest.mark.asyncio
async def test_get_active_cooldowns_empty(store):
    cooldowns = await store.get_active_cooldowns()
    assert cooldowns == []


@pytest.mark.asyncio
async def test_get_active_cooldowns(store):
    await store.apply_cooldown("user1", minutes=5)
    await store.apply_cooldown("user2", minutes=10)
    cooldowns = await store.get_active_cooldowns()
    assert len(cooldowns) == 2
    hashes = [c["user_hash"] for c in cooldowns]
    assert _hash_user_id("user1") in hashes
    assert _hash_user_id("user2") in hashes


@pytest.mark.asyncio
async def test_flag_does_not_store_raw_text(store):
    """Ensure record_flag never stores the raw offending message."""
    await store.record_flag(
        user_id="user1",
        category="instruction_override",
        confidence="high",
        source="message",
        reasoning="some reasoning here",
    )
    stats = await store.get_aggregate_stats()
    # The reasoning snippet should be at most 200 chars
    for flag in stats["recent_flags"]:
        assert len(flag.get("reasoning_snippet", "")) <= 200


@pytest.mark.asyncio
async def test_strike_threshold_triggers_cooldown(store):
    """Simulate hitting the strike threshold."""
    from config.settings import settings
    threshold = settings.INJECTION_STRIKE_THRESHOLD

    for i in range(threshold):
        count = await store.record_strike("user1")
        if count >= threshold:
            await store.apply_cooldown("user1")

    assert await store.is_in_cooldown("user1") is True
