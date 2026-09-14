# VoyagerAI Deployment Guide

## Prerequisites

- **Docker** 24+ ([install](https://docs.docker.com/get-docker/))
- **Docker Compose** v2+ (included with Docker Desktop)
- **API Keys**: Gemini API key, Tavily API key (see `backend/.env.example`)

---

## Quick Start

### 1. Configure environment

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env` and fill in required values:

```env
GEMINI_API_KEY=your-key-here
TAVILY_API_KEY=your-key-here
CORS_ORIGINS=http://localhost:3000
SESSION_SECRET_KEY=generate-a-strong-random-string
```

### 2. Start the stack

```bash
docker compose up -d
```

This starts three services:
- **Redis** on port 6379 (internal + exposed)
- **Backend** (FastAPI/Uvicorn) on port 8000
- **Frontend** (Next.js) on port 3000

### 3. Verify

```bash
# Backend health check
curl http://localhost:8000/health
# Expected: {"status":"ok","redis":"connected","agent":"deepagent"}

# Frontend
open http://localhost:3000
```

Check service status:
```bash
docker compose ps
```

---

## Common Operations

### View logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f backend
```

### Stop the stack

```bash
docker compose down
```

### Stop and remove volumes (⚠️ deletes all data)

```bash
docker compose down -v
```

### Rebuild after code changes

```bash
docker compose up -d --build
```

### Run backend tests inside container

```bash
docker compose exec backend python -m pytest tests/ -v
```

---

## Data Persistence

| Volume | Mount Point | Purpose |
|---|---|---|
| `redis-data` | `/data` (Redis container) | Redis data (threads, sessions, costs, etc.) |
| `backend-data` | `/app/data` (Backend container) | SQLite fallback DB (`stores.sqlite`, `checkpoints.sqlite`) |

Data persists across `docker compose down` + `docker compose up -d`.
Use `docker compose down -v` only if you want to wipe all data.

---

## Production Deployment

### Environment checklist

Before deploying to production, set these in `backend/.env`:

```env
AUTH_MODE=production
SESSION_SECRET_KEY=<strong-random-string>
CORS_ORIGINS=https://your-domain.com
GOOGLE_CLIENT_ID=<your-oauth-client-id>
GOOGLE_CLIENT_SECRET=<your-oauth-client-secret>
OAUTH_REDIRECT_URI=https://your-domain.com/auth/callback
ADMIN_EMAILS=admin@your-domain.com
```

### Frontend API URL

`NEXT_PUBLIC_API_URL` is a **build-time** variable in Next.js. To point the frontend at a different backend URL:

```bash
# In frontend/Dockerfile, the default is:
ENV NEXT_PUBLIC_API_URL=http://localhost:8000

# For production, rebuild with your domain:
docker compose build --build-arg NEXT_PUBLIC_API_URL=https://api.your-domain.com frontend
```

Or set it in `docker-compose.yml` under the `frontend.build.args` section.

### Scaling

- **Single server**: The current setup works as-is. Redis and SQLite fallback handle persistence.
- **Multi-server**: Use an external Redis (e.g., Redis Cloud, AWS ElastiCache). Remove the `redis` service from compose and set `REDIS_URL` to the external endpoint. SQLite fallback is single-server only — disable it by ensuring Redis is always available.
- **Horizontal scaling**: Scale the `backend` service with `docker compose up -d --scale backend=3`. Ensure Redis is external (not in compose) for multi-node.

---

## Troubleshooting

### Backend can't connect to Redis

```bash
docker compose logs backend | grep -i redis
```

Ensure Redis is healthy: `docker compose ps redis`. The backend waits for Redis to be healthy before starting (`depends_on: condition: service_healthy`).

### CORS errors in browser

Ensure `CORS_ORIGINS` in `backend/.env` includes your frontend URL (e.g., `http://localhost:3000`).

### Frontend can't reach backend

`NEXT_PUBLIC_API_URL` must be a URL accessible from the **browser** (not Docker's internal network). For local development, `http://localhost:8000` works. For production, use your public backend URL.

### Port already in use

Change the host port mapping in `docker-compose.yml`:
```yaml
ports:
  - "8001:8000"  # host:container
```

### Health check failing

```bash
# Check backend health
docker compose exec backend python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/health').read())"

# Check frontend
docker compose exec frontend wget -qO- http://localhost:3000/
```

## Dependency Management

### Backend lockfile (`requirements.lock.txt`)

The backend uses a pinned lockfile for reproducible Docker builds:

- **`requirements.txt`** is the source of truth (human-edited, loose ranges).
- **`requirements.lock.txt`** is the build artifact (exact versions, generated).
- The Dockerfile installs from `requirements.lock.txt` to ensure identical deps across builds.

**Regenerating the lockfile after bumping a dependency:**

```bash
# Create a clean venv to avoid capturing dev/local packages
python3.12 -m venv /tmp/lockfile-venv
/tmp/lockfile-venv/bin/pip install -r backend/requirements.txt
/tmp/lockfile-venv/bin/pip freeze | sort > backend/requirements.lock.txt
rm -rf /tmp/lockfile-venv

# Verify no known vulnerabilities
pip-audit -r backend/requirements.lock.txt
```

### Frontend npm audit

All npm vulnerabilities have been resolved (0 critical, 0 high, 0 moderate, 0 low):

- **`serialize-javascript`**: Forced to `^7.0.5` via `overrides` in `package.json`. This is a build-time-only dependency (webpack/workbox plugin), not shipped in the runtime bundle. Upstream `@ducanh2912/next-pwa` hasn't released a fix yet, so the override is the correct interim measure.
- **`sharp`**: Resolved via `npm audit fix` (transitive dep of Next.js).
- **`vitest`/`vite`/`undici`**: Upgraded to latest versions to fix dev-dependency vulnerabilities.

### CI/CD pipeline

GitHub Actions (`.github/workflows/ci.yml`) runs on every PR and push to `main`:

- **Backend job**: Redis service container, `ruff check`, `pytest tests/ -v`.
- **Frontend job**: `tsc --noEmit`, `eslint`, `vitest run`, `next build`.
- **Audit job**: `pip-audit` + `npm audit --production` (informational, non-blocking).
