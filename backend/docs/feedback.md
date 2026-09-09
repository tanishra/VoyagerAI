# Feedback Endpoint

## Overview

| Method | Path | Auth | Rate Limit | Description |
|--------|------|------|------------|-------------|
| POST | `/feedback` | API Key + Session | 30/min | Submit thumbs up/down feedback |

---

## POST /feedback

Submit or update thumbs up/down feedback for a specific message. One rating per user per message — submitting again overwrites the previous rating.

### Request Body

```json
{
  "thread_id": "chat:abc123:def456",
  "message_id": "msg-789",
  "rating": "up",
  "comment": "Great itinerary!"
}
```

### Field Constraints

| Field | Type | Required | Constraints |
|-------|------|----------|------------|
| `thread_id` | string | Yes | max 200 chars |
| `message_id` | string | Yes | max 200 chars |
| `rating` | string | Yes | "up" or "down" |
| `comment` | string | No | max 1000 chars |

### curl Example

```bash
curl -X POST http://localhost:8000/feedback \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -b "voyager_session=your-session" \
  -d '{
    "thread_id": "chat:abc123:def456",
    "message_id": "msg-789",
    "rating": "up",
    "comment": "Great itinerary!"
  }'
```

### Response

```json
{
  "status": "ok",
  "rating": "up"
}
```
