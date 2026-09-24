// User-facing error sanitization — technical text (exception names,
// tracebacks, provider URLs, stack frames) must never reach the UI.

const TECHNICAL_PATTERNS = [
  /\b[A-Z][A-Za-z]*Error\b/,            // RateLimitError, TypeError, ...
  /\b[a-z_]+Error:/i,                   // litellm.RateLimitError:, validation_error:
  /\bTraceback\b/,
  /\bFile "[^"]+"/,
  /litellm|openai\.com|anthropic\.com|platform\.openai|api\.openai/i,
  /\b[A-Za-z_]+Exception\b/,
  /at [a-zA-Z_$][\w$]* \(/,             // JS stack frames "at foo ("
  /\bECONNREFUSED|ECONNRESET|ENOTFOUND|ETIMEDOUT\b/,
];

const MAX_USER_ERROR_LEN = 200;

export function isTechnicalError(raw: string): boolean {
  if (!raw) return false;
  if (raw.length > MAX_USER_ERROR_LEN) return true;
  return TECHNICAL_PATTERNS.some((p) => p.test(raw));
}

/** Return `raw` if it's safe to show users, otherwise `fallback`. */
export function sanitizeError(raw: string | null | undefined, fallback: string): string {
  const text = (raw ?? '').trim();
  if (!text) return fallback;
  return isTechnicalError(text) ? fallback : text;
}

/**
 * Build a friendly message for a non-OK HTTP response.
 * Passes through short, already-friendly backend `detail` strings
 * (e.g. localized budget/cooldown messages) and drops everything technical.
 */
export function friendlyHttpError(
  status: number,
  body: string,
  fallbacks: { server: string; request: string },
): string {
  let detail = '';
  try {
    const parsed = JSON.parse(body) as { detail?: unknown };
    if (typeof parsed.detail === 'string') {
      detail = parsed.detail;
    } else if (parsed.detail && typeof parsed.detail === 'object') {
      // Structured error: {code, message} — display the message, code is for logic
      const msg = (parsed.detail as { message?: unknown }).message;
      if (typeof msg === 'string') detail = msg;
    }
  } catch {
    detail = body;
  }
  const safe = sanitizeError(detail, '');
  if (safe) return safe;
  return status >= 500 ? fallbacks.server : fallbacks.request;
}

/** Extract the machine-readable error code from a backend error body, if any.
 *  Returns null for legacy string details or unparseable bodies. */
export function parseErrorCode(body: string): string | null {
  try {
    const parsed = JSON.parse(body) as { detail?: unknown };
    if (parsed.detail && typeof parsed.detail === 'object') {
      const code = (parsed.detail as { code?: unknown }).code;
      if (typeof code === 'string') return code;
    }
  } catch {
    // not JSON — no code
  }
  return null;
}
