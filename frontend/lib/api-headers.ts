import { getCsrfHeaders, getCsrfToken } from './csrf';
import { getSessionToken } from './session-token';

/**
 * Returns combined headers for outgoing API requests:
 * - CSRF token header (`X-CSRF-Token`)
 * - Session token header (`X-Session-Token`) when available in localStorage
 * - Optional API key header (`X-API-Key`) when NEXT_PUBLIC_API_AUTH_KEY is provided
 * - Any additional custom headers
 */
export function getApiHeaders(extraHeaders: Record<string, string> = {}): Record<string, string> {
  const headers: Record<string, string> = {
    ...getCsrfHeaders(),
    ...extraHeaders,
  };

  const sessionToken = getSessionToken();
  if (sessionToken) {
    headers['X-Session-Token'] = sessionToken;
  }

  const apiKey = process.env.NEXT_PUBLIC_API_AUTH_KEY;
  if (apiKey) {
    headers['X-API-Key'] = apiKey;
  }

  return headers;
}

/**
 * Appends the session token and API key as query params instead of custom headers.
 *
 * Custom headers (X-Session-Token, X-API-Key) and non-simple Content-Types
 * (application/json) force the browser to send a CORS preflight OPTIONS
 * request. Some hosting proxies (e.g. Hugging Face Spaces) intercept and
 * answer OPTIONS requests themselves without proper
 * Access-Control-Allow-Credentials support, which silently breaks any
 * preflighted cross-origin request. Passing auth via query params keeps
 * the request a CORS "simple request" and avoids preflight entirely.
 */
export function withAuthParams(url: string): string {
  const u = new URL(url);
  const sessionToken = getSessionToken();
  if (sessionToken) {
    u.searchParams.set('session_token', sessionToken);
  }
  const csrfToken = getCsrfToken();
  if (csrfToken) {
    u.searchParams.set('csrf_token', csrfToken);
  }
  const apiKey = process.env.NEXT_PUBLIC_API_AUTH_KEY;
  if (apiKey) {
    u.searchParams.set('api_key', apiKey);
  }
  return u.toString();
}
