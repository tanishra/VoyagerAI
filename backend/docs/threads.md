# Thread Endpoints

## Overview

| Method | Path | Auth | Rate Limit | Description |
|--------|------|------|------------|-------------|
| GET | `/threads` | API Key + Session | 30/min | List user's recent threads |
| GET | `/threads/search` | API Key + Session | 30/min | Search across thread messages |
| GET | `/threads/{thread_id}/history` | API Key + Session | 30/min | Get thread message history |
| GET | `/threads/{thread_id}/branches` | API Key + Session | 30/min | List branches for last response |
| DELETE | `/threads/{thread_id}` | API Key + Session | 30/min | Delete a thread |
| PATCH | `/threads/{thread_id}` | API Key + Session | 30/min | Update thread metadata |

---

## GET /threads

List the user's recent conversation threads. Sorted: pinned first, then by updated_at desc.

### Query Parameters

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `offset` | int | 0 | Pagination offset |
| `limit` | int | 20 | Page size |

### curl Example

```bash
curl http://localhost:8000/threads?offset=0&limit=20 \
  -H "X-API-Key: your-key" \
  -b "voyager_session=your-session"
```

### Response

```json
{
  "threads": [
    {
      "thread_id": "chat:abc123:def456",
      "summary": "Paris trip plan",
      "created_at": 1735689600,
      "updated_at": 1735693200,
      "status": "idle",
      "message_count": 4,
      "search_text": "",
      "pinned": false,
      "pinned_at": 0
    }
  ],
  "has_more": false
}
```

---

## GET /threads/search

Full-text search across all user's thread message content.

### Query Parameters

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `q` | string | "" | Search query |
| `offset` | int | 0 | Pagination offset |
| `limit` | int | 20 | Page size |

### curl Example

```bash
curl "http://localhost:8000/threads/search?q=paris&limit=10" \
  -H "X-API-Key: your-key" \
  -b "voyager_session=your-session"
```

### Response

```json
{
  "results": [
    {
      "thread_id": "chat:abc123:def456",
      "summary": "Paris trip",
      "snippet": "...Eiffel Tower...",
      "created_at": 1735689600
    }
  ],
  "total": 1,
  "has_more": false
}
```

---

## GET /threads/{thread_id}/history

Get the full message history for a thread. Assistant messages may include `itinerary`, `comparison`, `activity`, `images`, and `charts` fields.

### Path Parameters

| Param | Description |
|-------|-------------|
| `thread_id` | Thread ID to fetch history for |

### Query Parameters

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `checkpoint_id` | string | null | Optional checkpoint ID for a specific version |

### curl Example

```bash
curl http://localhost:8000/threads/chat:abc123:def456/history \
  -H "X-API-Key: your-key" \
  -b "voyager_session=your-session"
```

### Response

```json
[
  {
    "role": "user",
    "content": "Plan a trip to Paris"
  },
  {
    "role": "assistant",
    "content": "Here's a 3-day Paris itinerary...",
    "itinerary": {
      "destination": "Paris",
      "total_days": 3,
      "estimated_total_cost_usd": 1500
    }
  }
]
```

### Error Responses

| Status | Description |
|--------|-------------|
| 403 | Thread does not belong to this user |
| 404 | Thread not found or empty |
| 503 | Failed to load thread history |

---

## GET /threads/{thread_id}/branches

List all branches (alternative responses) from the last assistant response's fork point.

### curl Example

```bash
curl http://localhost:8000/threads/chat:abc123:def456/branches \
  -H "X-API-Key: your-key" \
  -b "voyager_session=your-session"
```

### Response

```json
{
  "branches": [
    {
      "checkpoint_id": "abc-123",
      "is_current": true,
      "preview": "Here's a 3-day Paris itinerary..."
    },
    {
      "checkpoint_id": "def-456",
      "is_current": false,
      "preview": "Sure! Let me plan a trip to Paris..."
    }
  ]
}
```

---

## DELETE /threads/{thread_id}

Delete a thread and its underlying checkpoint state.

### curl Example

```bash
curl -X DELETE http://localhost:8000/threads/chat:abc123:def456 \
  -H "X-API-Key: your-key" \
  -b "voyager_session=your-session"
```

### Response

```json
{
  "status": "ok",
  "thread_id": "chat:abc123:def456"
}
```

### Error Responses

| Status | Description |
|--------|-------------|
| 403 | Thread does not belong to this user |
| 404 | Thread not found |

---

## PATCH /threads/{thread_id}

Update thread metadata (e.g., pin or unpin a thread).

### Request Body

```json
{
  "pinned": true
}
```

### curl Example

```bash
curl -X PATCH http://localhost:8000/threads/chat:abc123:def456 \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -b "voyager_session=your-session" \
  -d '{"pinned": true}'
```

### Response

```json
{
  "status": "ok",
  "thread_id": "chat:abc123:def456"
}
```
