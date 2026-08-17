import type { ChatStreamCallbacks, ComparisonData, Itinerary, ToolCallEntry, UsageEntry } from './types';

function parseSSELine(line: string): { event?: string; data?: string } | null {
  if (line.startsWith('event: ')) return { event: line.slice(7).trim() };
  if (line.startsWith('data: ')) return { data: line.slice(6).trim() };
  return null;
}

export async function streamChat(
  body: { message: string; thread_id?: string; locale?: string },
  callbacks: ChatStreamCallbacks,
): Promise<string | undefined> {
  const { onToken, onItinerary, onComparison, onStatus, onThreadId, onDone, onError, onAbort, signal, errorMessages, onThinking, onToolStart, onToolEnd, onToolError, onUsage } = callbacks;
  let resolvedThreadId: string | undefined;

  try {
    const response = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/chat/stream`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
          ...(body.locale ? { 'Accept-Language': body.locale } : {}),
        },
        body: JSON.stringify(body),
        signal,
        credentials: 'include',
      },
    );

    if (response.status === 401) {
      window.location.href = '/login';
      return undefined;
    }

    if (!response.ok) {
      const text = await response.text().catch(() => '');
      onError?.(errorMessages?.serverResponse?.(response.status, text) ?? `Server responded with ${response.status}: ${text}`);
      return undefined;
    }

    const reader = response.body?.getReader();
    if (!reader) {
      onError?.(errorMessages?.responseBody ?? 'Response body is not readable');
      return undefined;
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
              onStatus,
              onThreadId: (tid) => {
                resolvedThreadId = tid;
                onThreadId?.(tid);
              },
              onError,
              onDone: () => {
                sawDone = true;
                onDone?.();
              },
              onThinking,
              onToolStart,
              onToolEnd,
              onToolError,
              onUsage,
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
      onError?.(errorMessages?.streamEnded ?? 'Stream ended before the agent finished');
      return resolvedThreadId;
    }
    return resolvedThreadId;
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      onAbort?.();
      return resolvedThreadId;
    }
    onError?.(err instanceof Error ? err.message : String(err));
    return resolvedThreadId;
  }
}

function handleChatEvent(
  event: string,
  parsed: Record<string, unknown>,
  callbacks: {
    onToken?: (text: string) => void;
    onItinerary?: (itinerary: Itinerary) => void;
    onComparison?: (data: ComparisonData) => void;
    onStatus?: (status: { tool: string; status: string }) => void;
    onThreadId?: (threadId: string) => void;
    onError?: (error: string) => void;
    onDone?: () => void;
    onThinking?: (text: string) => void;
    onToolStart?: (tool: { name: string; input?: string; run_id: string }) => void;
    onToolEnd?: (tool: { name: string; output?: string; run_id: string }) => void;
    onToolError?: (tool: { name: string; error?: string; run_id: string }) => void;
    onUsage?: (usage: UsageEntry) => void;
  },
) {
  const { onToken, onItinerary, onComparison, onStatus, onThreadId, onError, onDone, onThinking, onToolStart, onToolEnd, onToolError, onUsage } = callbacks;

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
      onDone?.();
      break;
    }
    case 'thinking': {
      const data = parsed.data as string;
      onThinking?.(data);
      break;
    }
    case 'tool_start': {
      const data = parsed.data as { name: string; input?: string; run_id: string };
      onToolStart?.(data);
      break;
    }
    case 'tool_end': {
      const data = parsed.data as { name: string; output?: string; run_id: string };
      onToolEnd?.(data);
      break;
    }
    case 'tool_error': {
      const data = parsed.data as { name: string; error?: string; run_id: string };
      onToolError?.(data);
      break;
    }
    case 'usage': {
      const data = parsed.data as UsageEntry;
      onUsage?.(data);
      break;
    }
  }
}
