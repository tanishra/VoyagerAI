"""Tests for visual generation tools (image + chart).

Covers Phase 6.28: image generation, chart generation, SSE events emitted.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from agents.tools.visuals import (
    generate_chart,
    generate_travel_image,
    get_pending_visual,
    is_visual_tool,
    set_current_thread_id,
)


class TestIsVisualTool:
    def test_generate_travel_image_is_visual(self):
        assert is_visual_tool("generate_travel_image") is True

    def test_generate_chart_is_visual(self):
        assert is_visual_tool("generate_chart") is True

    def test_non_visual_tool(self):
        assert is_visual_tool("internet_search") is False


class TestGenerateChart:
    """Tests for the generate_chart tool."""

    def test_bar_chart_valid(self):
        result = generate_chart.invoke({
            "chart_type": "bar",
            "title": "Cost Breakdown",
            "labels": ["Flights", "Hotels", "Food"],
            "series": {"Cost (USD)": [450, 800, 300]},
        })
        parsed = json.loads(result)
        assert parsed["type"] == "chart"
        assert parsed["chart_type"] == "bar"
        assert parsed["title"] == "Cost Breakdown"
        assert len(parsed["data"]) == 3
        assert parsed["data"][0] == {"label": "Flights", "Cost (USD)": 450}
        assert parsed["data"][2] == {"label": "Food", "Cost (USD)": 300}
        assert parsed["series_keys"] == ["Cost (USD)"]

    def test_pie_chart_valid(self):
        result = generate_chart.invoke({
            "chart_type": "pie",
            "title": "Budget Split",
            "labels": ["Transport", "Lodging", "Meals", "Activities"],
            "series": {"Amount": [200, 600, 150, 100]},
        })
        parsed = json.loads(result)
        assert parsed["chart_type"] == "pie"
        assert len(parsed["data"]) == 4
        assert parsed["data"][1] == {"label": "Lodging", "Amount": 600}

    def test_invalid_chart_type(self):
        # Pydantic validates Literal["bar", "pie"] before the function runs,
        # so we call the underlying function directly to test the guard.
        result = generate_chart.func(
            chart_type="line",
            title="Test",
            labels=["A"],
            series={"S": [1]},
        )
        assert "Invalid chart_type" in result

    def test_empty_labels(self):
        result = generate_chart.invoke({
            "chart_type": "bar",
            "title": "Test",
            "labels": [],
            "series": {},
        })
        assert "must include labels" in result

    def test_series_label_mismatch(self):
        result = generate_chart.invoke({
            "chart_type": "bar",
            "title": "Test",
            "labels": ["A", "B"],
            "series": {"S": [1]},
        })
        assert "1 values" in result
        assert "2 labels" in result

    def test_multiple_series(self):
        result = generate_chart.invoke({
            "chart_type": "bar",
            "title": "Comparison",
            "labels": ["Mon", "Tue", "Wed"],
            "series": {"Budget": [100, 120, 90], "Actual": [110, 100, 95]},
        })
        parsed = json.loads(result)
        assert len(parsed["data"]) == 3
        assert parsed["data"][0] == {"label": "Mon", "Budget": 100, "Actual": 110}
        assert parsed["series_keys"] == ["Budget", "Actual"]


class TestGenerateTravelImage:
    """Tests for the generate_travel_image tool (mocked Gemini API)."""

    def test_image_generation_disabled(self, monkeypatch):
        from agents.tools import visuals as visuals_module

        monkeypatch.setattr(visuals_module.settings, "ENABLE_IMAGE_GENERATION", False)
        result = asyncio_run(generate_travel_image.ainvoke({"prompt": "Kyoto temple"}))
        assert "disabled" in result

    def test_empty_prompt(self, monkeypatch):
        from agents.tools import visuals as visuals_module

        monkeypatch.setattr(visuals_module.settings, "ENABLE_IMAGE_GENERATION", True)
        result = asyncio_run(generate_travel_image.ainvoke({"prompt": ""}))
        assert "empty" in result

    def test_image_cap_reached(self, monkeypatch):
        from agents.tools import visuals as visuals_module

        monkeypatch.setattr(visuals_module.settings, "ENABLE_IMAGE_GENERATION", True)
        monkeypatch.setattr(visuals_module.settings, "MAX_IMAGES_PER_THREAD", 1)
        set_current_thread_id("test-cap-thread")
        visuals_module._image_counts["test-cap-thread"] = 1

        result = asyncio_run(generate_travel_image.ainvoke({"prompt": "test"}))
        assert "limit reached" in result

    def test_successful_image_generation(self, monkeypatch):
        from agents.tools import visuals as visuals_module

        monkeypatch.setattr(visuals_module.settings, "ENABLE_IMAGE_GENERATION", True)
        monkeypatch.setattr(visuals_module.settings, "MAX_IMAGES_PER_THREAD", 3)
        monkeypatch.setattr(visuals_module.settings, "GEMINI_API_KEY", "fake-key")
        monkeypatch.setattr(visuals_module.settings, "IMAGE_GENERATION_MODEL", "gemini-2.0-flash-exp")
        set_current_thread_id("test-success-thread")
        visuals_module._image_counts["test-success-thread"] = 0
        visuals_module._pending_visuals.clear()

        fake_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

        mock_response = MagicMock()
        mock_part = MagicMock()
        mock_part.inline_data.data = fake_bytes
        mock_candidate = MagicMock()
        mock_candidate.content.parts = [mock_part]
        mock_response.candidates = [mock_candidate]

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with patch("google.genai.Client", return_value=mock_client):
            result = asyncio_run(generate_travel_image.ainvoke({
                "prompt": "Beautiful Kyoto temple at sunset",
                "alt_text": "Kyoto temple",
            }))

        parsed = json.loads(result)
        assert parsed["type"] == "image"
        assert parsed["alt"] == "Kyoto temple"
        assert "_visual_id" in parsed
        assert parsed["remaining"] == 2

        visual_data = get_pending_visual(parsed["_visual_id"])
        assert visual_data is not None
        assert visual_data["type"] == "image"
        assert visual_data["alt"] == "Kyoto temple"
        assert visual_data["data_url"].startswith("data:image/png;base64,")
        assert visual_data["prompt"] == "Beautiful Kyoto temple at sunset"

    def test_gemini_returns_no_image(self, monkeypatch):
        from agents.tools import visuals as visuals_module

        monkeypatch.setattr(visuals_module.settings, "ENABLE_IMAGE_GENERATION", True)
        monkeypatch.setattr(visuals_module.settings, "MAX_IMAGES_PER_THREAD", 3)
        monkeypatch.setattr(visuals_module.settings, "GEMINI_API_KEY", "fake-key")
        monkeypatch.setattr(visuals_module.settings, "IMAGE_GENERATION_MODEL", "gemini-2.0-flash-exp")
        set_current_thread_id("test-noimg-thread")
        visuals_module._image_counts["test-noimg-thread"] = 0

        mock_response = MagicMock()
        mock_candidate = MagicMock()
        mock_candidate.content = None
        mock_response.candidates = [mock_candidate]

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with patch("google.genai.Client", return_value=mock_client):
            result = asyncio_run(generate_travel_image.ainvoke({
                "prompt": "test prompt",
            }))

        assert "no image data" in result

    def test_gemini_exception_handled(self, monkeypatch):
        from agents.tools import visuals as visuals_module

        monkeypatch.setattr(visuals_module.settings, "ENABLE_IMAGE_GENERATION", True)
        monkeypatch.setattr(visuals_module.settings, "MAX_IMAGES_PER_THREAD", 3)
        monkeypatch.setattr(visuals_module.settings, "GEMINI_API_KEY", "fake-key")
        monkeypatch.setattr(visuals_module.settings, "IMAGE_GENERATION_MODEL", "gemini-2.0-flash-exp")
        set_current_thread_id("test-exc-thread")
        visuals_module._image_counts["test-exc-thread"] = 0

        with patch("google.genai.Client", side_effect=RuntimeError("API down")):
            result = asyncio_run(generate_travel_image.ainvoke({
                "prompt": "test prompt",
            }))

        assert "Image generation failed" in result


class TestPendingVisuals:
    def test_get_pending_visual_returns_none_for_unknown(self):
        assert get_pending_visual("nonexistent-id") is None

    def test_get_pending_visual_returns_and_removes(self):
        from agents.tools import visuals as visuals_module

        visuals_module._pending_visuals["test-id"] = {"type": "image", "data_url": "x"}
        result = get_pending_visual("test-id")
        assert result == {"type": "image", "data_url": "x"}
        assert "test-id" not in visuals_module._pending_visuals


def asyncio_run(coro):
    import asyncio

    return asyncio.run(coro)
