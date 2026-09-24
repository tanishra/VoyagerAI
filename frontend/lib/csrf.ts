const CSRF_COOKIE_NAME = "voyager_csrf";

export function getCsrfToken(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(
    new RegExp(`${CSRF_COOKIE_NAME}=([^;]+)`),
  );
  return match ? match[1] : null;
}

export function getCsrfHeaders(): Record<string, string> {
  const token = getCsrfToken();
  return token ? { "X-CSRF-Token": token } : {};
}
