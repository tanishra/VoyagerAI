const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface SessionUser {
  user_id: string;
  display_name: string;
  avatar_url: string | null;
  email: string;
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
      const res = await fetch(`${API_URL}/auth/me`, { credentials: 'include' });
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
    await fetch(`${API_URL}/auth/logout`, {
      method: 'POST',
      credentials: 'include',
    });
  } catch {
    // ignore — cookie clearing is the important part
  }
  clearSessionCache();
}

export function getLoginUrl(): string {
  return `${API_URL}/auth/login`;
}
