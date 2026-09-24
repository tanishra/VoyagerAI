<!-- OPENWIKI:START -->

## OpenWiki

This repository has a generated `openwiki/` evidence index. It is optional just-in-time context, not required startup reading.

- Treat source code and tests as authoritative. A brief's unknowns and review items are verification gaps, not automatic requirements.
- Prefer the narrowest quiet validation that proves the changed behavior. Preserve complete failure output.

The scheduled OpenWiki GitHub Actions workflow refreshes the repository wiki. Do not hand-edit generated OpenWiki pages unless explicitly asked; prefer updating source code/docs and letting OpenWiki regenerate.

<!-- OPENWIKI:END -->

## Backend architecture notes

- Trip-plan generation runs through the deterministic pipeline in
  `backend/agents/pipeline.py`. The orchestrator calls `generate_trip_plans`
  (3-tier comparison summaries) and `refine_itinerary` (full day-by-day after
  tier selection). Plan JSON is never written by the model — payloads travel
  a side channel (`backend/payload_store.py`: Redis + TTL, bounded in-memory
  fallback) and are emitted as SSE `comparison`/`itinerary` events.
- `<itinerary>`/`<comparison>` tag extraction in `deep_agent.py` is kept only
  as the legacy reader so pre-pipeline saved conversations still render.
- Only the `researcher` subagent is dispatchable via the task tool.
- Storage split: **Postgres is the durable tier** (`DATABASE_URL`, Supabase),
  **Upstash Redis is hot/TTL-only** (payloads, rate limits, research/geocode
  caches). `backend/pg_store.py` owns the shared pool, schema DDL, and
  `get_durable_db()` — a drop-in for `get_sqlite_connection()` that returns a
  `PgCompat` (translates the stores' SQLite dialect) when PG is up and the
  aiosqlite conn otherwise. Durable stores (threads, costs, shares, feedback,
  security, observability, oauth sessions, files) write Redis-as-cache +
  durable tier and merge on read; SQLite remains the disaster tier.
- `CHECKPOINTER_BACKEND=postgres` uses `AsyncPostgresSaver`; `STORE_BACKEND=
  postgres` uses LangGraph `PostgresStore` for activity/file memory. Empty
  `DATABASE_URL` or a PG outage degrades to SQLite/memory with warnings —
  nothing hard-fails. Upstash Redis lacks RediSearch, so `CHECKPOINTER_
  BACKEND=redis` still falls back to SQLite.
- Live verification: `cd backend && python tests/e2e_hybrid_live.py`
  (real OpenAI/Tavily/Redis calls — costs money, not part of pytest).
