# Auth Endpoints

## Overview

| Method | Path | Auth | Rate Limit | Description |
|--------|------|------|------------|-------------|
| GET | `/auth/login` | None | Default | Start Google OAuth login |
| GET | `/auth/callback` | None | Default | Handle OAuth callback |
| POST | `/auth/logout` | None | Default | Logout and clear session |
| GET | `/auth/me` | Session | Default | Get current user info |

---

## GET /auth/login

Redirect to Google OAuth consent screen. Always redirects to Google OAuth — no dev bypass.

### curl Example

```bash
curl -L http://localhost:8000/auth/login
```

### Response

302 redirect to Google OAuth.

---

## GET /auth/callback

Handle Google OAuth callback — exchanges the authorization code for user info and creates a session.

### Response

302 redirect to `http://localhost:3000/auth/callback?success=1` with `Set-Cookie` header containing the session cookie.

### Error Responses

| Status | Description |
|--------|-------------|
| 400 | No email in Google response |

---

## POST /auth/logout

Clear the session cookie and delete the session from Redis. No authentication required.

> **CSRF Protection:** This endpoint requires a valid `X-CSRF-Token` header matching the `voyager_csrf` cookie.

### curl Example

```bash
curl -X POST http://localhost:8000/auth/logout \
  -b "voyager_session=your-session; voyager_csrf=your-csrf-token" \
  -H "X-CSRF-Token: your-csrf-token"
```

### Response

```json
{
  "status": "ok"
}
```

---

## GET /auth/me

Return current user info from the session.

### curl Example

```bash
curl http://localhost:8000/auth/me \
  -b "voyager_session=your-session"
```

### Response

```json
{
  "user_id": "user@example.com",
  "display_name": "Jane Doe",
  "avatar_url": "https://lh3.googleusercontent.com/...",
  "email": "user@example.com"
}
```

### Error Responses

| Status | Description |
|--------|-------------|
| 401 | Not authenticated |

---

## Security Hardening (Phase 7.1)

### CSRF Protection

All mutation requests (POST, PUT, PATCH, DELETE) require a valid CSRF token using the **double-submit cookie** pattern:

1. The server sets a `voyager_csrf` cookie (non-HttpOnly, so frontend JS can read it).
2. The frontend reads the cookie and sends its value as the `X-CSRF-Token` header.
3. The server compares the cookie value to the header value using `hmac.compare_digest`.
4. If they match, the request is allowed. If not, a 403 is returned.

**Exempt endpoints:** `/chat/stream`, `/chat/regenerate`, `/chat/edit` (SSE endpoints), `/auth/callback`.

### Startup Guards

In production mode (`AUTH_MODE=production`), the app refuses to start if:
- `SESSION_SECRET_KEY` is the default value or empty.
- `API_AUTH_KEY` is not set.
- `GOOGLE_CLIENT_ID` or `GOOGLE_CLIENT_SECRET` is not set.

### Secure Cookie Flags

In production mode, both the session cookie and CSRF cookie are set with `secure=True`.

### Input Length Validation

Endpoints accepting `body: dict` validate string field lengths:
- `thread_id`: max 200 characters
- `message`: max 2000 characters
- `locale`: max 10 characters
- `timezone`: max 50 characters
