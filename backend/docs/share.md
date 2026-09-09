# Share Endpoints

## Overview

| Method | Path | Auth | Rate Limit | Description |
|--------|------|------|------------|-------------|
| POST | `/share/{thread_id}` | API Key + Session | 10/min | Create a shareable link |
| GET | `/share/{token}` | None (public) | 60/min | Get shared itinerary |
| DELETE | `/share/{token}` | API Key + Session | 20/min | Revoke a share link |
| GET | `/shares` | API Key + Session | 30/min | List user's share links |

---

## POST /share/{thread_id}

Create a shareable link for an itinerary. The itinerary is enriched with coordinates and stored with a token.

### Path Parameters

| Param | Description |
|-------|-------------|
| `thread_id` | Thread containing the itinerary to share |

### curl Example

```bash
curl -X POST http://localhost:8000/share/chat:abc123:def456 \
  -H "X-API-Key: your-key" \
  -b "voyager_session=your-session"
```

### Response

```json
{
  "share_url": "http://localhost:3000/en/share/abc123def456",
  "expires_at": 1736294400,
  "destination": "Paris"
}
```

### Error Responses

| Status | Description |
|--------|-------------|
| 404 | No itinerary found in this thread |

---

## GET /share/{token}

Get a shared itinerary by token. **Public endpoint — no authentication required.**

### Path Parameters

| Param | Description |
|-------|-------------|
| `token` | Share token from the URL |

### curl Example

```bash
curl http://localhost:8000/share/abc123def456
```

### Response

```json
{
  "itinerary": {
    "destination": "Paris",
    "total_days": 3,
    "estimated_total_cost_usd": 1500,
    "days": [...]
  },
  "destination": "Paris",
  "created_at": 1735689600,
  "expires_at": 1736294400
}
```

### Error Responses

| Status | Description |
|--------|-------------|
| 404 | Share link not found or expired |
| 500 | Corrupted share data |

---

## DELETE /share/{token}

Revoke a share link. Only the original creator can revoke.

### curl Example

```bash
curl -X DELETE http://localhost:8000/share/abc123def456 \
  -H "X-API-Key: your-key" \
  -b "voyager_session=your-session"
```

### Response

```json
{
  "status": "ok"
}
```

### Error Responses

| Status | Description |
|--------|-------------|
| 404 | Share link not found |

---

## GET /shares

List all active share links for the current user. Expired shares are automatically filtered out.

### curl Example

```bash
curl http://localhost:8000/shares \
  -H "X-API-Key: your-key" \
  -b "voyager_session=your-session"
```

### Response

```json
[
  {
    "token": "abc123def456",
    "thread_id": "chat:abc123:def456",
    "destination": "Paris",
    "created_at": 1735689600,
    "expires_at": 1736294400,
    "share_url": "http://localhost:3000/share/abc123def456"
  }
]
```
