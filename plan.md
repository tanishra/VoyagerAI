# PromptWars — Development Plan

## Phase 1: Core DeepAgent ✓

**Status: COMPLETE**

- [x] DeepAgent factory (`create_travel_agent`)
- [x] Sub-agents: researcher, validator, enricher, cost_optimizer
- [x] Tavily internet search tools
- [x] `/plan`, `/plan/stream`, `/replan-day` endpoints
- [x] Prompts for all agents
- [x] Redis checkpointer + store
- [x] All 84 backend tests passing

---

## Phase 2: SSE Streaming + Progress UI ✓

**Status: COMPLETE**

- [x] SSE streaming client (`frontend/lib/streaming-api.ts`)
- [x] Streaming progress component (`StreamingProgress.tsx`)
- [x] Plan page uses `/plan/stream` instead of blocking POST
- [x] Dead code cleanup (unused imports, vars, states)
- [x] Removed 4 redundant search tools from `internet.py`
- [x] Abort signal safety net — `setLoading(false)` after every exit path
- [x] CORS env var fix — use `settings.CORS_ORIGINS` not `os.getenv`
- [x] Cache check before streaming — `/plan/stream` checks + saves cache
- [x] Thread ID uniqueness — includes `request_id` for streaming
- [x] All code quality issues fixed

---

## Phase 3: Persistence & Memory ✓

**Status: COMPLETE**

- [x] `create_travel_agent()` accepts `user_id` parameter
- [x] `CompositeBackend` routes `/memories/` → `StoreBackend` with per-user namespace
- [x] Built-in `memory=["/memories/preferences.md"]` enables `MemoryMiddleware` auto-load
- [x] `get_redis_file_store()` singleton (Redis with `InMemoryStore` fallback)
- [x] Filesystem permissions include `/memories/**`
- [x] `GET /preferences` and `PUT /preferences` REST endpoints
- [x] All three planning endpoints extract `X-User-Id` header and pass to agent
- [x] `agents/__init__.py` exports `get_redis_file_store`
- [x] All prompts rewritten with XML tags (`<role>`, `<memory>`, `<workflow>`, etc.)
- [x] Memory read/write instructions with explicit `write_file` vs `edit_file` guidance
- [x] REST endpoints use `/preferences.md` key matching `StoreBackend` after route stripping
- [x] Frontend X-User-Id — `user-id.ts` utility with localStorage UUID
- [x] Preferences UI page — `/preferences` page with textarea editor
- [x] Backend tests — 5 tests covering round-trip, isolation, key schema

---

## Phase 4: Conversational Multi-Agent Planning Engine

**Status: IN PROGRESS**

### Overview

Migrate from the old form-based flow to a conversational multi-agent system. The user types a free-form request → an orchestrator agent decomposes it → dispatches specialized sub-agents in parallel → generates multiple plan variants → self-critiques → presents results with comparison. Every refinement resumes from checkpoint without restarting.

Built entirely on deepagent primitives: `create_deep_agent`, `Checkpointer` (for thread resumption), `SubAgent` (for parallel dispatch), `memory=` (for cross-session learning), `astream_events` (for streaming).

---

### Phase 4.1 — Chat Endpoint + Dual-Mode Agent Prompt ✓

**Goal:** `POST /chat/stream` endpoint. Agent can switch between conversational mode (chat naturally) and structured mode (emit JSON for frontend rendering).

**Backend:**
- [x] New system prompt in `agents/prompts.py` — `<chat_mode>` block with dual output rules:
  - `<mode type="conversation">`: natural language, ask clarifying questions, discuss options
  - `<mode type="structured">`: emit JSON itinerary inside `<itinerary>` tags
  - The agent decides which mode based on user intent
- [x] `create_chat_agent()` in `agents/deep_agent.py` — similar to `create_travel_agent()` but uses the new prompt, sets up checkpointing for resumption, and keeps the same CompositeBackend for memory
- [x] `POST /chat/stream` in `main.py` — accepts `{message: string, thread_id?: string}`, resumes from checkpoint if thread_id provided, streams SSE events (`token` for tokens, `itinerary` for structured output, `status` for tool progress)
- [x] `ChatRequest` model in `models.py` with optional `thread_id` (separate from form-based `PlanRequest`)

**Frontend:**
- [x] `frontend/app/chat/page.tsx` — message list + input bar, streaming text, inline itinerary cards
- [x] `frontend/lib/chat-api.ts` — SSE streaming client for chat (parses `token`, `itinerary`, `status`, `thread_id` events)
- [x] Add "Chat" link to `Navbar.tsx`

**Key deepagent features used:** `create_deep_agent`, checkpointer, `astream_events`, `memory=`

---

### Phase 4.2 — Parallel Sub-Agent Dispatch

**Goal:** Orchestrator decomposes user request and dispatches researcher, constraint analyzer, and risk detector agents in parallel via deepagents' `task` tool (parallel tool calls in one message — the framework's native `asyncio.gather` equivalent).

**Backend:**
- [x] New sub-agent: `risk_detector` (`agents/subagents/risk_detector.py`)
  - Checks: seasonal closures, weather risks, transit gaps, safety advisories, holiday impacts
  - Uses `internet_search` for current info
- [x] New sub-agent: `constraint_analyzer` (`agents/subagents/constraint_analyzer.py`)
  - Reads user preferences from memory
  - Analyzes budget constraints (per-day allocation, total cap)
  - Checks dietary, mobility, group constraints
- [x] Enhance `researcher` sub-agent to split into parallel sub-queries:
  - Hotels research, weather & events, must-see & transport
  - Each runs as a separate sub-agent task via deepagent's `task` tool (orchestrator dispatches 3× researcher in parallel)
- [x] Update orchestrator prompt to use `<parallel_dispatch>` workflow:
  1. Parse user request
  2. Dispatch researcher ×3 / constraint_analyzer / risk_detector in parallel
  3. Collect results
  4. Synthesize into structured plan brief
- [x] Bug fix: `/chat/stream` was dropping all raw v2 `astream_events` (tokens never streamed, tool statuses never reached the UI). Added `_parse_chat_event()` helper; tokens and subagent status events now flow over SSE.
- [x] SSE now emits subagent `status` events (`running` / `done`) from `on_tool_start` / `on_tool_end` (run_id-tracked)

**Frontend:**
- [x] `chat/page.tsx` — live worker status chips (researching / checking risks / checking constraints)
- [x] `StreamingProgress.tsx` — new steps for risk_detector + constraint_analyzer; maps `task` tool dispatches to subagent labels; uses `useEffectEvent` for stream-event handling

**Tests:** `test_subagents.py` (registry + prompts), `test_streaming.py` (v2 event parsing regression) — 36 new tests

**Key deepagent features used:** `SubAgent`, `task` tool, parallel tool calls (framework-native concurrency), `run_name`-based chain events

---

### Phase 4.2.1 — Bug Fix Audit ✓

**Goal:** Fix all bugs found in the post-4.2 audit across phases 4.1, 4.2, and earlier. 8 atomic commits (30f687f → 11ace99).

- [x] **Stale closure** (chat/page.tsx) — `itinerary: streamingItinerary ?? undefined` read a stale `null` from `handleSend`'s closure, so the itinerary card vanished after the stream committed. Now `let accumulatedItinerary` is set in the `onItinerary` callback and used at commit time
- [x] **Unreliable `<itinerary>` emission** — model skipped the tags in ~3 of 4 runs. Three-layer fix:
  - Prompt: "MANDATORY: every structured-mode response MUST end with the itinerary JSON inside `<itinerary></itinerary>` tags" (+ partial plans still in tags, no code fences)
  - Fallback extraction: `_find_largest_json_object()` scans for the largest brace-balanced JSON object (longest-first) and accepts it if it has `destination` + `days` keys
  - Retry: `stream_chat_agent` re-invokes the agent once ("output the itinerary JSON now") if nothing is extractable, then gives up gracefully
- [x] **Dead Redis → 500 on `/preferences`** — `get_redis_file_store` only guarded singleton creation. GET now returns 503, PUT returns `{"status":"error",...}` instead of crashing
- [x] **`on_tool_error` leak** — run_id stayed in `active_tasks` forever, leaving the worker chip stuck on "running". Handler now pops and emits `status {tool, "status":"error"}`
- [x] **Constant-time API key check** — auth used `!=` (timing side-channel). Now `hmac.compare_digest`
- [x] **`/replan-day` thread_id used `hash()`** — randomized per process, so resume-after-replan broke across restarts. Now `sha256(itinerary json)[:16]`
- [x] **ChatRequest.thread_id unbounded** — capped at `max_length=200` (message was already capped at 2000 — original audit item was a false positive)
- [x] **Duplicate "✓ task complete" log** — `on_tool_end` for the `task` tool double-logged dispatch completions; now suppressed for `name == "task"`
- [x] **No chat cancel button** — Stop button added to the input bar (aborts the fetch via `AbortController`)
- [x] **No SSE wiring integration test** — added end-to-end `TestClient` tests asserting the full event sequence (thread_id → thinking → token → subagent running/done → itinerary → done) plus the tool-error status path
- [x] **Model degeneracy guard** — 45-char truncated responses (Gemini flake) previously yielded no itinerary; covered by the retry (see above)
- [ ] (not fixed, by design) `X-User-Id` is client-controlled — no auth system exists yet; 300s timeout middleware left as-is; `plan.md` is gitignored

**Tests:** `test_streaming.py` (endpoint wiring, tool-error status, retry logic — fake agent), `test_itinerary_extraction.py` (tags + fallback) — 16 new tests. Total: 124 passed, 17 skipped. Live smoke: 5 parallel sub-agent dispatches + itinerary event confirmed.

---

### Phase 4.2.2 — Deepagents Migration Chat Hardening ✓

**Goal:** Fix all bugs found in the post-4.2.1 re-verification that are specific to the deepagents migration (chat endpoint, chat page, chat SSE client, chat agent). Form-based flow (plan wizard, preferences UI, replan) was out of scope. 3 atomic commits (538a39e → f0b62a2).

- [x] **Unvalidated chat itinerary could crash the chat page** — `_extract_chat_itinerary` only checks `destination`+`days`, so raw LLM JSON missing `warnings`/`days`/`estimated_total_cost_usd` flowed straight to `ItineraryCard` (`itinerary.days.map` / `itinerary.warnings.length`) with no ErrorBoundary. Now the card is defensive: `days ?? []`, `warnings ?? []`, `?? 0`/`?? days.length`, optional-chained day slots. Client-side only — strict backend `model_validate` was rejected because it would break the intentional partial-plan feature
- [x] **"New Chat" mid-stream resurrected the old thread** — the in-flight stream wasn't aborted, so `onThreadId` + the post-await commit re-wrote `localStorage` after the user reset; the next message silently resumed the old conversation. Now `handleNewChat` aborts the controller and a `sessionResetRef` guard skips all thread-id commits (callback + commit path)
- [x] **Backend `error` events were silently swallowed** — `handleChatEvent`'s switch had no `error` case, so an extraction failure produced a silent empty assistant bubble. Added `case 'error'`; the page now renders "⚠ Generation failed: …" and skips the itinerary commit
- [x] **Abort committed an empty/truncated bubble** — no aborted flag existed. Added `onAbort` callback (`ChatStreamCallbacks`) → the page commits "⏹ Generation stopped." when nothing was streamed
- [x] **SSE parser lost the final event on truncation** — buffered lines were never flushed when the stream closed mid-event (the pending event sat in the parser's closure, not the buffer) and `TextDecoder` never got its final `decode()`. Refactored to `processLines`/`dispatchIfReady` closures + `buffer += decoder.decode()` + `dispatchIfReady()` after the loop; verified with a byte-level node simulation (truncated final chunk, split multi-byte UTF-8, normal stream)
- [x] **Chat input hardening** — Enter no longer fires during IME composition (`nativeEvent.isComposing`), `sendingRef` guards double-send in the same tick (stale `loading` closure), `try/finally` guarantees `setLoading(false)`/abort cleanup, and `localStorage.setItem` throws (quota) no longer kill the stream mid-way
- [x] **`crypto.randomUUID()` threw on non-secure contexts** (http://LAN-IP) — broke every API call including chat. Now falls back to a generated id, and `localStorage` access is wrapped with an in-memory id fallback (shared util, but chat depends on it)

**Verified:** 124 backend tests pass, ruff clean, `tsc`/`eslint` clean, production build succeeds, SSE parser simulation passes all 3 edge cases, and a live HTTP smoke over the real backend produced the full event chain (thread_id → 10 subagent status events → 100+ tokens → complete 9-field itinerary event → done).

---

### Phase 4.2.3 — Chat Stream Resilience & Thread Scoping ✓

**Goal:** Fix the 6 findings from the plan.md-scoped audit of Phases 4.1/4.2/4.2.1/4.2.2 (deepagents scope only). 5 atomic commits (e482af8 → 620dfad).

- [x] **LLM/agent exception closed the SSE stream with no `error` event** — `chat_stream`'s generator had no try/except, so a mid-stream crash silently hung the client (spinner forever). Now wrapped; exceptions log with traceback and emit `error` SSE before closing. **Found live:** the very first post-fix smoke run proved the path — Redis reachability caused a `NotImplementedError` (below) that previously produced a dead stream and now produces a clean error event
- [x] **Thread ownership gap (cross-user resume)** — client-supplied `thread_id` was used verbatim against the global RedisSaver, so anyone could resume someone else's conversation. Now ids are server-side scoped to `chat:{sha256(user_id)[:12]}:{id}`; already-scoped ids pass through, unscoped/absent ids get scoped. Verified live: `chat:9bbf17488ebf:...`
- [x] **Retry turn never streamed** — the extraction-failure retry used `ainvoke`, so tokens from the second pass never reached the UI (and the response appeared to hang). Now it runs a second `astream_events` pass so retry tokens stream like the first
- [x] **`RedisSaver.aget_tuple` unimplemented → every async run crashed when Redis was reachable** — the sync `langgraph.checkpoint.redis.RedisSaver` inherits `BaseCheckpointSaver.aget_tuple` (`raise NotImplementedError`), so any chat/travel stream with Redis up died instantly (`NotImplementedError` in `AsyncPregelLoop.__aenter__`); with Redis down the MemorySaver fallback masked it (source of the earlier flakiness). Switched to `AsyncRedisSaver` (`langgraph.checkpoint.redis.aio`, implements `aget_tuple`); factories became async and await `setup()`. Note: this machine's Redis lacks RediSearch (`FT._LIST` unknown), so `setup()` fails and the factory falls back to MemorySaver — now a *clean* fallback instead of a guaranteed crash
- [x] **Premature stream close indistinguishable from success** — the client called `onDone` unconditionally after the read loop. Now `done` is a tracked event: `sawDone` flag; if the stream ends without it (and without abort), the client raises "Stream ended before the agent finished" instead of silently rendering a truncated reply
- [x] **No ErrorBoundary on the chat page** — unvalidated itinerary JSON crashing the renderer now shows a fallback notice (restart via New Chat) instead of a blank white screen
- [x] **Missing cost rendered as `$0`** — `estimated_total_cost_usd` is optional in raw LLM output; the card now shows "N/A" and the type is `number | null` (BudgetSummary uses `?? 0` to stay type-safe)

**Verified:** 130 backend tests pass (17 skipped), ruff clean, `tsc`/`eslint` clean, production build succeeds, live smoke over the real backend shows the complete chain (scoped thread_id → status → tokens → done) and the error path emits an `error` event instead of a dead stream.

---

### Phase 4.2.4 — Itinerary Reliability & Operational Hardening ✓

**Goal:** Close the 3 caveats from the 4.2.3 review: (1) Redis on this machine is the homebrew build without RediSearch (checkpointing silently fell back to MemorySaver → no persistence across restarts), (2) itinerary generation was prompt-only at temperature 0.4 with zero schema enforcement (frequent missing/partial JSON), (3) frontend lint debt + flaky TripWizard tests. 2 atomic commits (25abf85, d15beda).

- [x] **Redis Stack replaces homebrew redis** — `brew tap redis-stack/redis-stack && brew install redis-stack-server` (7.4.0-v8, modules: search 2.10.20 / timeseries / vectorset); homebrew redis stopped. `FT._LIST` now works so `AsyncRedisSaver.setup()` succeeds. Runs as a daemon (`redis-stack-server --daemonize yes`) — not auto-started on reboot
- [x] **Configurable checkpointer backends** — `CHECKPOINTER_BACKEND` setting (`redis` default / `sqlite` / `memory`) + `CHECKPOINTER_DB_PATH`; `create_checkpointer()` dispatches with Redis → SQLite file (`AsyncSqliteSaver` on an aiosqlite connection) → MemorySaver degradation chain; both agent factories use it. `.env.example` documents all three
- [x] **Itinerary emitted every turn (root-caused)** — the agent node persists only the *first stream chunk* of each model call, so checkpoint messages were truncated stubs (e.g. 17 chars of a 7000-char JSON). Extraction read the checkpoint, failed, and the formatter hallucinated a destination ("Paris, France" for a Udaipur trip). Fix: `_ModelStream` accumulates full text from `on_chat_model_stream` events per model run and extraction prefers it; state, feedback-aware retry hint, and the structured formatter remain as fallbacks. Verified live: resume turn now returns the correct 2-day Udaipur itinerary while the checkpoint still holds the stub
- [x] **Structured formatter + lower temperature** — chat model temp 0.4 → 0.2; `_format_itinerary` uses `with_structured_output(_ItineraryDraft)` (gemini-2.5-pro @ 0.1, pydantic schema: destination/days/visa_note/budget/warnings/packing) as the final fallback
- [x] **Eslint zero-warning cleanup** — plan/preferences pages (effect deps), Navbar (rAF), tests/setup (typed mocks), unused imports removed
- [x] **TripWizard test flake fixed** — sessionStorage form-data leaked between tests; `beforeEach(sessionStorage.clear())`

**Verified:** 138 backend tests (17 skipped), ruff clean; frontend eslint 0/0, tsc clean, build green, vitest 147/147; live smoke (new chat + resume "make it 2 days") returns Udaipur 1-day then 2-day itineraries with destinations matching the streamed tokens; checkpoint persistence across server restarts confirmed via Redis keys. Known env gap (out of scope): `TAVILY_API_KEY` unset so research subagents degrade gracefully; memory file read path shows `/preferences.md` not found (write succeeds).

---

### Phase 4.3 — Multi-Plan Generation + Comparison ✅

**Goal:** Agent generates 3 plan variants (budget / balanced / premium) and presents them in a side-by-side comparison view.

**Backend:**
- [x] New sub-agent: `multi_plan_generator` (`agents/subagents/multi_plan_generator.py`)
  - Takes the research + constraints + risk brief
  - Generates 3 itineraries at different budget tiers
  - Returns structured data: `{plans: [{tier, itinerary, cost_breakdown, tradeoffs}], comparison_matrix: {...}}`
- [x] Update orchestrator prompt to include `<comparison_format>` block for structured comparison output
- [x] Update `ChatEvent` model to include `comparison` event type for frontend rendering

**Frontend:**
- [x] `frontend/app/chat/ComparisonView.tsx` — card-based side-by-side comparison:
  - 3 columns with cost, hotel tier, food style, activities per day
  - Highlight differences (⚠ budget: street food only / ✅ premium: Michelin star)
  - Click to select a plan → resumes chat with chosen plan
- [x] Render comparison cards inline in chat when `comparison` event arrives

**Key deepagent features used:** `SubAgent`, `StructuredOutput`, `astream_events`

**Verified:** 126 backend tests passed, ruff clean; frontend 42 vitest passed, tsc clean, eslint 0 warnings, production build green.

---

### Dynamic LLM Provider Switching via LiteLLM ✅

**Goal:** Replace hardcoded Gemini model instantiation with a config-driven model factory, enabling provider switching (Gemini, OpenAI, Anthropic, etc.) via environment variables with fallback routing support.

**Changes:**
- [x] New `agents/llm.py` — model factory with `get_orchestrator_model()`, `get_subagent_model()`, `get_formatter_model()`
- [x] Config fields in `settings.py`: `LLM_ORCHESTRATOR_MODEL`, `LLM_ORCHESTRATOR_FALLBACK`, `LLM_SUBAGENT_MODEL`, `LLM_SUBAGENT_FALLBACK`, `LLM_TEMPERATURE_ORCHESTRATOR`, `LLM_TEMPERATURE_SUBAGENT`
- [x] Replaced all `ChatGoogleGenerativeAI` instantiations in `deep_agent.py` and `subagents/__init__.py` with factory calls
- [x] All 7 subagent builder type hints generalized to `BaseChatModel`
- [x] `.env.example` updated with LiteLLM provider config section
- [x] `conftest.py` checks for any provider API key (not just Gemini)
- [x] New `tests/test_llm.py` — 5 tests for model factory

**Verified:** 126 backend tests passed, ruff clean.

---

### Phase 4.3.1 — Production-Grade UI Upgrade ✅

**Goal:** Upgrade the frontend from dark-theme MVP to a premium light-theme design with smooth scrolling, Geist fonts, animated components, and provider-agnostic branding.

**Dependencies & Setup:**
- [x] Installed `lenis` (smooth scrolling) and `geist` (Vercel font family) packages
- [x] Created `SmoothScroll` provider (`components/providers/SmoothScroll.tsx`) using `ReactLenis` — wrapped around app in `layout.tsx`
- [x] Switched from Plus Jakarta Sans to Geist Sans + Geist Mono via `next/font` (`geist/font/sans`, `geist/font/mono`)

**Theme & Global Styles (`globals.css`):**
- [x] Replaced dark OKLCH palette with premium light palette (white background, indigo/violet accents)
- [x] Updated CSS custom properties: `--background`, `--foreground`, `--card`, `--muted`, `--border`, `--primary`, `--accent`
- [x] New keyframes: `aurora` (slow gradient drift), `float-slow` (gentle vertical float)
- [x] Updated `@theme` font variables to Geist Sans/Mono

**Components Upgraded:**
- [x] `Navbar.tsx` — blur-on-scroll background, animated active link underline (Framer Motion `layoutId`), indigo/violet CTA button, responsive mobile menu
- [x] `HeroSection.tsx` — aurora gradient background, indigo accent text, `TextGenerate` blur-in subtitle, provider-agnostic badge/heading
- [x] `HowItWorks.tsx` — white cards with indigo/violet/emerald accent gradients, provider-agnostic step titles
- [x] `FeatureGrid.tsx` — bento-style grid, white cards, `SpotlightCard` mouse-tracking hover effect, provider-agnostic text
- [x] `StatsSection.tsx` — animated count-up numbers, indigo accent colors, provider-agnostic labels
- [x] `CTASection.tsx` — indigo gradient banner with call-to-action
- [x] `Footer.tsx` — light theme with muted background, indigo logo accent, "Built with AI · Powered by LiteLLM"

**Pages Upgraded:**
- [x] `app/page.tsx` (Home) — aurora gradient container, all section components
- [x] `app/about/page.tsx` — light theme with indigo accents, white cards, "How It Works — Behind the Scenes" section
- [x] `app/faq/page.tsx` + `FaqSection.tsx` — light theme accordion, indigo badge, provider-agnostic Q&A text
- [x] `app/chat/page.tsx` — light theme chat bubbles (`bg-card`), indigo worker chips, `border-border` separators, light input bar
- [x] `app/chat/ComparisonView.tsx` — light theme plan cards with emerald/indigo/amber tier colors, white card containers
- [x] `app/preferences/page.tsx` — light theme with indigo accents, white card editor, light textarea

**Custom Animated Components (Aceternity UI / Animate UI inspired):**
- [x] `components/ui/text-generate.tsx` — blur-in text animation using `useInView` + Framer Motion
- [x] `components/ui/spotlight-card.tsx` — mouse-tracking radial spotlight overlay for cards
- [x] `components/ui/border-beam.tsx` — rotating conic-gradient border beam effect

**Provider-Agnostic Branding:**
- [x] Replaced all "Gemini" references with "AI" across all components and pages
- [x] Replaced "Powered by Google Gen AI" with "Powered by LiteLLM" in Footer
- [x] Updated all 7 test files to match new provider-agnostic text
- [x] Updated `tests/setup.ts` mock to include `useInView` for Framer Motion

**Verified:** `tsc --noEmit` 0 errors, `eslint . --max-warnings 0` 0 warnings, `vitest run` 42/42 passed, `next build` compiled successfully (all 7 routes generated).

---

### Phase 4.4 — Self-Critique Loop ✅

**Goal:** Before presenting any plan, the orchestrator dispatches a quality scorer agent that evaluates the plan against criteria and suggests improvements. The orchestrator applies fixes before output.

**Backend:**
- [x] New sub-agent: `quality_scorer` (`agents/subagents/quality_scorer.py`)
  - 10 evaluation criteria:
    1. Budget accuracy (total within cap, per-day reasonable)
    2. Constraint satisfaction (dietary, mobility, group)
    3. Route efficiency (logical day order, transit feasible)
    4. Activity density (not too packed, not too sparse)
    5. Seasonal appropriateness (weather, closures)
    6. Safety (advisories, neighborhood risks)
    7. Diversity (mix of culture/food/sightseeing/relaxation)
    8. Local authenticity (hidden gems vs tourist traps)
    9. Internal consistency (costs add up, durations match)
    10. Completeness (all required fields, warnings, tips)
  - Returns `{score: 0-100, criteria_scores, issues: [{criteria, severity, message, fix}], improved_plan?: dict}`
- [x] Update orchestrator with self-critique workflow (`<self_critique>` block in `CHAT_AGENT_SYSTEM_PROMPT`):
  1. Generate multi-plan
  2. Score each plan via `quality_scorer` (3 parallel task calls)
  3. If any plan scores < 80, apply fixes from `quality_scorer`
  4. Re-score improved plan (max 2 fix iterations per plan)
  5. Present only when all selected plans score >= 80 (or after max iterations)

**Frontend:**
- [x] Added `quality_scorer` to `TOOL_LABELS` ("Scoring quality") and `TOOL_ICONS` in `chat/page.tsx`

**Tests:** Updated `test_subagents.py` — registry 7→8, added `TestQualityScorerPrompt` (6 tests) and `TestChatPromptSelfCritique` (4 tests)

**Key deepagent features used:** `SubAgent`, agent calling agent pattern, iterative refinement loop

---

### Phase 4.5 — Thread Management Dashboard ✅

**Goal:** Users can view, resume, and delete past conversations. Threads are stored in Redis via the existing checkpointer.

**Backend:**
- [x] `GET /threads` — list user's recent threads from thread metadata store (returns `{threads: [{thread_id, summary, created_at, updated_at, status, message_count}], has_more: bool}`)
- [x] `GET /threads/{thread_id}/history` — replay past messages from checkpointer state, with itinerary/comparison extraction from assistant messages
- [x] `DELETE /threads/{thread_id}` — delete a thread's metadata + underlying checkpointer state via `adelete_thread()` (ownership-verified via prefix check)
- [x] `POST /chat/stream` auto-saves thread metadata via `thread_store.upsert_thread()` in `finally` block with AI-generated summary and status tracking
- [x] New `backend/threads.py` — `ThreadStore` with Redis sorted set + hash, in-memory fallback
- [x] Cursor-based pagination: `offset` + `limit` query params on `GET /threads`
- [x] Thread status tracking: `busy` at stream start, `idle` on success, `error` on failure
- [x] AI-generated summaries: `generate_summary()` calls subagent model for one-line conversation summary
- [x] Thread TTL: Redis key `EXPIRE` on metadata (default 30 days via `THREAD_TTL_DAYS`), background cleanup task for expired checkpoints
- [x] Checkpoint cleanup: `adelete_thread()` called on `DELETE /threads/{id}` to remove orphaned checkpointer state

**Frontend:**
- [x] `frontend/app/chat/ThreadSidebar.tsx` — ChatGPT-style collapsible sidebar with thread list
- [x] Thread preview shows: summary text, relative time, status dot indicator, message count, delete button with confirm
- [x] Click to resume — fetches message history via `GET /threads/{id}/history` and replays in chat UI with itinerary/comparison cards
- [x] `frontend/lib/threads-api.ts` — `listThreads(offset)`, `getThreadHistory()`, `deleteThread()` with `ThreadListResponse` type
- [x] Sidebar toggle button in chat header (`PanelLeft` icon)
- [x] "Load more" button at bottom of thread list for pagination

**Tests:** `backend/tests/test_threads.py` (24 tests: ThreadStore unit, endpoint, history, auto-save, status, pagination, count, itinerary extraction), `frontend/tests/ThreadSidebar.test.tsx` (7 tests)

**Key deepagent features used:** checkpointer (state replay via `aget_state`, cleanup via `adelete_thread`), `StoreBackend`, thread metadata index, Redis key TTL

---

### Phase 4.6 — Polish & Production Hardening ✅

**Goal:** Error handling, loading states, empty states, mobile responsiveness, accessibility, and performance.

- [ ] Graceful degradation — if a sub-agent fails, the orchestrator continues with partial results and notes the gap to the user *(deferred — backend change)*
- [x] Streaming timeout handling — elapsed timer shows "Thinking... Ns" after 5s, "Still thinking... Ns" after 15s
- [x] Mobile responsive chat layout — sidebar overlay drawer on mobile, responsive padding, header text hides on small screens
- [x] Keyboard shortcuts — Enter to send, Shift+Enter for newline (existing), Escape closes mobile sidebar, Cmd/Ctrl+K focuses input
- [x] Typing indicator animation — bouncing dots with elapsed timer
- [x] Markdown rendering in chat messages — `react-markdown` + `remark-gfm` via `MarkdownRenderer` component (bold, italic, lists, links, tables, code blocks, blockquotes)
- [x] Chat message history scroll-to-bottom — smart auto-scroll only when at bottom; floating scroll-to-bottom button when scrolled up
- [x] Accessibility — `role="log"` + `aria-live="polite"` on messages, `role="alert"` on error banner, `role="button"` + keyboard activation (Enter/Space) on sidebar items, `role="dialog"` + `aria-modal` on mobile sidebar, `aria-label` on input/buttons

**New files:** `frontend/components/MarkdownRenderer.tsx`, `frontend/tests/MarkdownRenderer.test.tsx`
**New dependencies:** `react-markdown`, `remark-gfm`
**Tests:** 60 passed (12 test files) — 9 MarkdownRenderer tests, 9 ThreadSidebar tests (added keyboard activation)

---

## Phase 5: Growth & Platform Features (future)

**Sequencing note:** 5.1 (auth) unlocks per-user correctness for 5.2 (share links, ownership checks) and 5.3 (per-user map keys); 5.2 and 5.3 are independent of each other and can run in parallel; 5.4 (PWA) depends on 5.2's read-only thread snapshot only if offline resume is desired; 5.6 (bookings) should land after 5.3 (map) so bookable items render on the map; 5.7 (observability) can start at any time since LangSmith tracing is already wired through langchain.

### Phase 5.1 — Multi-User Auth (Google OAuth) ✅

**Goal:** Replace the client-controlled `X-User-Id` header with real identity. Thread scoping (`chat:{sha256(user_id)[:12]}:...`), `/preferences` memory namespaces, and `/threads` lists become trustworthy per-account data.

**Backend:**
- [x] OAuth 2.0 Google login (Authlib): `/auth/login`, `/auth/callback`, `/auth/logout`, `/auth/me` in `main.py`
- [x] Session management — Redis-backed sessions with HttpOnly cookies (`voyager_session`), 7-day TTL, in-memory fallback when Redis is unavailable
- [x] `get_current_user` FastAPI dependency on `/chat/stream`, `/preferences`, `/threads`, `/threads/{id}/history`, `/threads/{id}`; the verified identity (not the client header) becomes `user_id`
- [x] Dev bypass mode (`AUTH_DEV_BYPASS=1`) returns mock user `dev@localhost` — no Google credentials needed for local development
- [x] `_resolve_user_id` removed — all endpoints use `Depends(get_current_user)`
- [x] `backend/oauth.py` — OAuth client setup, session create/read/delete, `get_current_user` dependency
- [x] New settings: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `OAUTH_REDIRECT_URI`, `SESSION_SECRET_KEY`, `AUTH_DEV_BYPASS`
- [x] New dependencies: `authlib>=1.3.0`, `itsdangerous>=2.1.0`
- [x] `ruff.toml` — ignore B008 (FastAPI `Depends()` in argument defaults is standard pattern)

**Frontend:**
- [x] `frontend/lib/auth.ts` — `getSession()`, `logout()`, `getLoginUrl()` with session caching
- [x] `frontend/app/login/page.tsx` — Google sign-in page with "Sign in with Google" button
- [x] `frontend/app/auth/callback/page.tsx` — OAuth callback handler with Suspense boundary, redirects to `/chat` on success
- [x] `frontend/components/Navbar.tsx` — avatar dropdown (desktop) + mobile menu auth section; shows user name, email, avatar (via `next/image`), Dev badge for dev bypass user; sign in / sign out buttons
- [x] `frontend/lib/chat-api.ts` — removed `X-User-Id` header, added `credentials: 'include'`, 401 → redirect to `/login`
- [x] `frontend/lib/threads-api.ts` — removed `X-User-Id` header, added `credentials: 'include'`, 401 → redirect to `/login`
- [x] `frontend/app/preferences/page.tsx` — removed `X-User-Id` header, added `credentials: 'include'`, auth guard redirects to `/login` if not authenticated
- [x] `frontend/app/chat/page.tsx` — auth guard: checks session on mount, redirects to `/login` if not authenticated, shows spinner while checking
- [x] `frontend/next.config.ts` — added `remotePatterns` for Google avatar URLs (`lh3.googleusercontent.com`)
- [x] `frontend/tests/Navbar.auth.test.tsx` — 3 tests: unauthenticated shows Sign in, authenticated shows user, dev user shows Dev badge

**Tests:** 162 backend tests passed (3 skipped), ruff clean; frontend 63 vitest passed, tsc clean, eslint 0 warnings, production build green.

**Key deepagent features used:** existing thread-scoping + per-user `StoreBackend` namespaces now keyed by verified identity

---

### Phase 5.2 — Itinerary Export & Sharing ✅

**Goal:** Users can export any itinerary as PDF/JSON/Markdown and share a read-only link with anyone.

**Backend:**
- [x] `GET /export/{thread_id}` — exports latest itinerary as JSON or Markdown (`?fmt=json|markdown`); ownership check against session user; `response_model=None` for union return type
- [x] `POST /share/{thread_id}` — creates unguessable share token (`secrets.token_urlsafe(16)`), stored in Redis with 7-day TTL; returns `{share_url, expires_at, destination}`
- [x] `GET /share/{token}` — public read-only JSON of the itinerary; no auth, no agent calls, no state writes; 60/min rate limit
- [x] `DELETE /share/{token}` — revoke a share link (auth required, ownership check); `GET /shares` — list user's active share links
- [x] `backend/share_store.py` — `ShareStore` class with Redis + in-memory fallback (same pattern as `ThreadStore`); `create_share`, `get_share`, `list_shares`, `revoke_share`
- [x] `_itinerary_to_markdown()` helper — converts itinerary dict to readable Markdown with days, costs, warnings, packing essentials
- [x] `_get_latest_itinerary()` helper — extracts latest itinerary from checkpointer state via `_extract_chat_itinerary`
- [x] New setting: `SHARE_TTL_DAYS` (default 7) in `config/settings.py` + `.env.example`
- [x] Tests: 16 tests in `test_sharing.py` — ShareStore unit tests (create, get, expire, revoke, list, cross-user) + endpoint tests (create, get, expire, revoke, list, export JSON, export Markdown, no itinerary 404)

**Frontend:**
- [x] `frontend/components/ItineraryCard.tsx` — extracted shared component with export/share dropdown (Print/PDF, JSON, Markdown, Share link); `printMode` prop for print-optimized rendering
- [x] `frontend/app/export/[threadId]/page.tsx` — print-optimized page that fetches thread history, renders itinerary, triggers `window.print()`; `@media print` CSS in `globals.css`
- [x] `frontend/app/share/[token]/page.tsx` — public share page rendering shared itinerary with "Powered by VoyagerAI" footer; expired link state
- [x] `frontend/lib/share-api.ts` — `createShare`, `getShare`, `revokeShare`, `listShares`, `exportItinerary` with `credentials: 'include'` and 401 redirect
- [x] `frontend/app/chat/ThreadSidebar.tsx` — "Shared Links" collapsible section with copy/revoke buttons and expiry display
- [x] `frontend/app/chat/page.tsx` — imports extracted `ItineraryCard`, passes `threadId` for export/share
- [x] `frontend/app/globals.css` — `@media print` styles (`.print-hidden`, `.print-break-inside-avoid`)
- [x] Tests: `SharePage.test.tsx` (2 tests: valid itinerary, expired), `ShareManagement.test.tsx` (4 tests: empty state, list, count badge, revoke)

**Tests:** 178 backend tests passed (3 skipped), ruff clean; frontend 69 vitest passed, tsc clean, eslint 0 warnings, production build green.

**Key deepagent features used:** checkpointer (fetch itinerary state by thread), Redis for share token storage with TTL

---

### Phase 5.3 — Map Visualization (MapLibre GL) ✅

**Goal:** Every itinerary renders on a map: per-day route lines, activity markers, and a cost-tinted legend.

**Backend:**
- [x] `backend/geocode_cache.py` — Redis-backed cache (180-day TTL) with in-memory fallback; stores `{"lat", "lng"}` per location query, case-insensitive SHA256 key
- [x] `backend/geocode_service.py` — Nominatim geocoding client with process-wide 1.1s throttle lock, 5s timeout, `User-Agent: VoyagerAI/1.0`; never raises (returns None on any failure)
- [x] `backend/agents/deep_agent.py` — `_enrich_itinerary_with_coordinates()` deep-copies itinerary dict, geocodes morning/afternoon/evening locations, attaches `lat`/`lng` to each slot dict; never mutates original, never raises
- [x] Enrichment wired into 4 call sites: `stream_chat_agent` (SSE itinerary event), `create_share_link` (enrich at creation time — immutable snapshot), `export_itinerary` (JSON export includes coords), `get_thread_history` (reloaded threads get coords)
- [x] Fallback chain: missing/failed geocode → slot lacks lat/lng → frontend skips that marker; all-fail → itinerary renders unchanged with no map section
- [x] No API key required (Nominatim + CARTO free tiles); `httpx` added to `requirements.txt`
- [x] Tests: 15 tests in `test_geocoding.py` — GeocodeCache (set/get, miss, case-insensitive), geocode service (cache hit, success, empty results, non-200, exception, empty query, throttle), enrichment (all-geocoded, partial-fail, all-fail, no-mutation, exception-fallback)

**Frontend:**
- [x] `frontend/components/ItineraryMap.tsx` — MapLibre GL with free CARTO Voyager raster tiles; day selector tabs, numbered markers (morning=amber/afternoon=blue/evening=purple), dashed route polyline, popups with activity+cost+"Open in Google Maps" link, auto-fit bounds, legend
- [x] `frontend/components/ItineraryCard.tsx` — collapsible "Map" section (lazy-loaded via `next/dynamic`, `ssr: false`), hidden in print mode (`.print-hidden`)
- [x] `frontend/lib/types.ts` — `TimeSlot` extended with optional `lat`/`lng` fields (backward compatible)
- [x] Marker popups with activity name + estimated cost; "Open in Google Maps" deep link per marker
- [x] Lazy-loaded map assets (code-split via `next/dynamic`) so non-map renders stay fast
- [x] Tests: 5 tests in `ItineraryMap.test.tsx` — day tabs render, unavailable message, day switching, legend content, mixed-coords filtering

**Tests:** 193 backend tests passed (3 skipped), ruff clean; frontend 74 vitest passed, tsc clean, eslint 0 warnings, production build green.

**Key deepagent features used:** itinerary JSON as the single source of truth for both chat cards and map; geocoding enrichment applied post-generation without touching LLM schema or prompts

---

### Phase 5.4 — PWA / Offline Support ✅

**Goal:** Installable app; chat history and last itinerary available offline; queued messages sync when back online.

**Frontend:**
- [x] `@ducanh2912/next-pwa` (Workbox) integrated in `next.config.ts` — `dest: 'public'`, `register: true`, disabled in dev; `turbopack: {}` for Next.js 16 compat; build produces `public/sw.js` + `public/workbox-*.js`
- [x] `frontend/public/manifest.json` — web app manifest (name, icons, theme_color, display: standalone, start_url)
- [x] `frontend/public/icon-192.png`, `frontend/public/icon-512.png` — app icons
- [x] `frontend/app/layout.tsx` — manifest link, `viewport` export with `themeColor`, `appleWebApp` config, icon links
- [x] `frontend/lib/offline-db.ts` — IndexedDB wrapper using `idb`; stores: `threads` (keyPath: thread_id), `history` (out-of-line key: threadId), `queue` (keyPath: id); caches last 10 threads, evicts oldest; all ops fail silently
- [x] `frontend/lib/useOnlineStatus.ts` — hook tracking `navigator.onLine` via `online`/`offline` events
- [x] `frontend/components/OfflineBanner.tsx` — toast banner: amber "You're offline" when offline, blue "sending queued messages" when replaying, green "Back online" for 3s after reconnect; uses ref to detect offline→online transition; `print-hidden`
- [x] `frontend/lib/message-queue.ts` — `queueMessage()` stores in IndexedDB with UUID; `replayQueuedMessages()` sends in order, deletes on success, stops on failure; `getQueuedCount()`
- [x] `frontend/app/chat/page.tsx` — offline detection: if offline, queues message + shows pending UI with clock icon; on reconnect, auto-replays queued messages via `streamChat`; refreshes thread list after replay
- [x] `frontend/lib/threads-api.ts` — write-through caching: `listThreads` upserts to IndexedDB on success, falls back to `getAllCachedThreads()` on network failure; `getThreadHistory` caches on success, falls back to `getCachedThreadHistory()` on failure
- [x] `frontend/components/InstallPrompt.tsx` — custom install button via `beforeinstallprompt` event; dismissible with localStorage persistence (`voyagerai_install_dismissed`); rendered in Navbar
- [x] Tests: `offline-db.test.ts` (9 tests: put/get threads, sort, batch, eviction, history round trip, queue CRUD), `OfflineBanner.test.tsx` (4 tests: offline message, online no-op, replaying, reconnect auto-dismiss), `MessageQueue.test.ts` (6 tests: queue, replay in order, delete on success, stop on failure, stop on exception, empty queue), `InstallPrompt.test.tsx` (4 tests: no render, install button, dismiss + localStorage, dismissed persistence)

**Backend:**
- [x] `backend/models.py` — `ChatRequest` gains optional `client_message_id: str | None` (max 100 chars) for offline message dedup
- [x] `backend/main.py` — `Cache-Control: public, max-age=300` on `GET /threads` and `GET /threads/{thread_id}/history` responses (SSE stream unchanged); `client_message_id` logged in stream endpoint
- [x] Tests: `test_pwa.py` (6 tests: ChatRequest model optional/accepted/max-length/rejects-too-long, cache headers on threads list + history)

**Tests:** 199 backend tests passed (3 skipped), ruff clean; frontend 97 vitest passed, tsc clean, eslint 0 warnings, production build green (sw.js + workbox generated).

**Key deepagent features used:** checkpointer remains server-side truth; PWA caches a read-only mirror in IndexedDB; message queue with idempotency keys for offline→online sync

---

### Phase 5.5 — Multi-Language Support

**Goal:** UI and agent replies in the user's language; itinerary fields localized (currency, units, notes).

**Backend:**
- [x] `Accept-Language` negotiation on `/chat/stream` (body `locale` field takes priority, then `Accept-Language` header, then default); validated against supported-locale allowlist (`en`, `es`, `fr`, `de`, `hi`, `ja`)
- [ ] `Accept-Language` negotiation on `/plan/*` and `/preferences` endpoints
- [x] Chat prompt: inject `<language>` instruction (reply in the user's locale) + `locale` field in itinerary JSON; `_ItineraryDraft` gains optional `locale`/`currency`
- [ ] SSE error/status strings i18n'd (status chips already label from `_parse_chat_event` — move labels to a locale map)
- [x] Tests: locale round-trip integration test (`test_locale_integration.py` — 5 tests: body locale, Accept-Language header, body > header priority, no locale → None, unsupported → None fallback)
- [ ] Tests: locale round-trip with French prose assertion, currency formatting in cost fields

**Frontend:**
- [x] `next-intl` message catalogs for 6 locales (204 keys each, verified by `i18n-audit.test.ts` CI-guard)
- [x] Language switcher in Navbar (`LanguageSwitcher.tsx` with locale flags + names)
- [x] Per-locale currency formatting via `formatCurrency()` using `Intl.NumberFormat` with locale-specific currency (USD/EUR/INR/JPY)
- [x] `formatCurrency()` wired into `ItineraryCard.tsx` (total cost + daily cost) and `ComparisonView.tsx` (plan card headers, cost breakdown, matrix table)
- [x] Locale-prefixed routes (`/en/chat`, `/es/chat`, `/fr/about`, etc.) via `[locale]` dynamic segment + `next-intl/middleware` with `localePrefix: 'always'`
- [x] Non-locale routes (`/auth/callback`, `/export/[threadId]`, `/share/[token]`) excluded from middleware, have own layouts with `getLocale`/`getMessages`
- [x] Navbar/Footer links use locale-prefixed paths via `useLocale()`; `setLocale()` navigates to `/{locale}{pathname}` instead of cookie+reload
- [x] Persist chosen locale in cookie (`NEXT_LOCALE`) + localStorage
- [x] Tests: 113 frontend tests pass (including `i18n-audit.test.ts` with 6 key-completeness tests, `ComparisonView.test.tsx` with locale-formatted currency assertions)
- [ ] Localize chat UI (input placeholder, status chips, error boundary copy, share/export labels) + RTL-aware layout where needed
- [ ] Tests: locale switch re-renders strings, currency format snapshots per locale

**Key deepagent features used:** prompt-level locale injection (agent behavior), no model swap needed

**Verified:** 5 backend locale integration tests pass; 113 frontend tests pass; `tsc` clean; `next build` generates all 6 locale-prefixed routes; translation audit confirms 204 keys match across all 6 catalogs.

---

### Phase 5.6 — Booking API Integration

**Goal:** Itineraries become bookable: hotel/flight/activity deep links (and where feasible, direct booking) with confirmation handling.

**Backend:**
- [ ] Booking providers via SDKs/APIs: hotels + flights (Amadeus or Skyscanner partner), activities (GetYourGuide/Viator); keys in `.env.example` with graceful degradation when unset
- [ ] New `booking_agent` sub-agent: takes the chosen itinerary, searches bookable options per day, returns `{bookings: [{type, provider, item, price_estimate, book_url, booking_id?}]}`; all prices marked approximate with a "prices vary" disclaimer
- [ ] Direct-booking confirmation flow: webhook/callback endpoint + `POST /bookings/{id}/confirm`; store booking state in Redis; refund/cancellation policy surfaced as text only (no payments)
- [ ] Rate-limit provider calls, cache search results with TTL, redact provider keys; tests: provider outage → sub-agent returns partial results with gap noted (reuses 4.6 degradation pattern), booking state transitions

**Frontend:**
- [ ] "Book" button on itinerary cards → expands bookable options (provider, price estimate, deep link); booking status chips (pending / confirmed / cancelled)
- [ ] Confirmation view per booking; link-out fallback when direct booking unsupported

**Key deepagent features used:** `SubAgent` (booking_agent with provider tools), structured output for `bookings`

---

### Phase 5.7 — Agent Observability Dashboard

**Goal:** Per-session trace view (waterfall of sub-agents, tools, model calls), token/cost accounting, and error rates.

**Backend:**
- [ ] LangSmith wiring (already available via langchain): ensure `LANGCHAIN_TRACING_V2` + project env documented; keep traces for chat/plan sessions
- [ ] Aggregated metrics endpoints (read-only, admin-key protected): `GET /observability/usage?from=&to=` (tokens/cost per user per day, from trace exports or a local counter), `GET /observability/errors` (error-event counts by phase), `GET /observability/sessions` (session list with duration + subagent counts)
- [ ] Structured event logging: every SSE event already parsed in `_parse_chat_event` — mirror it to a metrics log; PII redaction (never log raw user messages, only lengths/hashes)
- [ ] Tests: usage aggregation math, error-rate computation, auth guard on admin endpoints

**Frontend:**
- [ ] `frontend/app/observability/page.tsx` (admin-only route): session table → drill-in waterfall (subagent/tool/model steps with durations), token/cost charts per day, error-rate trend
- [ ] Chart lib consistent with the codebase's existing stack (recharts or similar), dark-mode safe

**Key deepagent features used:** `run_name`-based chain events, `astream_events` (already the transport) as the tracing hook

---

### Backlog (not yet scoped)

- Multi-user collaborative trips (invite users to one thread)
- Gamification / prompt-vs-prompt battles (the "PromptWars" angle — head-to-head plan quality scores)
- Multi-modal itinerary (image previews of destinations, AR on the map)
- Voice input for chat
- Mobile native app (React Native wrapper around the SSE API)
