import { getUserId } from '@/lib/user-id';
import type { Itinerary, PlanRequest, StreamCallbacks } from './types';

function parseSSELine(line: string): { event?: string; data?: string } | null {
  if (line.startsWith('event: ')) return { event: line.slice(7).trim() };
  if (line.startsWith('data: ')) return { data: line.slice(6).trim() };
  return null;
}

export async function streamPlan(
  url: string,
  body: PlanRequest,
  callbacks: StreamCallbacks,
): Promise<void> {
  const { onEvent, onFinal, onError, signal } = callbacks;

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream', 'X-User-Id': getUserId() },
      body: JSON.stringify(body),
      signal,
    });

    if (!response.ok) {
      const text = await response.text().catch(() => '');
      onError?.(`Server responded with ${response.status}: ${text}`);
      return;
    }

    const reader = response.body?.getReader();
    if (!reader) {
      onError?.('Response body is not readable');
      return;
    }

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      let currentData = '';

      for (const line of lines) {
        if (line.trim() === '') {
          if (currentData) {
            try {
              const parsed = JSON.parse(currentData);
              onEvent?.(parsed);
              handleEvent(parsed, onFinal, onError);
            } catch {
              onError?.('Failed to parse event data');
            }
          }
          currentData = '';
          continue;
        }

        const parsed = parseSSELine(line);
        if (parsed?.data) currentData = parsed.data;
      }
    }
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') return;
    onError?.(err instanceof Error ? err.message : String(err));
  }
}

function handleEvent(
  parsed: Record<string, unknown>,
  onFinal?: StreamCallbacks['onFinal'],
  onError?: StreamCallbacks['onError'],
) {
  const event = parsed.event as string;

  switch (event) {
    case 'final': {
      const itinerary = parsed.data as Itinerary;
      onFinal?.(itinerary);
      break;
    }
    case 'error': {
      onError?.(String(parsed.data ?? 'Unknown error'));
      break;
    }
  }
}
