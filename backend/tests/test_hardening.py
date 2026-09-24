"""Production hardening tests — A2/A3/A4/A5/A6/A7 + api_key query-param warn."""
from __future__ import annotations

import pytest

import agents.deep_agent as da
import main as main_module


# --- A6: resilient PG wrappers ----------------------------------------------

class TestResilientSaver:
    def _make(self, monkeypatch):
        import psycopg  # noqa: F401 — ensure dep present
        cls = da._resilient_saver_class()
        saver = cls.__new__(cls)
        saver._conninfo = "postgresql://x"
        reconnects = []

        class _FakeConn:
            async def close(self):
                pass

        saver.conn = _FakeConn()

        async def _fake_connect(conninfo):
            reconnects.append(conninfo)
            return _FakeConn()

        monkeypatch.setattr(da, "_pg_async_connect", _fake_connect)
        return saver, reconnects

    @pytest.mark.asyncio
    async def test_retry_reconnects_once(self, monkeypatch):
        import psycopg
        saver, reconnects = self._make(monkeypatch)
        calls = []

        async def flaky(cfg):
            calls.append(1)
            if len(calls) == 1:
                raise psycopg.OperationalError("connection is dead")
            return "ok"

        out = await saver._retry(flaky, {"config": 1})
        assert out == "ok"
        assert len(reconnects) == 1

    @pytest.mark.asyncio
    async def test_second_failure_propagates(self, monkeypatch):
        import psycopg
        saver, reconnects = self._make(monkeypatch)

        async def always_dead(cfg):
            raise psycopg.OperationalError("dead")

        with pytest.raises(psycopg.OperationalError):
            await saver._retry(always_dead, {})
        assert len(reconnects) == 1

    @pytest.mark.asyncio
    async def test_non_conn_error_no_reconnect(self, monkeypatch):
        saver, reconnects = self._make(monkeypatch)

        async def value_err(cfg):
            raise ValueError("bad arg")

        with pytest.raises(ValueError):
            await saver._retry(value_err, {})
        assert reconnects == []

    @pytest.mark.asyncio
    async def test_alist_retries_initial_pull(self, monkeypatch):
        import psycopg
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        saver, reconnects = self._make(monkeypatch)
        calls = []

        async def fake_alist(self, config, *a, **kw):
            calls.append(1)
            if len(calls) == 1:
                raise psycopg.OperationalError("dead")
                yield  # pragma: no cover
            yield "cp1"
            yield "cp2"

        monkeypatch.setattr(AsyncPostgresSaver, "alist", fake_alist)
        items = [i async for i in saver.alist({"config": 1})]
        assert items == ["cp1", "cp2"]
        assert len(reconnects) == 1


class TestResilientStore:
    def _make(self):
        cls = da._resilient_store_class()
        store = cls.__new__(cls)
        store._conninfo = "postgresql://x"
        import threading
        store._conn_lock = threading.Lock()

        class _FakeConn:
            def close(self):
                pass

        store.conn = _FakeConn()
        return store

    def test_batch_retries_once(self, monkeypatch):
        import psycopg
        from langgraph.store.postgres import PostgresStore
        store = self._make()
        reconnects = []
        monkeypatch.setattr(store, "_reconnect", lambda: reconnects.append(1))
        calls = []

        def flaky(self, ops):
            calls.append(1)
            if len(calls) == 1:
                raise psycopg.OperationalError("dead")
            return ["ok"]

        monkeypatch.setattr(PostgresStore, "batch", flaky)
        assert store.batch(["op"]) == ["ok"]
        assert len(reconnects) == 1


# --- A3: attachment resolution ----------------------------------------------

class TestResolveAttachments:
    @pytest.mark.asyncio
    async def test_file_id_resolves_stored_bytes(self, monkeypatch):
        from file_store import FileMeta

        async def _get(user_id, file_id):
            return FileMeta(
                file_id=file_id, filename="doc.pdf", content_type="application/pdf",
                size=10, data="QUJD", created_at=0.0,
            )

        monkeypatch.setattr(main_module.file_store, "get", _get)
        out = await main_module._resolve_attachments("u1", [{
            "file_id": "f1", "filename": "doc.pdf", "content_type": "application/pdf",
            "data_url": "data:application/pdf;base64,FORGED",
        }])
        assert out[0]["data_url"] == "data:application/pdf;base64,QUJD"

    @pytest.mark.asyncio
    async def test_malformed_data_url_dropped(self, monkeypatch):
        async def _none(user_id, file_id):
            return None
        monkeypatch.setattr(main_module.file_store, "get", _none)
        out = await main_module._resolve_attachments("u1", [{
            "file_id": "gone", "filename": "x.png", "content_type": "image/png",
            "data_url": "javascript:alert(1)",
        }])
        assert out == []

    @pytest.mark.asyncio
    async def test_valid_legacy_data_url_accepted(self, monkeypatch):
        async def _none(user_id, file_id):
            return None
        monkeypatch.setattr(main_module.file_store, "get", _none)
        out = await main_module._resolve_attachments("u1", [{
            "file_id": "expired", "filename": "p.png", "content_type": "image/png",
            "data_url": "data:image/png;base64,aGVsbG8=",
        }])
        assert len(out) == 1


# --- A3 model caps -----------------------------------------------------------

def test_attachments_count_cap():
    from models import AttachmentInfo, ChatRequest
    atts = [
        AttachmentInfo(file_id=f"f{i}", filename="a.png",
                       content_type="image/png", data_url="data:image/png;base64,x")
        for i in range(6)
    ]
    with pytest.raises(Exception):
        ChatRequest(message="hi", attachments=atts)


def test_attachment_data_url_optional_and_capped():
    from models import AttachmentInfo
    # data_url now optional (frontend strips it; server resolves via file_id)
    a = AttachmentInfo(file_id="f1", filename="a.png", content_type="image/png")
    assert a.data_url is None
    with pytest.raises(Exception):
        AttachmentInfo(file_id="f1", filename="a.png", content_type="image/png",
                       data_url="x" * 14_000_001)


# --- A5: /metrics auth gate --------------------------------------------------

class TestMetricsAuth:
    def test_metrics_open_in_dev(self, client):
        assert client.get("/metrics").status_code == 200

    def test_metrics_requires_key_in_prod(self, monkeypatch, client):
        import auth
        monkeypatch.setattr(auth, "AUTH_MODE", "production")
        monkeypatch.setattr(auth, "API_AUTH_KEY", "secret-key")
        assert client.get("/metrics").status_code == 401
        assert client.get("/metrics", headers={"X-API-Key": "secret-key"}).status_code == 200


# --- A7: body size caps -------------------------------------------------------

class TestBodyCaps:
    def test_oversized_content_length_rejected(self, authed_client):
        resp = authed_client.post(
            "/chat/edit",
            content=b"{}",
            headers={
                "X-CSRF-Token": "test-csrf-token",
                "Content-Type": "application/json",
                "Content-Length": str(3 * 1024 * 1024),
            },
        )
        assert resp.status_code == 413


# --- #9: api_key query-param fallback ----------------------------------------

class TestApiKeyFallback:
    @pytest.mark.asyncio
    async def test_query_param_warns_but_authenticates(self, monkeypatch, caplog):
        import auth
        from unittest.mock import MagicMock
        monkeypatch.setattr(auth, "AUTH_MODE", "production")
        monkeypatch.setattr(auth, "API_AUTH_KEY", "secret-key")
        req = MagicMock()
        req.headers = {}
        req.query_params = {"api_key": "secret-key"}
        req.client = MagicMock(host="1.2.3.4")
        with caplog.at_level("WARNING", logger="auth"):
            out = await auth.verify_api_key(req, x_api_key=None)
        assert out == "secret-key"
        assert "query-param" in caplog.text

    @pytest.mark.asyncio
    async def test_header_preferred_no_warning(self, monkeypatch, caplog):
        import auth
        from unittest.mock import MagicMock
        monkeypatch.setattr(auth, "AUTH_MODE", "production")
        monkeypatch.setattr(auth, "API_AUTH_KEY", "secret-key")
        req = MagicMock()
        req.query_params = {}
        with caplog.at_level("WARNING", logger="auth"):
            out = await auth.verify_api_key(req, x_api_key="secret-key")
        assert out == "secret-key"
        assert "query-param" not in caplog.text


# --- /ready readiness probe ---------------------------------------------------

class TestReady:
    def test_ready_returns_tier_statuses(self, client):
        resp = client.get("/ready")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] in ("ok", "degraded")
        for tier in ("redis", "postgres", "sqlite"):
            assert tier in body

    def test_ready_postgres_disabled_without_database_url(self, client, monkeypatch):
        monkeypatch.setattr(main_module.settings, "DATABASE_URL", "")
        body = client.get("/ready").json()
        assert body["postgres"] == "disabled"


# --- DATA_DIR resolution -------------------------------------------------------

class TestDataDir:
    def test_data_dir_rewrites_default_paths(self):
        from config.settings import Settings
        s = Settings(DATA_DIR="/tmp/voy-data-test",
                     CHECKPOINTER_DB_PATH="./data/checkpoints.sqlite",
                     SQLITE_FALLBACK_DB_PATH="./data/stores.sqlite")
        assert s.CHECKPOINTER_DB_PATH == "/tmp/voy-data-test/checkpoints.sqlite"
        assert s.SQLITE_FALLBACK_DB_PATH == "/tmp/voy-data-test/stores.sqlite"

    def test_explicit_path_not_rewritten(self):
        from config.settings import Settings
        s = Settings(DATA_DIR="/tmp/voy-data-test", CHECKPOINTER_DB_PATH="/custom/cp.sqlite")
        assert s.CHECKPOINTER_DB_PATH == "/custom/cp.sqlite"


# --- structured errors ----------------------------------------------------------

def test_err_produces_structured_detail():
    exc = main_module._err(404, "thread_not_found", "nope")
    assert exc.status_code == 404
    assert exc.detail == {"code": "thread_not_found", "message": "nope"}
