import { getUserId } from '@/lib/user-id';

export interface FetchOptions {
  timeout?: number;
  retries?: number;
  signal?: AbortSignal;
}

export interface FetchError {
  message: string;
  isTimeout: boolean;
  isNetworkError: boolean;
  isAborted: boolean;
  statusCode: number | null;
}

const DEFAULT_TIMEOUT = 120_000;
const DEFAULT_RETRIES = 2;
const BASE_RETRY_DELAY = 1000;

export function isFetchError(e: unknown): e is FetchError {
  return typeof e === 'object' && e !== null && 'isTimeout' in e && 'isNetworkError' in e;
}

export async function fetchWithTimeout<T>(
  url: string,
  body: unknown,
  options: FetchOptions = {},
): Promise<T> {
  const { timeout = DEFAULT_TIMEOUT, retries = DEFAULT_RETRIES } = options;

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      return await doFetch<T>(url, body, options);
    } catch (err) {
      const fetchErr = normalizeError(err);

      if (fetchErr.isAborted) throw fetchErr;

      if (fetchErr.isNetworkError && attempt < retries) {
        const delay = BASE_RETRY_DELAY * Math.pow(2, attempt);
        await new Promise((r) => setTimeout(r, delay));
        continue;
      }

      throw fetchErr;
    }
  }

  throw new Error('unreachable');
}

async function doFetch<T>(
  url: string,
  body: unknown,
  options: FetchOptions,
): Promise<T> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), options.timeout ?? DEFAULT_TIMEOUT);

  const combinedSignal = options.signal
    ? combineSignals(options.signal, controller.signal)
    : controller.signal;

  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-User-Id': getUserId() },
      body: JSON.stringify(body),
      signal: combinedSignal,
    });

    if (!res.ok) {
      const text = await res.text().catch(() => '');
      throw makeError(`Server responded with ${res.status}`, {
        statusCode: res.status,
        message: text || res.statusText,
      });
    }

    return res.json() as Promise<T>;
  } finally {
    clearTimeout(timeoutId);
  }
}

function combineSignals(...signals: AbortSignal[]): AbortSignal {
  const controller = new AbortController();
  for (const signal of signals) {
    if (signal.aborted) {
      controller.abort(signal.reason);
      return controller.signal;
    }
    signal.addEventListener('abort', () => controller.abort(signal.reason), { once: true });
  }
  return controller.signal;
}

function makeError(message: string, extra?: Partial<FetchError>): FetchError {
  return {
    message,
    isTimeout: false,
    isNetworkError: false,
    isAborted: false,
    statusCode: null,
    ...extra,
  };
}

function normalizeError(err: unknown): FetchError {
  if (err && typeof err === 'object' && 'isTimeout' in err) {
    return err as FetchError;
  }

  if (err instanceof DOMException && err.name === 'AbortError') {
    return makeError('Request was cancelled', { isAborted: true });
  }

  if (err instanceof TypeError) {
    return makeError('Unable to connect to the server. Make sure it is running.', {
      isNetworkError: true,
    });
  }

  return makeError(String(err));
}
