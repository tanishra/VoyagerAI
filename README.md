<div align="center">
  <img src="images/banner.svg" alt="VoyagerAI Banner" width="100%">
  <br><br>
  <p>
    <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
    <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI">
    <img src="https://img.shields.io/badge/LiteLLM-Provider_Agnostic-8E75C2?style=for-the-badge" alt="LiteLLM">
    <img src="https://img.shields.io/badge/Next.js-000000?style=for-the-badge&logo=nextdotjs&logoColor=white" alt="Next.js">
    <img src="https://img.shields.io/badge/Tailwind_CSS_v4-38B2AC?style=for-the-badge&logo=tailwindcss&logoColor=white" alt="Tailwind CSS">
    <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License">
  </p>
</div>

**VoyagerAI** is a multi-agent AI travel planning platform. It uses 8 specialized sub-agents working in parallel to research destinations, analyze constraints, detect risks, generate multiple plan variants, self-critique quality, and present interactive itineraries with map visualization — all through a conversational chat interface.

---

## Features

- **Conversational Multi-Agent Planning** — Free-form chat, agent decomposes requests and dispatches sub-agents in parallel (researcher, constraint analyzer, risk detector, quality scorer, and more)
- **Multi-Plan Comparison** — Generates 3 budget tiers (budget / balanced / premium) side-by-side with tradeoff highlights
- **Self-Critique Loop** — Quality scorer evaluates plans against 10 criteria, applies fixes, re-scores (max 2 iterations)
- **Interactive Itinerary Cards** — Day-by-day breakdown with morning/afternoon/evening slots, costs, transport, tips, warnings, packing essentials
- **Map Visualization** — MapLibre GL with per-day route lines, numbered markers, cost popups, and Google Maps deep links
- **Thread Management** — Save, resume, and delete past conversations with AI-generated summaries
- **Memory & Preferences** — Agent remembers user preferences across sessions (dietary, budget, mobility)
- **Export & Sharing** — PDF print view, JSON/Markdown export, shareable read-only links with expiry
- **Multi-Language Support** — 6 languages (English, Spanish, French, German, Hindi, Japanese) with locale-aware currency formatting
- **Google OAuth** — Real authentication with per-user data isolation
- **PWA / Offline** — Installable app, cached thread history, message queueing when offline, auto-sync on reconnect
- **Provider-Agnostic LLM** — Swap between Gemini, OpenAI, Anthropic, etc. via env vars (powered by LiteLLM)

---

## Tech Stack

**Backend:** Python 3.11+, FastAPI, deepagents, LangGraph, LiteLLM, Redis, Tavily, Pydantic

**Frontend:** Next.js 16, React, TypeScript, Tailwind CSS v4, next-intl, MapLibre GL, Framer Motion, PWA (Workbox)

---

## Quick Start

### Prerequisites

- Python 3.11+, Node.js 18+, Redis (optional but recommended)

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Edit .env — set at least one LLM provider API key
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

### 3. Redis (optional)

Without Redis, the app falls back to in-memory storage (no persistence across restarts).

```bash
# macOS
brew install redis-stack-server
redis-stack-server --daemonize yes
```

---

## Configuration

### Backend (`backend/.env`)

See [`backend/.env.example`](backend/.env.example) for all options. Key settings:

| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_API_KEY` | Google Gemini API key | — |
| `LLM_ORCHESTRATOR_MODEL` | LiteLLM model string for orchestrator | `gemini/gemini-2.5-pro` |
| `LLM_SUBAGENT_MODEL` | LiteLLM model string for sub-agents | `gemini/gemini-3.5-flash` |
| `TAVILY_API_KEY` | Tavily search API key (for research sub-agents) | — |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |
| `CHECKPOINTER_BACKEND` | Checkpoint storage: `redis`, `sqlite`, or `memory` | `redis` |
| `AUTH_DEV_BYPASS` | Skip OAuth, use mock user `dev@localhost` | `false` |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID (required for production) | — |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret | — |
| `SESSION_SECRET_KEY` | Session encryption key (change in production!) | `dev-only-insecure-key...` |
| `CORS_ORIGINS` | Comma-separated allowed origins | `http://localhost:3000` |
| `SHARE_TTL_DAYS` | Share link expiry in days | `7` |
| `THREAD_TTL_DAYS` | Thread metadata expiry in days | `30` |

### Frontend (`frontend/.env.local`)

| Variable | Description | Default |
|----------|-------------|---------|
| `NEXT_PUBLIC_API_URL` | Backend API URL | `http://localhost:8000` |

---

## Architecture

```
User Chat Input
    |
    v
FastAPI /chat/stream (SSE)
    |
    v
Orchestrator Agent (deepagents)
    |--- researcher x3 (parallel: hotels, weather, transport)
    |--- constraint_analyzer (budget, dietary, mobility)
    |--- risk_detector (safety, seasonal, transit)
    |--- multi_plan_generator (3 budget tiers)
    |--- quality_scorer (10-criteria self-critique)
    +--- cost_optimizer (per-day allocation)
    |
    v
Structured Itinerary JSON
    |
    v
Next.js Frontend
    |--- Chat UI (streaming tokens + worker status chips)
    |--- ItineraryCard (day-by-day with costs, tips, warnings)
    |--- ComparisonView (side-by-side plan variants)
    |--- ItineraryMap (MapLibre GL markers + routes)
    |--- ThreadSidebar (history, resume, delete)
    +--- Export/Share (PDF, JSON, Markdown, shareable links)
```

---

## Testing

```bash
# Backend (220 tests)
cd backend
python -m pytest

# Frontend (119 tests)
cd frontend
npx vitest run
```

---

## Contribute

PRs and ideas welcome. Open an issue or submit a pull request.
