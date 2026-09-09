# Chat Endpoints

## Overview

| Method | Path | Auth | Rate Limit | Description |
|--------|------|------|------------|-------------|
| POST | `/chat/stream` | API Key + Session | 20/min | Stream a chat conversation |
| POST | `/chat/cancel` | API Key + Session | 30/min | Cancel an active stream |
| POST | `/chat/regenerate` | API Key + Session | 30/min | Regenerate last response |
| POST | `/chat/edit` | API Key + Session | 30/min | Edit last user message and regenerate |

---

## POST /chat/stream

Stream a chat conversation with the travel agent. Returns Server-Sent Events (SSE).

### Request Body

```json
{
  "message": "Plan a 3-day trip to Paris",
  "thread_id": null,
  "client_message_id": null,
  "locale": "en",
  "timezone": "Asia/Kolkata",
  "attachments": []
}
```

### curl Example

```bash
curl -N -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -b "voyager_session=your-session" \
  -d '{"message": "Plan a 3-day trip to Paris"}'
```

### SSE Event Types

| Event | Data | Description |
|-------|------|-------------|
| `thread_id` | `{"thread_id": "chat:abc123:def456"}` | Thread ID for the conversation |
| `status` | `{"tool": "research", "status": "thinking"}` | Subagent status updates |
| `token` | `"Hello"` | Streamed LLM text chunks |
| `itinerary` | `{...}` | Structured itinerary data |
| `comparison` | `{...}` | Comparison data |
| `image` | `{...}` | Generated image |
| `chart` | `{...}` | Chart data |
| `usage` | `{"input_tokens": 500, "output_tokens": 200, "model": "gpt-4o"}` | Token usage stats |
| `tool_error` | `{"name": "research", "error": "..."}` | Tool execution errors |
| `subagent_progress` | `{...}` | Subagent progress updates |
| `cancelled` | `null` | Stream cancelled by user |
| `error` | `"Error message"` | Stream errors |
| `done` | `null` | Stream complete |

### Error Responses

| Status | Description |
|--------|-------------|
| 400 | Prompt injection detected — request blocked |
| 401 | Missing or invalid API key |
| 429 | Rate limit exceeded or user in cooldown |

---

## POST /chat/cancel

Cancel an active chat stream.

### Request Body

```json
{
  "thread_id": "chat:abc123:def456"
}
```

### curl Example

```bash
curl -X POST http://localhost:8000/chat/cancel \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -b "voyager_session=your-session" \
  -d '{"thread_id": "chat:abc123:def456"}'
```

### Response

```json
{
  "cancelled": true
}
```

---

## POST /chat/regenerate

Regenerate the last assistant response for a thread. Returns SSE stream.

### Request Body

```json
{
  "thread_id": "chat:abc123:def456",
  "locale": "en",
  "timezone": "Asia/Kolkata"
}
```

### curl Example

```bash
curl -N -X POST http://localhost:8000/chat/regenerate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -b "voyager_session=your-session" \
  -d '{"thread_id": "chat:abc123:def456"}'
```

### SSE Event Types

Same as `/chat/stream` — see above.

---

## POST /chat/edit

Edit the last user message and regenerate the assistant response. Returns SSE stream.

### Request Body

```json
{
  "thread_id": "chat:abc123:def456",
  "message": "Plan a 5-day trip to Paris instead",
  "locale": "en",
  "timezone": "Asia/Kolkata"
}
```

### curl Example

```bash
curl -N -X POST http://localhost:8000/chat/edit \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -b "voyager_session=your-session" \
  -d '{"thread_id": "chat:abc123:def456", "message": "Plan a 5-day trip to Paris instead"}'
```

### SSE Event Types

Same as `/chat/stream` — see above.
