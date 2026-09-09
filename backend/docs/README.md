# VoyagerAI Backend API Documentation

Comprehensive documentation for all 32 backend API endpoints across 9 tag groups.

## Quick Links

| Tag | File | Endpoints |
|-----|------|-----------|
| chat | [chat.md](chat.md) | `/chat/stream`, `/chat/cancel`, `/chat/regenerate`, `/chat/edit` |
| threads | [threads.md](threads.md) | `/threads`, `/threads/search`, `/threads/{id}/history`, `/threads/{id}/branches`, `DELETE /threads/{id}`, `PATCH /threads/{id}` |
| preferences | [preferences.md](preferences.md) | `GET /preferences`, `PUT /preferences` |
| auth | [auth.md](auth.md) | `/auth/login`, `/auth/callback`, `/auth/logout`, `/auth/me` |
| share | [share.md](share.md) | `POST /share/{thread_id}`, `GET /share/{token}`, `DELETE /share/{token}`, `GET /shares` |
| export | [export.md](export.md) | `GET /export/{thread_id}` |
| upload | [upload.md](upload.md) | `POST /upload` |
| feedback | [feedback.md](feedback.md) | `POST /feedback` |
| admin | [admin.md](admin.md) | `/admin/costs`, `/admin/costs/threads/{id}`, `/admin/costs/export`, `/admin/feedback`, `/admin/cache/research`, `/admin/security/flags`, `/admin/security/cooldowns`, `DELETE /admin/security/cooldowns/{user_hash}` |
| ops | [ops.md](ops.md) | `/health` |

## Authentication

### API Key (`X-API-Key` header)

Most endpoints require an `X-API-Key` header. In development mode (`AUTH_MODE=development`), this is a no-op. In production (`AUTH_MODE=production`), the header must match `API_AUTH_KEY`.

### Session Cookie

User-authenticated endpoints require a valid session cookie set by `/auth/login` → `/auth/callback`. The cookie name is `voyager_session`.

### Admin Endpoints

Admin endpoints additionally require the user's email to be in the `ADMIN_EMAILS` allowlist.

## Rate Limiting

All endpoints are rate-limited via slowapi. Default: 30 requests/hour. Individual limits:

| Endpoint | Rate Limit |
|----------|-----------|
| `/chat/stream` | 20/minute |
| `/chat/cancel`, `/chat/regenerate`, `/chat/edit` | 30/minute |
| `/upload` | 10/minute |
| `/admin/costs` | 10/minute |
| `/admin/costs/export` | 5/minute |
| `/admin/cache/research` | 5/minute |
| `/admin/security/*` | 10/minute |
| `/share/{thread_id}` | 10/minute |
| `/share/{token}` | 60/minute |
| `/export/{thread_id}` | 10/minute |

## Interactive Docs

- **Swagger UI**: `GET /docs` (open in dev, admin-only in production)
- **ReDoc**: `GET /redoc` (open in dev, admin-only in production)
- **OpenAPI JSON**: `GET /openapi.json` (open in dev, admin-only in production)

## Static OpenAPI Export

On every backend startup, the OpenAPI schema is exported to `backend/static/openapi.json`. This file can be consumed by the frontend or other tools.
