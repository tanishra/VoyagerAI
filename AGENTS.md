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
- Upstash Redis lacks RediSearch (`FT.*`), so the LangGraph checkpointer
  falls back to SQLite and semantic memory falls back to in-memory; payload
  store uses plain Redis ops and works.
- Live verification: `cd backend && python tests/e2e_hybrid_live.py`
  (real OpenAI/Tavily/Redis calls — costs money, not part of pytest).
