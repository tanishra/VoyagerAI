const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
import { withAuthParams } from './api-headers';
import { clearSessionToken } from './session-token';

export interface SessionUser {
  user_id: string;
  display_name: string;
  avatar_url: string | null;
  email: string;
  is_admin: boolean;
}

let cachedUser: SessionUser | null = null;
let cachedNull = false;
let fetchPromise: Promise<SessionUser | null> | null = null;

export async function getSession(): Promise<SessionUser | null> {
  if (cachedUser) return cachedUser;
  if (cachedNull) return null;

  if (fetchPromise) return fetchPromise;

  fetchPromise = (async () => {
    try {
      // Use a query param (not a custom header) for the session token fallback so this
      // GET request stays a CORS "simple request" and never triggers a preflight OPTIONS —
      // some hosting proxies (e.g. Hugging Face Spaces) intercept OPTIONS and answer it
      // without Access-Control-Allow-Credentials, which would otherwise break this call.
      const res = await fetch(withAuthParams(`${API_URL}/auth/me`), {
        credentials: 'include',
      });
      if (!res.ok) {
        if (res.status === 401) {
          cachedNull = true;
        }
        return null;
      }
      const user = await res.json();
      cachedUser = user;
      return user;
    } catch {
      return null;
    } finally {
      fetchPromise = null;
    }
  })();

  return fetchPromise;
}

export function clearSessionCache() {
  cachedUser = null;
  cachedNull = false;
  fetchPromise = null;
}

export async function logout(): Promise<void> {
  try {
    await fetch(withAuthParams(`${API_URL}/auth/logout`), {
      method: 'POST',
      credentials: 'include',
    });
  } catch {
    // ignore — cookie clearing is the important part
  }
  clearSessionCache();
  clearSessionToken();
}

export function getLoginUrl(): string {
  return `${API_URL}/auth/login`;
}
