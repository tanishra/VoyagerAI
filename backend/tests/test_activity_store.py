"""Tests for activity_store persistence (including images/charts).

Covers Phase 6.28: images and charts must persist across page refresh.
"""

from __future__ import annotations

import asyncio

import pytest
from langgraph.store.memory import InMemoryStore

from agents.activity_store import save_activity, load_activity, load_all_activity


class _StoreItem:
    def __init__(self, value):
        self.value = value


class FakeStore:
    """Minimal async store for testing."""

    def __init__(self):
        self.data: dict[tuple, dict] = {}

    async def aget(self, namespace, key):
        full_key = (namespace, key)
        if full_key in self.data:
            return _StoreItem(self.data[full_key])
        return None

    async def aput(self, namespace, key, value):
        self.data[(namespace, key)] = value


class TestSaveActivityPerMessage:
    def test_save_with_images_and_charts(self):
        store = FakeStore()
        activity = {
            "thinking": [{"text": "Planning..."}],
            "tool_calls": [{"name": "search", "status": "done"}],
            "usage": [{"input_tokens": 100, "output_tokens": 50}],
            "total_input_tokens": 100,
            "total_output_tokens": 50,
            "images": [{"type": "image", "data_url": "data:image/png;base64,abc", "alt": "Kyoto"}],
            "charts": [{"type": "chart", "chart_type": "bar", "title": "Costs", "data": [], "series_keys": []}],
        }

        asyncio.run(save_activity(store, "thread-1", activity, message_index=0))

        loaded = asyncio.run(load_activity(store, "thread-1", message_index=0))
        assert loaded is not None
        assert loaded["images"] == activity["images"]
        assert loaded["charts"] == activity["charts"]
        assert loaded["thinking"] == activity["thinking"]
        assert loaded["tool_calls"] == activity["tool_calls"]
        assert loaded["total_input_tokens"] == 100

    def test_save_multiple_messages(self):
        store = FakeStore()

        activity_0 = {
            "thinking": [], "tool_calls": [], "usage": [],
            "total_input_tokens": 0, "total_output_tokens": 0,
            "images": [{"type": "image", "data_url": "img1"}],
            "charts": [],
        }
        activity_1 = {
            "thinking": [], "tool_calls": [], "usage": [],
            "total_input_tokens": 0, "total_output_tokens": 0,
            "images": [],
            "charts": [{"type": "chart", "chart_type": "pie", "title": "Budget", "data": [], "series_keys": []}],
        }

        asyncio.run(save_activity(store, "thread-1", activity_0, message_index=0))
        asyncio.run(save_activity(store, "thread-1", activity_1, message_index=1))

        all_activity = asyncio.run(load_all_activity(store, "thread-1"))
        assert all_activity is not None
        assert len(all_activity) == 2
        assert all_activity["0"]["images"] == [{"type": "image", "data_url": "img1"}]
        assert all_activity["0"]["charts"] == []
        assert all_activity["1"]["images"] == []
        assert all_activity["1"]["charts"][0]["title"] == "Budget"

    def test_save_without_images_charts_defaults_to_empty(self):
        store = FakeStore()
        activity = {
            "thinking": [], "tool_calls": [], "usage": [],
            "total_input_tokens": 0, "total_output_tokens": 0,
        }

        asyncio.run(save_activity(store, "thread-1", activity, message_index=0))

        loaded = asyncio.run(load_activity(store, "thread-1", message_index=0))
        assert loaded is not None
        assert loaded["images"] == []
        assert loaded["charts"] == []

    def test_save_preserves_existing_messages(self):
        store = FakeStore()

        activity_0 = {
            "thinking": [], "tool_calls": [], "usage": [],
            "total_input_tokens": 0, "total_output_tokens": 0,
            "images": [{"type": "image", "data_url": "img0"}],
            "charts": [],
        }
        asyncio.run(save_activity(store, "thread-1", activity_0, message_index=0))

        activity_1 = {
            "thinking": [], "tool_calls": [], "usage": [],
            "total_input_tokens": 0, "total_output_tokens": 0,
            "images": [],
            "charts": [],
        }
        asyncio.run(save_activity(store, "thread-1", activity_1, message_index=1))

        loaded_0 = asyncio.run(load_activity(store, "thread-1", message_index=0))
        assert loaded_0["images"] == [{"type": "image", "data_url": "img0"}]


class TestSaveActivityLegacy:
    def test_legacy_save_with_images_and_charts(self):
        store = FakeStore()
        activity = {
            "thinking": [], "tool_calls": [], "usage": [],
            "total_input_tokens": 10, "total_output_tokens": 5,
            "images": [{"type": "image", "data_url": "legacy-img"}],
            "charts": [{"type": "chart", "chart_type": "bar", "title": "Legacy", "data": [], "series_keys": []}],
        }

        asyncio.run(save_activity(store, "thread-1", activity))

        loaded = asyncio.run(load_activity(store, "thread-1"))
        assert loaded is not None
        assert loaded["images"] == [{"type": "image", "data_url": "legacy-img"}]
        assert loaded["charts"][0]["title"] == "Legacy"

    def test_legacy_save_without_images_charts(self):
        store = FakeStore()
        activity = {
            "thinking": [], "tool_calls": [], "usage": [],
            "total_input_tokens": 0, "total_output_tokens": 0,
        }

        asyncio.run(save_activity(store, "thread-1", activity))

        loaded = asyncio.run(load_activity(store, "thread-1"))
        assert loaded is not None
        assert loaded["images"] == []
        assert loaded["charts"] == []


class TestLoadActivity:
    def test_load_nonexistent_thread(self):
        store = FakeStore()
        result = asyncio.run(load_activity(store, "no-such-thread", message_index=0))
        assert result is None

    def test_load_all_nonexistent_thread(self):
        store = FakeStore()
        result = asyncio.run(load_all_activity(store, "no-such-thread"))
        assert result is None

    def test_load_nonexistent_message_index(self):
        store = FakeStore()
        activity = {
            "thinking": [], "tool_calls": [], "usage": [],
            "total_input_tokens": 0, "total_output_tokens": 0,
            "images": [], "charts": [],
        }
        asyncio.run(save_activity(store, "thread-1", activity, message_index=0))

        result = asyncio.run(load_activity(store, "thread-1", message_index=99))
        assert result is None
