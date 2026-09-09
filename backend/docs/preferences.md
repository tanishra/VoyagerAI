# Preferences Endpoints

## Overview

| Method | Path | Auth | Rate Limit | Description |
|--------|------|------|------------|-------------|
| GET | `/preferences` | API Key + Session | 30/min | Get user preferences (Markdown) |
| PUT | `/preferences` | API Key + Session | 30/min | Save user preferences (Markdown) |

---

## GET /preferences

Get the current user's preferences as Markdown text. Returns `text/plain` content type.

### curl Example

```bash
curl http://localhost:8000/preferences \
  -H "X-API-Key: your-key" \
  -b "voyager_session=your-session"
```

### Response

```
<user_instructions>
I prefer budget travel and local cuisine.
</user_instructions>
```

### Error Responses

| Status | Description |
|--------|-------------|
| 503 | Preferences store unavailable |

---

## PUT /preferences

Save user preferences as raw Markdown text (not JSON). XML-like tags in the `<user_instructions>` section are stripped for safety.

### Request Body

Raw Markdown text (not JSON). Sent as the raw request body.

### curl Example

```bash
curl -X PUT http://localhost:8000/preferences \
  -H "Content-Type: text/plain" \
  -H "X-API-Key: your-key" \
  -b "voyager_session=your-session" \
  -d '<user_instructions>I prefer budget travel.</user_instructions>'
```

### Response

```json
{
  "status": "ok",
  "user_id": "user@example.com"
}
```

### Error Responses

| Status | Description |
|--------|-------------|
| 503 | Preferences store unavailable |
