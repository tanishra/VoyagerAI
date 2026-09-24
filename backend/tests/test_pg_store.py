"""Tests for pg_store: SQL translation, compat adapter, durable-tier fallback."""
from __future__ import annotations

import pytest

import pg_store


class TestTranslateSql:
    def test_insert_or_replace_pk_table(self):
        out = pg_store._translate_sql(
            "INSERT OR REPLACE INTO threads (thread_id, user_tag, summary) VALUES (?, ?, ?)"
        )
        assert out == (
            "INSERT INTO threads (thread_id, user_tag, summary) VALUES (%s, %s, %s) "
            "ON CONFLICT (thread_id) DO UPDATE SET user_tag = EXCLUDED.user_tag, "
            "summary = EXCLUDED.summary"
        )

    def test_insert_or_replace_no_pk_map(self):
        # Identity tables are not in _PK → plain insert, no conflict clause
        out = pg_store._translate_sql(
            "INSERT OR REPLACE INTO costs_subagent (thread_id, cost_usd) VALUES (?, ?)"
        )
        assert "ON CONFLICT" not in out
        assert "%s" in out and "?" not in out

    def test_composite_pk(self):
        out = pg_store._translate_sql(
            "INSERT OR REPLACE INTO rate_limits (key, timestamp) VALUES (?, ?)"
        )
        assert "ON CONFLICT (key, timestamp) DO NOTHING" in out

    def test_insert_or_ignore(self):
        out = pg_store._translate_sql(
            "INSERT OR IGNORE INTO research_cache (key, value) VALUES (?, ?)"
        )
        assert out.endswith("ON CONFLICT DO NOTHING")
        assert "%s" in out

    def test_select_delete_update(self):
        assert pg_store._translate_sql(
            "SELECT * FROM threads WHERE thread_id = ? AND user_tag = ? LIMIT ?"
        ) == "SELECT * FROM threads WHERE thread_id = %s AND user_tag = %s LIMIT %s"
        assert pg_store._translate_sql(
            "UPDATE threads SET pinned = ? WHERE thread_id = ?"
        ) == "UPDATE threads SET pinned = %s WHERE thread_id = %s"


class TestPgRow:
    def test_named_and_positional_access(self):
        row = pg_store._PgRow(["a", "b"], (1, "x"))
        assert row["a"] == 1
        assert row[0] == 1
        assert row[1] == "x"
        assert dict(row) == {"a": 1, "b": "x"}
        assert row.get("b") == "x"


class _FakeCursor:
    def __init__(self, rows=(), cols=(), rowcount=0):
        self._rows = list(rows)
        self.rowcount = rowcount
        self.description = [type("D", (), {"name": c}) for c in cols]

    async def fetchall(self):
        return self._rows


class _FakeConn:
    def __init__(self, cursor, recorder):
        self._cursor = cursor
        self._rec = recorder

    def cursor(self, row_factory=None):
        outer = self

        class _C:
            async def execute(self, sql, params):
                outer._rec.append((sql, params))
                return outer._cursor

        return _C()


class _FakePool:
    def __init__(self, cursor, recorder):
        self._conn = _FakeConn(cursor, recorder)

    def connection(self):
        conn = self._conn

        class _CM:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, *a):
                return False

        return _CM()


@pytest.mark.asyncio
async def test_pgcompat_execute_translates_and_fetches(monkeypatch):
    rec = []
    cur = _FakeCursor(rows=[(1, "delhi")], cols=["id", "name"], rowcount=1)
    monkeypatch.setattr(pg_store, "get_pg_pool",
                        lambda: _always(_FakePool(cur, rec)))
    db = pg_store.PgCompat()
    c = await db.execute("SELECT * FROM t WHERE id = ?", (1,))
    row = await c.fetchone()
    assert row["name"] == "delhi" and row[1] == "delhi"
    assert rec[0][0] == "SELECT * FROM t WHERE id = %s"
    assert rec[0][1] == (1,)
    assert c.rowcount == 1


async def _always(x):
    return x


@pytest.mark.asyncio
async def test_pgcompat_marks_broken_on_error(monkeypatch):
    class _BadConn:
        def cursor(self, row_factory=None):
            class _C:
                async def execute(self, sql, params):
                    raise RuntimeError("pg down")
            return _C()

    class _BadPool:
        def connection(self):
            class _CM:
                async def __aenter__(self):
                    return _BadConn()
                async def __aexit__(self, *a):
                    return False
            return _CM()

    monkeypatch.setattr(pg_store, "get_pg_pool", lambda: _always(_BadPool()))
    monkeypatch.setattr(pg_store, "_pg_broken_until", 0.0)
    db = pg_store.PgCompat()
    with pytest.raises(RuntimeError):
        await db.execute("SELECT 1")
    assert pg_store._pg_broken_until > 0


@pytest.mark.asyncio
async def test_get_durable_db_falls_back_to_sqlite(monkeypatch):
    async def _none():
        return None
    monkeypatch.setattr(pg_store, "get_pg_pool", _none)
    db = await pg_store.get_durable_db()
    # sqlite conn (or None if sqlite init also failed) — never a PgCompat
    assert not isinstance(db, pg_store.PgCompat)


@pytest.mark.asyncio
async def test_get_durable_db_prefers_pg(monkeypatch):
    monkeypatch.setattr(pg_store, "get_pg_pool", lambda: _always(object()))
    db = await pg_store.get_durable_db()
    assert isinstance(db, pg_store.PgCompat)


def test_conninfo_sslmode_for_supabase(monkeypatch):
    monkeypatch.setattr(pg_store.settings, "DATABASE_URL",
                        "postgresql://x@pooler.supabase.com:5432/postgres")
    assert "sslmode=require" in pg_store._conninfo()
    monkeypatch.setattr(pg_store.settings, "DATABASE_URL",
                        "postgresql://x@db.local/postgres")
    assert pg_store._conninfo().endswith("/postgres")
