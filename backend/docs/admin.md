# Admin Endpoints

## Overview

All admin endpoints require:
1. Valid `X-API-Key` header (production mode)
2. Valid session cookie
3. User must be in the `ADMIN_EMAILS` allowlist

| Method | Path | Rate Limit | Description |
|--------|------|------------|-------------|
| GET | `/admin/costs` | 10/min | Aggregate cost analytics |
| GET | `/admin/costs/threads/{thread_id}` | 30/min | Per-subagent cost breakdown |
| GET | `/admin/costs/export` | 5/min | Export costs as CSV |
| GET | `/admin/feedback` | 10/min | Aggregate feedback stats |
| DELETE | `/admin/cache/research` | 5/min | Invalidate research cache |
| GET | `/admin/security/flags` | 10/min | Security flag stats |
| GET | `/admin/security/cooldowns` | 10/min | Active cooldowns |
| DELETE | `/admin/security/cooldowns/{user_hash}` | 10/min | Remove a cooldown |

---

## GET /admin/costs

Get aggregate cost analytics for a time period.

### Query Parameters

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `period` | string | "week" | "day", "week", or "month" |

### curl Example

```bash
curl "http://localhost:8000/admin/costs?period=week" \
  -H "X-API-Key: your-key" \
  -b "voyager_session=your-admin-session"
```

### Response

```json
{
  "total_cost": 12.34,
  "total_conversations": 42,
  "avg_cost_per_conversation": 0.29,
  "total_input_tokens": 150000,
  "total_output_tokens": 80000,
  "per_day": [{"date": "2026-09-08", "cost": 2.5}],
  "per_subagent": [{"name": "research", "cost": 5.0, "input_tokens": 20000, "output_tokens": 10000}],
  "top_users": [{"user_id": "user@example.com", "cost": 3.5}],
  "poor_efficiency_sessions": []
}
```

---

## GET /admin/costs/threads/{thread_id}

Get per-subagent cost breakdown for a specific conversation.

### curl Example

```bash
curl http://localhost:8000/admin/costs/threads/chat:abc123:def456 \
  -H "X-API-Key: your-key" \
  -b "voyager_session=your-admin-session"
```

### Response

```json
{
  "session": {
    "thread_id": "chat:abc123:def456",
    "total_cost_usd": 0.15,
    "total_input_tokens": 5000,
    "total_output_tokens": 2000
  },
  "subagents": {
    "research": {"cost": 0.08, "input_tokens": 3000, "output_tokens": 1000}
  }
}
```

---

## GET /admin/costs/export

Export all cost records as a CSV file.

### curl Example

```bash
curl -L http://localhost:8000/admin/costs/export \
  -H "X-API-Key: your-key" \
  -b "voyager_session=your-admin-session" \
  -o costs.csv
```

### Response

CSV file with `Content-Disposition: attachment; filename=costs.csv`.

---

## GET /admin/feedback

Get aggregate feedback statistics.

### curl Example

```bash
curl http://localhost:8000/admin/feedback \
  -H "X-API-Key: your-key" \
  -b "voyager_session=your-admin-session"
```

### Response

```json
{
  "total_up": 120,
  "total_down": 15,
  "total_ratings": 135,
  "satisfaction_ratio": 0.889,
  "recent_comments": [
    {
      "comment": "The itinerary was too rushed",
      "thread_id": "chat:abc123:def456",
      "created_at": 1735689600
    }
  ]
}
```

---

## DELETE /admin/cache/research

Clear all cached Tavily search results. Forces fresh research on subsequent chat requests.

### curl Example

```bash
curl -X DELETE http://localhost:8000/admin/cache/research \
  -H "X-API-Key: your-key" \
  -b "voyager_session=your-admin-session"
```

### Response

```json
{
  "status": "ok",
  "cleared": 42
}
```

---

## GET /admin/security/flags

Get aggregate prompt injection flag statistics.

### Query Parameters

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `period` | string | "week" | "day", "week", or "month" |

### curl Example

```bash
curl "http://localhost:8000/admin/security/flags?period=week" \
  -H "X-API-Key: your-key" \
  -b "voyager_session=your-admin-session"
```

### Response

```json
{
  "total_flags": 5,
  "by_category": {"instruction_override": 3, "extraction_attempt": 2},
  "by_source": {"message": 4, "pdf": 1},
  "by_confidence": {"high": 3, "low": 2},
  "unique_users": 2,
  "active_cooldowns": 1,
  "recent_flags": []
}
```

---

## GET /admin/security/cooldowns

Get all currently active injection cooldowns.

### curl Example

```bash
curl http://localhost:8000/admin/security/cooldowns \
  -H "X-API-Key: your-key" \
  -b "voyager_session=your-admin-session"
```

### Response

```json
{
  "cooldowns": [
    {
      "user_hash": "abc123def456",
      "until": 1735689600,
      "remaining_seconds": 3600
    }
  ],
  "count": 1
}
```

---

## DELETE /admin/security/cooldowns/{user_hash}

Manually remove a cooldown for a user (in case of false-positive lockout).

### Path Parameters

| Param | Description |
|-------|-------------|
| `user_hash` | Hashed user ID (12-char SHA256 prefix) to unblock |

### curl Example

```bash
curl -X DELETE http://localhost:8000/admin/security/cooldowns/abc123def456 \
  -H "X-API-Key: your-key" \
  -b "voyager_session=your-admin-session"
```

### Response

```json
{
  "status": "ok",
  "user_hash": "abc123def456"
}
```

If no cooldown exists for the user hash, `status` will be `"not_found"`.
