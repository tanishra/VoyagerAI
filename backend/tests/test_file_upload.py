"""Tests for file upload, FileStore, and PDF processing.

Uses in-memory FileStore (no Redis required) and TestClient with mocked
stream_chat_agent — same pattern as test_threads.py.
"""

from __future__ import annotations

import base64
import io
from unittest.mock import patch, AsyncMock

import pytest
from fastapi.testclient import TestClient

from file_store import FileStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fresh_file_store():
    """A FileStore with no Redis connection — uses in-memory fallback."""
    store = FileStore()
    store._redis = None
    return store


@pytest.fixture
def client(fresh_file_store, monkeypatch):
    """TestClient with the file_store patched to use in-memory."""
    import main as main_module

    monkeypatch.setattr("config.settings.AUTH_DEV_BYPASS", True)
    with (
        patch.object(main_module, "file_store", fresh_file_store),
        patch.object(main_module, "stream_chat_agent", _fake_stream),
        TestClient(main_module.app) as c,
    ):
        # Establish dev-bypass session
        c.get("/auth/login", follow_redirects=False)
        yield c


async def _fake_stream(message, thread_id, user_id=None, locale=None, timezone=None, cancel_event=None, attachments=None):
    yield {"event": "done", "data": None}


# ---------------------------------------------------------------------------
# TestFileStore — unit tests for the store
# ---------------------------------------------------------------------------


class TestFileStore:
    @pytest.mark.asyncio
    async def test_upload_and_get(self, fresh_file_store):
        result = await fresh_file_store.upload("user1", "test.jpg", "image/jpeg", b"\xff\xd8\xff\xe0")
        assert result["file_id"]
        assert result["data_url"].startswith("data:image/jpeg;base64,")
        assert result["filename"] == "test.jpg"
        assert result["size"] == 4

        meta = await fresh_file_store.get("user1", result["file_id"])
        assert meta is not None
        assert meta.filename == "test.jpg"
        assert meta.content_type == "image/jpeg"
        assert meta.size == 4

    @pytest.mark.asyncio
    async def test_delete(self, fresh_file_store):
        result = await fresh_file_store.upload("user1", "test.png", "image/png", b"\x89PNG")
        deleted = await fresh_file_store.delete("user1", result["file_id"])
        assert deleted is True

        meta = await fresh_file_store.get("user1", result["file_id"])
        assert meta is None

    @pytest.mark.asyncio
    async def test_cross_user_isolation(self, fresh_file_store):
        result = await fresh_file_store.upload("userA", "secret.jpg", "image/jpeg", b"data")
        meta = await fresh_file_store.get("userB", result["file_id"])
        assert meta is None


# ---------------------------------------------------------------------------
# TestUploadEndpoint — tests for POST /upload
# ---------------------------------------------------------------------------


class TestUploadEndpoint:
    def test_upload_image(self, client):
        resp = client.post(
            "/upload",
            files={"file": ("test.jpg", b"\xff\xd8\xff\xe0\x00\x10", "image/jpeg")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "file_id" in data
        assert "data_url" in data
        assert data["filename"] == "test.jpg"
        assert data["content_type"] == "image/jpeg"

    def test_upload_pdf(self, client):
        resp = client.post(
            "/upload",
            files={"file": ("doc.pdf", b"%PDF-1.4 test", "application/pdf")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["content_type"] == "application/pdf"

    def test_upload_oversized(self, client):
        big_data = b"\x00" * (10 * 1024 * 1024 + 1)
        resp = client.post(
            "/upload",
            files={"file": ("big.jpg", big_data, "image/jpeg")},
        )
        assert resp.status_code == 413

    def test_upload_unsupported_type(self, client):
        resp = client.post(
            "/upload",
            files={"file": ("test.txt", b"hello", "text/plain")},
        )
        assert resp.status_code == 415


# ---------------------------------------------------------------------------
# TestPDFProcessing — unit tests for PDF helpers
# ---------------------------------------------------------------------------


class TestPDFProcessing:
    def test_extract_pdf_text_with_text_pdf(self):
        """Test that text extraction works for a text-based PDF."""
        import fitz

        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 72), "Hello World! This is a test PDF with some text content.")
        pdf_bytes = doc.tobytes()
        doc.close()

        b64 = base64.b64encode(pdf_bytes).decode()
        data_url = f"data:application/pdf;base64,{b64}"

        from agents.deep_agent import extract_pdf_text
        text = extract_pdf_text(data_url)
        assert "Hello World" in text
        assert len(text.strip()) > 50

    def test_extract_pdf_text_empty_pdf(self):
        """Test that text extraction returns empty for a PDF with no text."""
        import fitz

        doc = fitz.open()
        doc.new_page()  # blank page, no text
        pdf_bytes = doc.tobytes()
        doc.close()

        b64 = base64.b64encode(pdf_bytes).decode()
        data_url = f"data:application/pdf;base64,{b64}"

        from agents.deep_agent import extract_pdf_text
        text = extract_pdf_text(data_url)
        assert text.strip() == ""

    def test_render_pdf_pages_as_images(self):
        """Test that page rendering returns base64 PNG data URLs."""
        import fitz

        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 72), "Page 1")
        pdf_bytes = doc.tobytes()
        doc.close()

        b64 = base64.b64encode(pdf_bytes).decode()
        data_url = f"data:application/pdf;base64,{b64}"

        from agents.deep_agent import render_pdf_pages_as_images
        images = render_pdf_pages_as_images(data_url, max_pages=10)
        assert len(images) == 1
        assert images[0].startswith("data:image/png;base64,")

    def test_render_multipage_pdf(self):
        """Test that multi-page PDFs produce one image per page."""
        import fitz

        doc = fitz.open()
        for i in range(3):
            page = doc.new_page()
            page.insert_text((50, 72), f"Page {i+1}")
        pdf_bytes = doc.tobytes()
        doc.close()

        b64 = base64.b64encode(pdf_bytes).decode()
        data_url = f"data:application/pdf;base64,{b64}"

        from agents.deep_agent import render_pdf_pages_as_images
        images = render_pdf_pages_as_images(data_url, max_pages=10)
        assert len(images) == 3

    def test_render_pdf_max_pages_cap(self):
        """Test that page rendering respects max_pages limit."""
        import fitz

        doc = fitz.open()
        for i in range(15):
            doc.new_page()
        pdf_bytes = doc.tobytes()
        doc.close()

        b64 = base64.b64encode(pdf_bytes).decode()
        data_url = f"data:application/pdf;base64,{b64}"

        from agents.deep_agent import render_pdf_pages_as_images
        images = render_pdf_pages_as_images(data_url, max_pages=10)
        assert len(images) == 10


# ---------------------------------------------------------------------------
# TestChatStreamWithAttachments — tests for chat stream with attachments
# ---------------------------------------------------------------------------


class TestChatStreamWithAttachments:
    def test_chat_stream_with_image_attachment(self, client):
        """Test that chat stream accepts image attachments."""
        # First upload a file
        upload_resp = client.post(
            "/upload",
            files={"file": ("test.jpg", b"\xff\xd8\xff\xe0\x00\x10", "image/jpeg")},
        )
        assert upload_resp.status_code == 200
        att = upload_resp.json()

        # Now send a chat message with the attachment
        resp = client.post(
            "/chat/stream",
            json={
                "message": "What's in this image?",
                "attachments": [att],
            },
        )
        assert resp.status_code == 200

    def test_chat_stream_with_pdf_attachment(self, client):
        """Test that chat stream accepts PDF attachments."""
        # Create a minimal text PDF
        import fitz
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 72), "This is a test PDF with enough text content to pass the threshold check for text extraction.")
        pdf_bytes = doc.tobytes()
        doc.close()

        upload_resp = client.post(
            "/upload",
            files={"file": ("doc.pdf", pdf_bytes, "application/pdf")},
        )
        assert upload_resp.status_code == 200
        att = upload_resp.json()

        resp = client.post(
            "/chat/stream",
            json={
                "message": "Summarize this PDF",
                "attachments": [att],
            },
        )
        assert resp.status_code == 200

    def test_chat_stream_without_attachments_still_works(self, client):
        """Test that chat stream without attachments still works (backward compat)."""
        resp = client.post(
            "/chat/stream",
            json={"message": "Hello"},
        )
        assert resp.status_code == 200
