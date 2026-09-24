# VoyagerAI — Known Bugs & Improvements

Audit date: 2026-09-18. Bugs ranked by severity.

## Bugs

### 1. Split-brain reads across all stores — FIXED
Every store (threads, files, shares, costs, security) writes to the first working store but reads Redis-first with early return. Data written to SQLite during a Redis blip becomes invisible once Redis recovers — reads hit empty Redis and return empty/None without checking fallbacks.

- `backend/threads.py:82` — `list_threads` returns `[]` when Redis up but empty → thread list vanishes
- `backend/threads.py:280` — `get_thread` returns None without checking SQLite/memory
- `backend/file_store.py:146` — `get` returns None → uploaded attachment lost
- `backend/share_store.py:149` — `get_share` returns None → share link 404s
- `backend/cost_store.py:517` — `get_user_daily_spend` returns 0 → daily budget cap bypassed

Deletes don't propagate either: `delete_thread` / `revoke_share` / file `delete` remove from one store only — stale copies resurrect on Redis failure.

**Fix applied:** all stores now write-through to Redis + SQLite, reads consult every store and merge/dedupe (freshest wins), deletes propagate everywhere. Covers threads, files, shares, costs, security, rate limits, research cache, geocode cache, feedback, observability. Regression tests in `backend/tests/test_split_brain.py` (17 tests).

### 2. Cooldown bypass — security control fail-open — FIXED (with #1)
`backend/security_store.py:232` — `is_in_cooldown` checks only Redis when connected. A cooldown written to SQLite during a blip becomes invisible → attacker escapes injection cooldown.

**Fix applied:** `is_in_cooldown` now checks Redis, SQLite, and memory — any active cooldown wins. `apply_cooldown`/`remove_cooldown` write/delete everywhere.

### 3. Strikes never decay in SQLite path — FIXED (with #1)
`backend/security_store.py:208` — `get_strike_count` counts all strikes ever (SELECT lacks `created_at >= window_start`; only the DELETE filters). Strikes accumulate forever → permanent cooldown. Redis path is correct.

**Fix applied:** SQLite count query now filters `created_at >= window_start`; count is max across all stores.

### 4. `update_session_total` resets `created_at` every call — FIXED
`backend/cost_store.py` — `created_at: str(now)` overwrote each update:
- Daily spend attributed to last update time, not when incurred → budget check wrong across midnight
- Resumed old threads counted in "last hour" → circuit breaker false-trips for all users

**Fix applied:** `update_session_total` reads the existing session first and preserves the original `created_at` (current time only on first creation), in Redis, SQLite, and memory writes.

### 5. `start_of_day` uses local timezone, not UTC — FIXED
`backend/cost_store.py` — `time.mktime(time.strptime(utc_date))` interpreted a UTC date string as local time. Daily budget window shifted by server TZ offset (IST: +5.5h).

**Fix applied:** shared `_utc_start_of_day()` helper uses `calendar.timegm()` (true UTC) in both `get_user_daily_spend` and `check_platform_alerts`.

### 6. `streamChat` retry duplicates the user message — FIXED
`frontend/lib/chat-api.ts` — stream ended without `done` → re-POSTed same message → backend appended it to the checkpoint again → duplicated user message in history + double LLM cost + doubled visible text.

**Fix applied:** end-to-end idempotency via `client_message_id`:
- Frontend generates one id per logical send (UUID, reused across retries); offline-queue replays reuse the queued `msg.id` so dedup survives reloads.
- `stream_chat_agent`/`edit_chat_agent` stamp the `HumanMessage` with the id and check the checkpoint first: completed run → replay the saved reply (zero LLM cost); interrupted run → resume pending nodes; unseen → append normally. `add_messages` merges same-id messages as a second safety net.
- `_scoped_chat_thread_id` derives a deterministic thread id from `client_message_id` when no thread id exists — retries on new chats hit the same checkpoint instead of minting orphan threads.
- Frontend resets streaming accumulators on `onReconnecting` so re-streamed tokens don't double-display.

### 7. Subagent costs double-persisted — FIXED
`backend/agents/deep_agent.py` — `persist_costs` ran twice per stream; `record_subagent_cost` wrote `{name}:{new_ts}` fields → duplicate rows → admin cost stats inflated ~2x after extraction-retry runs. Prometheus counters double-counted too.

**Fix applied:** `_ModelStream._persisted_subagent_costs` tracks last-persisted per-subagent totals; `persist_costs` writes only the delta (tokens + cost) and increments metrics by the same delta. Zero-delta entries skipped entirely; session total still refreshed each call.

### 8. Shared search counter across concurrent users — FIXED
`backend/agents/tools/internet.py` — `_orchestrator_search_count` was module-global: one user's stream reset or consumed another's quota. Bonus bug: `regenerate_chat_agent`, `edit_chat_agent`, `edit_itinerary_agent` never reset the counter → quota permanently dead after 3 lookups in a thread.

**Fix applied:** `_search_counts[thread_id]` dict keyed by the existing thread-id ContextVar (same pattern as `_image_counts` in visuals.py; new `get_current_thread_id` getter). `reset_orchestrator_search_count(thread_id)` now clears only that thread's bucket and is called at all 4 stream entry points in `deep_agent.py`.

### 9. `Cache-Control: public` on per-user data — FIXED
`backend/main.py` — `/threads` and `/threads/{id}/history` sent `public, max-age=300`. Shared caches/proxies could serve user A's threads to user B.

**Fix applied:** both endpoints now send `private, max-age=300` — browsers still cache 5 min, shared caches may not store or re-serve.

### 10. Hardcoded `localhost:3000` share URL — FIXED
`backend/main.py` — `GET /shares` returned `share_url` pointing at localhost and missing the `/{locale}/` segment. Same hardcoded fallback existed in the OAuth callback.

**Fix applied:** new `_frontend_base_url()` helper (first https CORS origin > first non-`*` origin > localhost) used by the OAuth callback, `create_share_link`, and `list_shares`. Listed URLs now match create's shape: `{base}/{locale}/share/{token}` with the requester's locale.

### 11. Shared `/tmp/agent_fs` across all users — FIXED
`backend/agents/deep_agent.py` — `FilesystemBackend(root_dir="/tmp/agent_fs")` — all users' agent files shared one directory → cross-user file reads/collisions.

**Fix applied:** `root_dir` is now `/tmp/agent_fs/{sha256(user_id)[:12]}` — per-user workspace matching the `/memories/` per-user namespace. Ops note: stale files in the old shared `/tmp/agent_fs` root can be wiped post-deploy.

### 12. Fire-and-forget `asyncio.create_task` per SSE event — FIXED
`backend/main.py` — unreferenced task per streamed token → GC could kill tasks mid-write (observability events silently lost) + unordered writes (events could land before `start_session`, `finalize_session` before trailing events).

**Fix applied:** `_ObsQueue` — one `asyncio.Queue` + one consumer task per stream; callables drained FIFO so ordering is guaranteed. `close()` awaited in each generator's `finally` (5s cap) so `finalize_session` is always written before teardown. All 3 generators (stream/regenerate/edit) rewired via shared `_send_obs_event` helper; only remaining `create_task` is the referenced startup cleanup task.

## Improvements

- ~~**oauth.py per-call Redis connection**~~ — DONE; `_redis_client` singleton reused across session ops (redis.asyncio pools internally), `_drop_redis()` discards it on failure so the next call reconnects.
- ~~**`get_thread_history` builds a full agent per request**~~ — DONE; `_read_thread_values` reads `channel_values` straight from the checkpointer (`aget_tuple`) for history + itinerary; branch listing keeps the full agent for `aget_state_history`.
- ~~**Regenerate/edit streams lack `sawDone` tracking**~~ — DONE; `regenerateStream`, `editStream`, `editItinerary` now retry truncated streams and surface `streamEnded` like `streamChat`.
- ~~**Attachment messages stringify to Python repr**~~ — DONE; `_history_message_text` renders text blocks + `[Image attached]`/`--- Attached PDF: name ---` markers, drops extracted bodies.
- ~~**`handleSend` stale closures**~~ — DONE; dep arrays completed (`pendingAttachments`, `locale`, `currency`, `userTimezone`, `partialResearch`; `handleRetry` + `lastSentMessage`).
- ~~**`extraction_failure_hint` injected as a real user message**~~ — DONE; hint gets a known id and is `RemoveMessage`d from the checkpoint post-retry at all 4 sites.
- ~~**In-memory fallbacks never expire**~~ — DONE; every `_mem` dict honors its store's `_TTL_SECONDS` via `_prune_mem` on write + lazy expiry on read + hourly sweep (`cleanup_expired*` now also sweeps mem). Also fixed: expired `_mem_sessions` no longer authenticate, and SQLite-miss early-returns in `get_session_cost`/`get_feedback`/`geocode get` now fall through to memory.
- ~~**Any non-OK response treated as logout**~~ — DONE; all sites already gated on 401, and `get_session` now raises `SessionStoreUnavailable` → 503 + Retry-After when durable stores fail mid-lookup (no more logout on transient outage).
- ~~**Multi-worker unsafe**~~ — DONE (warn + docs); startup warns when `UVICORN_WORKERS`/`WEB_CONCURRENCY`/`GUNICORN_WORKERS` > 1, naming per-worker state (cancel_registry, `_search_counts`, `_mem`, checkpointer caches). Docstring notes added to `cancel_registry.py` + `internet.py`.

## Suggested fix order

1. ~~**#1**~~ — DONE; write-through/read-all/delete-all applied to all stores.
2. ~~**#2 + #3**~~ — DONE (fixed alongside #1).
3. ~~**#4 + #5**~~ — DONE; `created_at` preserved + true-UTC daily boundary.
4. ~~**#6**~~ — DONE; end-to-end idempotent retries via client_message_id.
5. ~~**#9 + #11**~~ — DONE; per-user agent fs + private cache headers.
6. ~~**#7**~~ — DONE; delta-based persist_costs.
7. ~~**#8**~~ — DONE; per-thread search quota.
8. ~~**#10**~~ — DONE; `_frontend_base_url()` shared helper.
9. ~~**#12**~~ — DONE; `_ObsQueue` ordered observability writes. All bugs fixed — Improvements list remains.

---

# Pipeline Migration — Post-Cutover Tracker

Audit date: 2026-09-24, after the deterministic-pipeline cutover (commit `584c612`).
Old tag-emission path removed; single path live. Items ranked by severity.

## Reliability / trust

### R1. Upstash lacks RediSearch → checkpointer + semantic memory degraded — FIXED (Postgres durable tier)
Resolved by the Postgres migration: `CHECKPOINTER_BACKEND=postgres` + `STORE_BACKEND=postgres` route LangGraph state to `AsyncPostgresSaver`/`PostgresStore` in Supabase via `DATABASE_URL` — no RediSearch needed. Upstash stays for hot/TTL data only (payloads, rate limits, caches). `backend/pg_store.py` provides the shared pool + `get_durable_db()` (PG-primary, SQLite disaster-tier) for all durable stores; PG outage or empty `DATABASE_URL` degrades to SQLite/memory with warnings. `CHECKPOINTER_BACKEND=redis` remains as a fallback path with the old degraded behavior.

**Verify:** set `DATABASE_URL` → startup logs `pg durable tier: CONNECTED`; restart backend → conversations + memories/preferences survive; pull PG → logs `DEGRADED` and stores keep working on SQLite.

### R2. `estimated_total_cost_usd` field name lies about currency — OPEN (minor)
Field actually holds the user's currency (₹/€/¥), but the `_usd` name nudges the model toward USD — observed live: first generation attempt emitted USD-ish totals in one field and INR in the matrix (validator caught it, retry fixed).

**Options:** (a) rename field everywhere incl. frontend (breaking), (b) add a `total_cost` alias and deprecate `_usd` reads, (c) leave — prompt already warns, validator catches.
**Files:** `backend/agents/pipeline.py` schemas, `frontend/lib/types.ts`, `ComparisonView.tsx`, reconciler in `deep_agent.py`.

### R3. Validation retries burn tokens silently — OPEN (minor)
Each failed structured-generation attempt retries with feedback (~1 extra gpt-4o-mini call, seen live ~10-20s each). `_stage_usage` attributes them correctly, but there's no cap beyond `_MAX_GENERATION_ATTEMPTS` and no surfacing of "this request needed N retries" to observability.

**Options:** emit a `retries` count on the tool result → activity row; add a metric counter; consider trimming research briefs (big inputs may be why gpt-4o-mini strays).

### R4. Fresh payload not replayable — OPEN (small)
`pop_payload` is one-shot by design. If a client's SSE connection dies between card emission and render, the payload is gone; the checkpoint only holds the compact tool message. Chat text survives — card does not re-emit on reload.

**Options:** keep one-shot for itinerary but TTL-cache the latest comparison per thread keyed by message id (already have `pipeline:thread:{tid}:latest_comparison`) and re-emit on history load if the last AI turn references a payload id.

### R5. Tavily is a single point of failure for research — OPEN (known/degraded-by-design)
Search outage → briefs become `[unavailable]` markers and plans still generate with thin data. Graceful, but quality drops silently.

**Options:** second provider fallback (Serper/Brave), or surface "limited research" warning in the comparison payload → UI badge.

## UX upgrades

### U1. Per-stage progress labels — FIXED
`lib/stage.ts` derives the running stage from top-level `tool_calls` (`generate_trip_plans`/`refine_itinerary`/researcher/subagents → `status.*` keys) and the detail line from `progressMap`. `GenerationStatus.tsx` renders the localized label + rotating backend descriptions ("Searching: hotels in Delhi…") under the streaming bubble — visible even while text streams. New `status.buildingItinerary` key in all 6 locales.

### U2. Skeleton cards during generation — FIXED
`ComparisonSkeleton` (banner + matrix strip + 3 tier cards) renders between `generate_trip_plans` tool_start and the `comparison` event; `ItinerarySkeleton` (header + day rows) between `refine_itinerary` start and `itinerary`. Run-ids are tracked so `tool_end`/`tool_error` clears exactly; `onComparison`/`onItinerary`/`done`/`error`/`cancelled`/`reconnect` all reset — skeletons cannot stick. Uses `.shimmer` + DESIGN.md tokens, reduced-motion safe.

### U3. "Why this tier" explainer on cards — OPEN
`tradeoffs`/`highlights` already in payload, partially shown; surface as a hover chip ("Why balanced?") summarizing tradeoffs in one line.

### U4. Currency-aware number formatting — OPEN
₹ should render Indian-style (₹50,000 → lakh separators), JPY no decimals, etc. Check `ComparisonView`/itinerary totals formatting — likely plain `toLocaleString` or none.

### U5. Edit-diff view after manual edit validation — OPEN
`run_edit_validation_pipeline` may change the user's edit (fills slots, fixes conflicts). User sees the corrected card but not what changed.

**Do:** have the stage return a `changes[]` list (field/before/after/reason — the repaired diff) and show a dismissible "Adjusted 2 things" note.
**Files:** `backend/agents/pipeline.py` edit stage result; frontend edit flow.

### U6. Regenerate a single tier — OPEN
"Try again" regenerates all 3 plans. If user only dislikes premium, that's wasted cost/time.

**Do:** `refine_itinerary`-adjacent tool or `generate_trip_plans(tier=...)` variant; UI: per-card refresh icon.

### U7. Constraint quick-pick chips — OPEN
After "plan a trip", model asks for fields in prose. Chips for travel_style / group_type / dietary would cut a round-trip.
**Do:** emit a `clarify` event when required fields are missing with `missing_fields[]`; frontend renders chips that prefill the reply.

## Map status

### M1. MapLibre import crash — FIXED
`import * as maplibregl` broke under Next.js + maplibre-gl v6 ESM → named imports (`Map`, `Marker`, `Popup`, `LngLatBounds`) in `frontend/components/ItineraryMap.tsx`. Tests pass.

### M2. Blank-map fallback — FIXED (commit `c33c067`)
Day-panel map previously stayed blank on missing coords; now falls back instead.

### M3. Geocode coverage gaps — OPEN (verify live)
Pipeline enriches coordinates, but activities the geocoder misses get no pin — silently. Check a real generated itinerary: count activities vs pins.

**Options if gaps:** per-day centroid fallback pin; log geocode misses per itinerary for observability; async re-enrich after card delivery.
**Files:** `backend/geocode_cache.py`, enrichment stage in `pipeline.py`, `ItineraryMap.tsx`.

## Suggested order

1. ~~**R1** — decide Redis path~~ FIXED — Postgres durable tier (needs `DATABASE_URL` set to go live)
2. ~~**U1 + U2**~~ FIXED — stage status line + comparison/itinerary skeletons
3. **M3** — verify pins on a real itinerary
4. **U6** — single-tier regenerate (cost saver)
5. **R2–R5, U3–U5, U7** — batch when touching those files
