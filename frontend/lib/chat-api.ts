import type { BranchInfo, ChatStreamCallbacks, ComparisonData, GeneratedChart, GeneratedImage, Itinerary, UsageEntry } from './types';
import { withAuthParams } from './api-headers';
import { friendlyHttpError, sanitizeError } from './errors';

const MAX_RETRIES = 3;
const RETRY_DELAYS = [1000, 2000, 4000];

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException('Aborted', 'AbortError'));
      return;
    }
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener('abort', () => {
      clearTimeout(timer);
      reject(new DOMException('Aborted', 'AbortError'));
    }, { once: true });
  });
}

function isAbortError(err: unknown): boolean {
  return err instanceof DOMException && err.name === 'AbortError';
}

function isRetryableHttpStatus(status: number): boolean {
  return status >= 500 || status === 429;
}

function parseSSELine(line: string): { event?: string; data?: string } | null {
  if (line.startsWith('event: ')) return { event: line.slice(7).trim() };
  if (line.startsWith('data: ')) return { data: line.slice(6).trim() };
  return null;
}

function makeClientMessageId(): string {
  return globalThis.crypto?.randomUUID?.() ?? `cm-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export async function streamChat(
  body: { message: string; thread_id?: string; locale?: string; timezone?: string; currency?: string; attachments?: import('./upload-api').UploadedFile[]; client_message_id?: string },
  callbacks: ChatStreamCallbacks,
): Promise<string | undefined> {
  const { onToken, onItinerary, onComparison, onImage, onChart, onStatus, onThreadId, onDone, onError, onAbort, onCancelled, signal, errorMessages, onThinking, onToolStart, onToolEnd, onToolError, onUsage, onSubagentProgress, onReconnecting } = callbacks;
  let resolvedThreadId: string | undefined;

  const url = withAuthParams(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/chat/stream`);
  // No custom headers or application/json Content-Type here — both force a CORS
  // preflight OPTIONS request, which some hosting proxies (e.g. Hugging Face
  // Spaces) mishandle. Accept/Accept-Language are CORS-safelisted and fine to send.
  // The backend parses the JSON body manually, independent of Content-Type.
  const headers: Record<string, string> = {
    Accept: 'text/event-stream',
    ...(body.locale ? { 'Accept-Language': body.locale } : {}),
  };
  // One id per logical send — retries reuse it so the backend can dedupe
  // the message instead of appending it to the checkpoint twice.
  const bodyStr = JSON.stringify({ ...body, client_message_id: body.client_message_id ?? makeClientMessageId() });

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers,
        body: bodyStr,
        signal,
        credentials: 'include',
      });

      if (response.status === 401) {
        window.location.href = '/login';
        return undefined;
      }

      if (!response.ok) {
        if (attempt < MAX_RETRIES && isRetryableHttpStatus(response.status)) {
          onReconnecting?.(attempt + 1, MAX_RETRIES);
          await sleep(RETRY_DELAYS[attempt], signal);
          continue;
        }
        const text = await response.text().catch(() => '');
        const unexpected = errorMessages?.unexpected ?? 'Something went wrong. Please try again.';
        const detail = friendlyHttpError(response.status, text, { server: unexpected, request: unexpected });
        onError?.(errorMessages?.serverResponse?.(response.status, detail) ?? detail);
        return resolvedThreadId;
      }

      const reader = response.body?.getReader();
      if (!reader) {
        if (attempt < MAX_RETRIES) {
          onReconnecting?.(attempt + 1, MAX_RETRIES);
          await sleep(RETRY_DELAYS[attempt], signal);
          continue;
        }
        onError?.(errorMessages?.responseBody ?? 'Response body is not readable');
        return resolvedThreadId;
      }

      const decoder = new TextDecoder();
      let buffer = '';
      let sawDone = false;
      let currentEvent = '';
      let currentData = '';

      const dispatchIfReady = () => {
        if (currentData) {
          try {
            const parsed = JSON.parse(currentData);
            handleChatEvent(
              currentEvent,
              parsed,
              {
                onToken,
                onItinerary,
                onComparison,
                onImage,
                onChart,
                onStatus,
                onThreadId: (tid) => {
                  resolvedThreadId = tid;
                  onThreadId?.(tid);
                },
                onError,
                onDone: (data) => {
                  sawDone = true;
                  onDone?.(data);
                },
                onCancelled,
                onThinking,
                onToolStart,
                onToolEnd,
                onToolError,
                onUsage,
                onSubagentProgress,
              },
            );
          } catch {
            onError?.(errorMessages?.parseFailed ?? 'Failed to parse event data');
          }
        }
        currentEvent = '';
        currentData = '';
      };

      const processLines = (lines: string[]) => {
        for (const line of lines) {
          if (line.trim() === '') {
            dispatchIfReady();
            continue;
          }
          const parsed = parseSSELine(line);
          if (parsed?.event) currentEvent = parsed.event;
          if (parsed?.data) currentData = parsed.data;
        }
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        processLines(lines);
      }

      buffer += decoder.decode();
      if (buffer.trim()) processLines(buffer.split('\n'));
      dispatchIfReady();

      if (!sawDone) {
        if (attempt < MAX_RETRIES) {
          onReconnecting?.(attempt + 1, MAX_RETRIES);
          await sleep(RETRY_DELAYS[attempt], signal);
          continue;
        }
        onError?.(errorMessages?.streamEnded ?? 'Stream ended before the agent finished');
        return resolvedThreadId;
      }
      return resolvedThreadId;
    } catch (err) {
      if (isAbortError(err)) {
        onAbort?.();
        return resolvedThreadId;
      }
      if (attempt < MAX_RETRIES) {
        onReconnecting?.(attempt + 1, MAX_RETRIES);
        try {
          await sleep(RETRY_DELAYS[attempt], signal);
        } catch (abortErr) {
          if (isAbortError(abortErr)) {
            onAbort?.();
            return resolvedThreadId;
          }
        }
        continue;
      }
      onError?.(sanitizeError(
        err instanceof Error ? err.message : String(err),
        errorMessages?.unexpected ?? 'Something went wrong. Please try again.',
      ));
      return resolvedThreadId;
    }
  }
  return resolvedThreadId;
}

export async function cancelStream(threadId: string): Promise<void> {
  try {
    await fetch(
      withAuthParams(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/chat/cancel`),
      {
        method: 'POST',
        credentials: 'include',
        body: JSON.stringify({ thread_id: threadId }),
      },
    );
  } catch {
    // Best-effort — the fetch abort will also stop the stream
  }
}

function handleChatEvent(
  event: string,
  parsed: Record<string, unknown>,
  callbacks: {
    onToken?: (text: string) => void;
    onItinerary?: (itinerary: Itinerary) => void;
    onComparison?: (data: ComparisonData) => void;
    onImage?: (image: GeneratedImage) => void;
    onChart?: (chart: GeneratedChart) => void;
    onStatus?: (status: { tool: string; status: string }) => void;
    onThreadId?: (threadId: string) => void;
    onError?: (error: string) => void;
    onDone?: (data?: { budget_reached?: boolean }) => void;
    onCancelled?: () => void;
    onThinking?: (text: string) => void;
    onToolStart?: (tool: { name: string; input?: string; run_id: string; parent_run_id?: string }) => void;
    onToolEnd?: (tool: { name: string; output?: string; run_id: string; parent_run_id?: string }) => void;
    onToolError?: (tool: { name: string; error?: string; run_id: string; parent_run_id?: string }) => void;
    onUsage?: (usage: UsageEntry) => void;
    onSubagentProgress?: (data: { run_id: string; description: string }) => void;
  },
) {
  const { onToken, onItinerary, onComparison, onImage, onChart, onStatus, onThreadId, onError, onDone, onCancelled, onThinking, onToolStart, onToolEnd, onToolError, onUsage, onSubagentProgress } = callbacks;

  switch (event) {
    case 'token': {
      const data = parsed.data as string;
      onToken?.(data);
      break;
    }
    case 'itinerary': {
      const data = parsed.data as Itinerary;
      onItinerary?.(data);
      break;
    }
    case 'comparison': {
      const data = parsed.data as ComparisonData;
      onComparison?.(data);
      break;
    }
    case 'image': {
      const data = parsed.data as GeneratedImage;
      onImage?.(data);
      break;
    }
    case 'chart': {
      const data = parsed.data as GeneratedChart;
      onChart?.(data);
      break;
    }
    case 'status': {
      const data = parsed.data as { tool: string; status: string };
      onStatus?.(data);
      break;
    }
    case 'thread_id': {
      const data = parsed.data as { thread_id: string };
      onThreadId?.(data.thread_id);
      break;
    }
    case 'error': {
      onError?.(String(parsed.data ?? 'Unknown error'));
      break;
    }
    case 'done': {
      const data = parsed.data as { budget_reached?: boolean } | null;
      onDone?.(data ?? undefined);
      break;
    }
    case 'cancelled': {
      onCancelled?.();
      break;
    }
    case 'thinking': {
      const data = parsed.data as string;
      onThinking?.(data);
      break;
    }
    case 'tool_start': {
      const data = parsed.data as { name: string; input?: string; run_id: string; parent_run_id?: string };
      onToolStart?.(data);
      break;
    }
    case 'tool_end': {
      const data = parsed.data as { name: string; output?: string; run_id: string; parent_run_id?: string };
      onToolEnd?.(data);
      break;
    }
    case 'tool_error': {
      const data = parsed.data as { name: string; error?: string; run_id: string; parent_run_id?: string };
      onToolError?.(data);
      break;
    }
    case 'usage': {
      const data = parsed.data as UsageEntry;
      onUsage?.(data);
      break;
    }
    case 'subagent_progress': {
      const data = parsed.data as { run_id: string; description: string };
      onSubagentProgress?.(data);
      break;
    }
  }
}

export async function regenerateStream(
  body: { thread_id: string; locale?: string; timezone?: string; currency?: string },
  callbacks: ChatStreamCallbacks,
): Promise<string | undefined> {
  const { onToken, onItinerary, onComparison, onImage, onChart, onStatus, onThreadId, onDone, onError, onAbort, onCancelled, signal, errorMessages, onThinking, onToolStart, onToolEnd, onToolError, onUsage, onSubagentProgress, onReconnecting } = callbacks;
  let resolvedThreadId: string | undefined;
  let sawDone = false;

  const url = withAuthParams(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/chat/regenerate`);
  const headers: Record<string, string> = {
    Accept: 'text/event-stream',
    ...(body.locale ? { 'Accept-Language': body.locale } : {}),
  };
  const bodyStr = JSON.stringify(body);

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers,
        body: bodyStr,
        signal,
        credentials: 'include',
      });

      if (response.status === 401) {
        window.location.href = '/login';
        return undefined;
      }

      if (!response.ok || !response.body) {
        if (attempt < MAX_RETRIES && isRetryableHttpStatus(response.status)) {
          onReconnecting?.(attempt + 1, MAX_RETRIES);
          await sleep(RETRY_DELAYS[attempt], signal);
          continue;
        }
        onError?.(errorMessages?.unexpected ?? `HTTP ${response.status}`);
        return undefined;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        let currentEvent: string | undefined;
        for (const line of lines) {
          const parsed = parseSSELine(line);
          if (!parsed) continue;
          if (parsed.event) {
            currentEvent = parsed.event;
            continue;
          }
          if (parsed.data && currentEvent) {
            let data: Record<string, unknown>;
            try {
              data = JSON.parse(parsed.data);
            } catch {
              data = { data: parsed.data };
            }
            if (currentEvent === 'thread_id') {
              const tid = data.thread_id as string;
              if (tid) {
                resolvedThreadId = tid;
                onThreadId?.(tid);
              }
            } else {
              handleChatEvent(currentEvent, data, {
                onToken, onItinerary, onComparison, onImage, onChart, onStatus, onThreadId, onDone: (d) => { sawDone = true; onDone?.(d); }, onError, onCancelled, onThinking, onToolStart, onToolEnd, onToolError, onUsage, onSubagentProgress,
              });
            }
          }
        }
      }
      if (!sawDone) {
        if (attempt < MAX_RETRIES) {
          onReconnecting?.(attempt + 1, MAX_RETRIES);
          await sleep(RETRY_DELAYS[attempt], signal);
          continue;
        }
        onError?.(errorMessages?.streamEnded ?? 'Stream ended before the agent finished');
        return resolvedThreadId;
      }
      return resolvedThreadId;
    } catch (err) {
      if (isAbortError(err)) {
        onAbort?.();
        return resolvedThreadId;
      }
      if (attempt < MAX_RETRIES) {
        onReconnecting?.(attempt + 1, MAX_RETRIES);
        try {
          await sleep(RETRY_DELAYS[attempt], signal);
        } catch (abortErr) {
          if (isAbortError(abortErr)) {
            onAbort?.();
            return resolvedThreadId;
          }
        }
        continue;
      }
      onError?.(sanitizeError(
        err instanceof Error ? err.message : String(err),
        errorMessages?.unexpected ?? 'Something went wrong. Please try again.',
      ));
      return resolvedThreadId;
    }
  }
  return resolvedThreadId;
}

export async function editItinerary(
  body: { thread_id: string; itinerary: Itinerary; locale?: string; timezone?: string; currency?: string },
  callbacks: ChatStreamCallbacks,
): Promise<string | undefined> {
  const { onToken, onItinerary, onComparison, onImage, onChart, onStatus, onThreadId, onDone, onError, onAbort, onCancelled, signal, errorMessages, onThinking, onToolStart, onToolEnd, onToolError, onUsage, onSubagentProgress, onReconnecting } = callbacks;
  let resolvedThreadId: string | undefined;
  let sawDone = false;

  const url = withAuthParams(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/chat/${body.thread_id}/edit-itinerary`);
  const headers: Record<string, string> = {
    Accept: 'text/event-stream',
    ...(body.locale ? { 'Accept-Language': body.locale } : {}),
  };
  const bodyStr = JSON.stringify(body);

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers,
        body: bodyStr,
        signal,
        credentials: 'include',
      });

      if (response.status === 401) {
        window.location.href = '/login';
        return undefined;
      }

      if (!response.ok || !response.body) {
        if (attempt < MAX_RETRIES && isRetryableHttpStatus(response.status)) {
          onReconnecting?.(attempt + 1, MAX_RETRIES);
          await sleep(RETRY_DELAYS[attempt], signal);
          continue;
        }
        onError?.(errorMessages?.unexpected ?? `HTTP ${response.status}`);
        return undefined;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        let currentEvent: string | undefined;
        for (const line of lines) {
          const parsed = parseSSELine(line);
          if (!parsed) continue;
          if (parsed.event) {
            currentEvent = parsed.event;
            continue;
          }
          if (parsed.data && currentEvent) {
            let data: Record<string, unknown>;
            try {
              data = JSON.parse(parsed.data);
            } catch {
              data = { data: parsed.data };
            }
            if (currentEvent === 'thread_id') {
              const tid = data.thread_id as string;
              if (tid) {
                resolvedThreadId = tid;
                onThreadId?.(tid);
              }
            } else {
              handleChatEvent(currentEvent, data, {
                onToken, onItinerary, onComparison, onImage, onChart, onStatus, onThreadId, onDone: (d) => { sawDone = true; onDone?.(d); }, onError, onCancelled, onThinking, onToolStart, onToolEnd, onToolError, onUsage, onSubagentProgress,
              });
            }
          }
        }
      }
      if (!sawDone) {
        if (attempt < MAX_RETRIES) {
          onReconnecting?.(attempt + 1, MAX_RETRIES);
          await sleep(RETRY_DELAYS[attempt], signal);
          continue;
        }
        onError?.(errorMessages?.streamEnded ?? 'Stream ended before the agent finished');
        return resolvedThreadId;
      }
      return resolvedThreadId;
    } catch (err) {
      if (isAbortError(err)) {
        onAbort?.();
        return resolvedThreadId;
      }
      if (attempt < MAX_RETRIES) {
        onReconnecting?.(attempt + 1, MAX_RETRIES);
        try {
          await sleep(RETRY_DELAYS[attempt], signal);
        } catch (abortErr) {
          if (isAbortError(abortErr)) {
            onAbort?.();
            return resolvedThreadId;
          }
        }
        continue;
      }
      onError?.(sanitizeError(
        err instanceof Error ? err.message : String(err),
        errorMessages?.unexpected ?? 'Something went wrong. Please try again.',
      ));
      return resolvedThreadId;
    }
  }
  return resolvedThreadId;
}

export async function getBranches(threadId: string): Promise<BranchInfo[]> {
  try {
    const res = await fetch(
      withAuthParams(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/threads/${threadId}/branches`),
      { credentials: 'include' },
    );
    if (res.status === 401) {
      window.location.href = '/login';
      return [];
    }
    if (!res.ok) return [];
    const data = await res.json();
    return data.branches ?? [];
  } catch {
    return [];
  }
}

export async function editStream(
  body: { thread_id: string; message: string; locale?: string; timezone?: string; currency?: string; client_message_id?: string },
  callbacks: ChatStreamCallbacks,
): Promise<string | undefined> {
  const { onToken, onItinerary, onComparison, onImage, onChart, onStatus, onThreadId, onDone, onError, onAbort, onCancelled, signal, errorMessages, onThinking, onToolStart, onToolEnd, onToolError, onUsage, onSubagentProgress, onReconnecting } = callbacks;
  let resolvedThreadId: string | undefined;
  let sawDone = false;

  const url = withAuthParams(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/chat/edit`);
  const headers: Record<string, string> = {
    Accept: 'text/event-stream',
    ...(body.locale ? { 'Accept-Language': body.locale } : {}),
  };
  const bodyStr = JSON.stringify({ ...body, client_message_id: body.client_message_id ?? makeClientMessageId() });

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers,
        body: bodyStr,
        signal,
        credentials: 'include',
      });

      if (response.status === 401) {
        window.location.href = '/login';
        return undefined;
      }

      if (!response.ok || !response.body) {
        if (attempt < MAX_RETRIES && isRetryableHttpStatus(response.status)) {
          onReconnecting?.(attempt + 1, MAX_RETRIES);
          await sleep(RETRY_DELAYS[attempt], signal);
          continue;
        }
        onError?.(errorMessages?.unexpected ?? `HTTP ${response.status}`);
        return undefined;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        let currentEvent: string | undefined;
        for (const line of lines) {
          const parsed = parseSSELine(line);
          if (!parsed) continue;
          if (parsed.event) {
            currentEvent = parsed.event;
            continue;
          }
          if (parsed.data && currentEvent) {
            let data: Record<string, unknown>;
            try {
              data = JSON.parse(parsed.data);
            } catch {
              data = { data: parsed.data };
            }
            if (currentEvent === 'thread_id') {
              const tid = data.thread_id as string;
              if (tid) {
                resolvedThreadId = tid;
                onThreadId?.(tid);
              }
            } else {
              handleChatEvent(currentEvent, data, {
                onToken, onItinerary, onComparison, onImage, onChart, onStatus, onThreadId, onDone: (d) => { sawDone = true; onDone?.(d); }, onError, onCancelled, onThinking, onToolStart, onToolEnd, onToolError, onUsage, onSubagentProgress,
              });
            }
          }
        }
      }
      if (!sawDone) {
        if (attempt < MAX_RETRIES) {
          onReconnecting?.(attempt + 1, MAX_RETRIES);
          await sleep(RETRY_DELAYS[attempt], signal);
          continue;
        }
        onError?.(errorMessages?.streamEnded ?? 'Stream ended before the agent finished');
        return resolvedThreadId;
      }
      return resolvedThreadId;
    } catch (err) {
      if (isAbortError(err)) {
        onAbort?.();
        return resolvedThreadId;
      }
      if (attempt < MAX_RETRIES) {
        onReconnecting?.(attempt + 1, MAX_RETRIES);
        try {
          await sleep(RETRY_DELAYS[attempt], signal);
        } catch (abortErr) {
          if (isAbortError(abortErr)) {
            onAbort?.();
            return resolvedThreadId;
          }
        }
        continue;
      }
      onError?.(sanitizeError(
        err instanceof Error ? err.message : String(err),
        errorMessages?.unexpected ?? 'Something went wrong. Please try again.',
      ));
      return resolvedThreadId;
    }
  }
  return resolvedThreadId;
}

export class TierRegenError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail || `HTTP ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

export async function regenerateTier(
  body: { thread_id: string; tier: string; locale?: string; currency?: string },
  signal?: AbortSignal,
): Promise<ComparisonData> {
  const url = withAuthParams(
    `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/chat/regenerate-tier`
  );
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(body.locale ? { 'Accept-Language': body.locale } : {}),
    },
    body: JSON.stringify(body),
    signal,
    credentials: 'include',
  });

  if (response.status === 401) {
    window.location.href = '/login';
    throw new TierRegenError(401, 'unauthorized');
  }

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new TierRegenError(response.status, String(data?.detail ?? ''));
  }
  return data.comparison as ComparisonData;
}
