# Export Endpoint

## Overview

| Method | Path | Auth | Rate Limit | Description |
|--------|------|------|------------|-------------|
| GET | `/export/{thread_id}` | API Key + Session | 10/min | Export itinerary as JSON, Markdown, or iCal |

---

## GET /export/{thread_id}

Export an itinerary in JSON, Markdown, or iCal format. Returns a file download with appropriate `Content-Type` and `Content-Disposition` headers.

### Path Parameters

| Param | Description |
|-------|-------------|
| `thread_id` | Thread containing the itinerary |

### Query Parameters

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `fmt` | string | "json" | Export format: "json", "markdown", or "ical" |

### curl Examples

**JSON:**
```bash
curl -L http://localhost:8000/export/chat:abc123:def456?fmt=json \
  -H "X-API-Key: your-key" \
  -b "voyager_session=your-session" \
  -o paris.json
```

**Markdown:**
```bash
curl -L http://localhost:8000/export/chat:abc123:def456?fmt=markdown \
  -H "X-API-Key: your-key" \
  -b "voyager_session=your-session" \
  -o paris.md
```

**iCal:**
```bash
curl -L http://localhost:8000/export/chat:abc123:def456?fmt=ical \
  -H "X-API-Key: your-key" \
  -b "voyager_session=your-session" \
  -o paris.ics
```

### Response Content Types

| Format | Content-Type | Filename |
|--------|-------------|----------|
| json | `application/json` | `{destination}.json` |
| markdown | `text/markdown` | `{destination}.md` |
| ical | `text/calendar` | `{destination}.ics` |

### Error Responses

| Status | Description |
|--------|-------------|
| 404 | No itinerary found in this thread |
