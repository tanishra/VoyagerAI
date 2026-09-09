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

Redirect to Google OAuth consent screen. In development mode (`AUTH_DEV_BYPASS=true`), creates a dev session and redirects directly.

### curl Example

```bash
curl -L http://localhost:8000/auth/login
```

### Response

302 redirect to Google OAuth (or frontend callback in dev mode).

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

### curl Example

```bash
curl -X POST http://localhost:8000/auth/logout \
  -b "voyager_session=your-session"
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
