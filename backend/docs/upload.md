# Upload Endpoint

## Overview

| Method | Path | Auth | Rate Limit | Description |
|--------|------|------|------------|-------------|
| POST | `/upload` | API Key + Session | 10/min | Upload a file for chat attachments |

---

## POST /upload

Upload a file (image or PDF) for use as a chat attachment. Files are stored in Redis with a 1-hour TTL and auto-expire.

### Supported Types

| MIME Type | Extension |
|-----------|-----------|
| `image/jpeg` | .jpg, .jpeg |
| `image/png` | .png |
| `image/webp` | .webp |
| `application/pdf` | .pdf |

**Max size:** 10 MB

### Request Body

`multipart/form-data` with a `file` field.

### curl Example

```bash
curl -X POST http://localhost:8000/upload \
  -H "X-API-Key: your-key" \
  -b "voyager_session=your-session" \
  -F "file=@photo.jpg"
```

### Response

```json
{
  "file_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "data_url": "data:image/jpeg;base64,/9j/4AAQ...",
  "filename": "photo.jpg",
  "content_type": "image/jpeg",
  "size": 102400
}
```

### Error Responses

| Status | Description |
|--------|-------------|
| 400 | Empty file |
| 413 | File too large (max 10MB) |
| 415 | Unsupported file type or extension |
