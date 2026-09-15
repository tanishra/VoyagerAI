import { getCsrfHeaders } from './csrf';

/**
 * Returns combined headers for outgoing API requests:
 * - CSRF token header (`X-CSRF-Token`)
 * - Optional API key header (`X-API-Key`) when NEXT_PUBLIC_API_AUTH_KEY is provided
 * - Any additional custom headers
 */
export function getApiHeaders(extraHeaders: Record<string, string> = {}): Record<string, string> {
  const headers: Record<string, string> = {
    ...getCsrfHeaders(),
    ...extraHeaders,
  };

  const apiKey = process.env.NEXT_PUBLIC_API_AUTH_KEY;
  if (apiKey) {
    headers['X-API-Key'] = apiKey;
  }

  return headers;
}
