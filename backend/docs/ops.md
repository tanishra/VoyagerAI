# Ops Endpoint

## Overview

| Method | Path | Auth | Rate Limit | Description |
|--------|------|------|------------|-------------|
| GET | `/health` | None | Default | Health check |

---

## GET /health

Check if the backend and Redis are healthy. No authentication required — used by load balancers and monitoring.

### curl Example

```bash
curl http://localhost:8000/health
```

### Response (healthy)

```json
{
  "status": "ok",
  "redis": "connected",
  "agent": "deepagent"
}
```

### Response (degraded)

```json
{
  "status": "degraded",
  "redis": "unavailable",
  "agent": "deepagent"
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | "ok" if Redis is connected, "degraded" otherwise |
| `redis` | string | "connected" or "unavailable" |
| `agent` | string | Always "deepagent" (identifies the agent framework) |
