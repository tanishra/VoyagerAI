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
  const { onEvent, onProgress, onFinal, onError, signal } = callbacks;

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
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

      let currentEvent = '';
      let currentData = '';

      for (const line of lines) {
        if (line.trim() === '') {
          if (currentData) {
            try {
              const parsed = JSON.parse(currentData);
              onEvent?.(parsed);
              handleEvent(parsed, onProgress, onFinal, onError);
            } catch {
              onError?.('Failed to parse event data');
            }
          }
          currentEvent = '';
          currentData = '';
          continue;
        }

        const parsed = parseSSELine(line);
        if (parsed?.event) currentEvent = parsed.event;
        if (parsed?.data) currentData = parsed.data;
      }
    }
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') return;
    onError?.(err instanceof Error ? err.message : String(err));
  }
}

function getData(parsed: Record<string, unknown>): Record<string, unknown> | undefined {
  const d = parsed.data;
  if (d && typeof d === 'object' && !Array.isArray(d)) return d as Record<string, unknown>;
  return undefined;
}

function handleEvent(
  parsed: Record<string, unknown>,
  onProgress?: StreamCallbacks['onProgress'],
  onFinal?: StreamCallbacks['onFinal'],
  onError?: StreamCallbacks['onError'],
) {
  const event = parsed.event as string;
  const data = getData(parsed);

  switch (event) {
    case 'on_tool_start': {
      const name = parsed.name as string;
      const input = data?.input;
      onProgress?.(`Running ${name}`, input ? JSON.stringify(input).slice(0, 120) : '');
      break;
    }
    case 'on_tool_end': {
      const name = parsed.name as string;
      onProgress?.(`${name} complete`, '');
      break;
    }
    case 'on_chain_start': {
      const name = parsed.name as string;
      onProgress?.(`Starting ${name}`, '');
      break;
    }
    case 'on_chain_end': {
      const name = parsed.name as string;
      onProgress?.(`${name} complete`, '');
      break;
    }
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
