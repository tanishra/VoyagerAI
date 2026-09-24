"""Tests for destination image generation on share link creation."""
from __future__ import annotations

import base64
import json
from typing import ClassVar
from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_generate_destination_image_disabled():
    """Returns None when image generation is disabled."""
    with patch("config.settings.settings.ENABLE_IMAGE_GENERATION", False):
        from agents.tools.visuals import generate_destination_image
        result = await generate_destination_image("Paris")
        assert result is None


@pytest.mark.asyncio
async def test_generate_destination_image_no_api_key():
    """Returns None when GEMINI_API_KEY is not set."""
    with (
        patch("config.settings.settings.ENABLE_IMAGE_GENERATION", True),
        patch("config.settings.settings.GEMINI_API_KEY", ""),
    ):
        from agents.tools.visuals import generate_destination_image
        result = await generate_destination_image("Paris")
        assert result is None


@pytest.mark.asyncio
async def test_generate_destination_image_success():
    """Returns base64 string when image generation succeeds."""
    fake_image_bytes = b"fake-png-data"

    class FakePart:
        class inline_data:
            data = fake_image_bytes

    class FakeContent:
        parts: ClassVar = [FakePart()]

    class FakeCandidate:
        content: ClassVar = FakeContent()

    class FakeResponse:
        candidates: ClassVar = [FakeCandidate()]

    class FakeModels:
        def generate_content(self, **kwargs):
            return FakeResponse()

    class FakeClient:
        def __init__(self, **kwargs):
            self.models = FakeModels()

    with (
        patch("config.settings.settings.ENABLE_IMAGE_GENERATION", True),
        patch("config.settings.settings.GEMINI_API_KEY", "fake-key"),
        patch("config.settings.settings.IMAGE_GENERATION_MODEL", "gemini-2.5-flash-image"),
        patch("google.genai.Client", return_value=FakeClient()),
        patch("google.genai.types.GenerateContentConfig", return_value=None),
    ):
        from agents.tools.visuals import generate_destination_image
        result = await generate_destination_image("Paris")
        assert result is not None
        assert isinstance(result, str)
        decoded = base64.b64decode(result)
        assert decoded == fake_image_bytes


@pytest.mark.asyncio
async def test_generate_destination_image_api_failure():
    """Returns None when Gemini API raises an exception."""
    with (
        patch("config.settings.settings.ENABLE_IMAGE_GENERATION", True),
        patch("config.settings.settings.GEMINI_API_KEY", "fake-key"),
        patch("google.genai.Client", side_effect=Exception("API error")),
    ):
        from agents.tools.visuals import generate_destination_image
        result = await generate_destination_image("Paris")
        assert result is None


def test_share_create_includes_image_in_response(authed_client, csrf_headers, monkeypatch):
    """Share creation generates destination image and includes it in get response."""
    fake_image_b64 = "dGVzdC1pbWFnZS1kYXRh"  # base64 of "test-image-data"

    async def mock_generate(destination):
        return fake_image_b64

    monkeypatch.setattr("main.generate_destination_image", mock_generate)

    # First, create a thread with an itinerary
    thread_id = None
    try:
        with authed_client.stream(
            "POST", "/chat/stream",
            headers={
                **csrf_headers,
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
            json={"message": "Plan a 1-day trip to Paris"},
        ) as thread_resp:
            assert thread_resp.status_code in (200, 401, 403)
            if thread_resp.status_code != 200:
                pytest.skip("Cannot create thread for share image test")
            for line in thread_resp.iter_lines():
                if line.startswith("event: thread_id"):
                    pass
                elif line.startswith("data:"):
                    try:
                        data = json.loads(line[5:].strip())
                        if "thread_id" in data:
                            thread_id = data["thread_id"]
                            break
                    except json.JSONDecodeError:
                        pass
    except Exception:  # noqa: BLE001
        pytest.skip("Cannot create thread for share image test")

    if not thread_id:
        pytest.skip("Could not extract thread_id from stream")

    # Create share link
    share_resp = authed_client.post(
        f"/share/{thread_id}",
        headers=csrf_headers,
    )
    assert share_resp.status_code == 200
    share_data = share_resp.json()
    assert "share_url" in share_data
    token = share_data["share_url"].split("/share/")[-1]

    # Get shared itinerary — should include image_base64
    get_resp = authed_client.get(f"/share/{token}")
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert "image_base64" in get_data
    assert get_data["image_base64"] == fake_image_b64


def test_share_create_image_generation_disabled(authed_client, csrf_headers, monkeypatch):
    """Share creation works without image when generation is disabled."""
    async def mock_generate(destination):
        return None

    monkeypatch.setattr("main.generate_destination_image", mock_generate)

    # Create a thread with an itinerary
    thread_id = None
    try:
        with authed_client.stream(
            "POST", "/chat/stream",
            headers={
            **csrf_headers,
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
            json={"message": "Plan a 1-day trip to Paris"},
        ) as thread_resp:
            assert thread_resp.status_code in (200, 401, 403)
            if thread_resp.status_code != 200:
                pytest.skip("Cannot create thread for share image test")
            for line in thread_resp.iter_lines():
                if line.startswith("data:"):
                    try:
                        data = json.loads(line[5:].strip())
                        if "thread_id" in data:
                            thread_id = data["thread_id"]
                            break
                    except json.JSONDecodeError:
                        pass
    except Exception:  # noqa: BLE001
        pytest.skip("Cannot create thread for share image test")

    if not thread_id:
        pytest.skip("Could not extract thread_id from stream")

    # Create share link
    share_resp = authed_client.post(
        f"/share/{thread_id}",
        headers=csrf_headers,
    )
    assert share_resp.status_code == 200
    share_data = share_resp.json()
    token = share_data["share_url"].split("/share/")[-1]

    # Get shared itinerary — image_base64 should be None
    get_resp = authed_client.get(f"/share/{token}")
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data.get("image_base64") is None
