const CSRF_COOKIE_NAME = "voyager_csrf";

export function getCsrfHeaders(): Record<string, string> {
  if (typeof document === "undefined") return {};
  const match = document.cookie.match(
    new RegExp(`${CSRF_COOKIE_NAME}=([^;]+)`),
  );
  return match ? { "X-CSRF-Token": match[1] } : {};
}
