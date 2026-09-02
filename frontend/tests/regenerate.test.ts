import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { getBranches } from '@/lib/chat-api';

function makeDoneStream(): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode('event: thread_id\ndata: {"data":{"thread_id":"test-thread"}}\n\n'));
      controller.enqueue(encoder.encode('event: done\ndata: {"data":null}\n\n'));
      controller.close();
    },
  });
  return new Response(stream, { status: 200, headers: { 'Content-Type': 'text/event-stream' } });
}

describe('regenerateStream', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('regenerateStream sends POST with thread_id to /chat/regenerate', async () => {
    const mockResponse = {
      ok: true,
      status: 200,
      body: {
        getReader: () => ({
          read: async () => ({ done: true, value: undefined }),
        }),
      },
    };
    const mockFetch = vi.fn().mockResolvedValue(mockResponse);
    vi.stubGlobal('fetch', mockFetch);

    const { regenerateStream } = await import('@/lib/chat-api');
    await regenerateStream(
      { thread_id: 'test-thread-123' },
      {},
    );

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toContain('/chat/regenerate');
    expect(options.method).toBe('POST');
    expect(options.credentials).toBe('include');
    expect(JSON.parse(options.body)).toEqual({ thread_id: 'test-thread-123' });
  });

  it('regenerateStream includes credentials for auth cookies', async () => {
    const mockResponse = {
      ok: true,
      status: 200,
      body: {
        getReader: () => ({
          read: async () => ({ done: true, value: undefined }),
        }),
      },
    };
    const mockFetch = vi.fn().mockResolvedValue(mockResponse);
    vi.stubGlobal('fetch', mockFetch);

    const { regenerateStream } = await import('@/lib/chat-api');
    await regenerateStream({ thread_id: 'thread-abc' }, {});

    const [, options] = mockFetch.mock.calls[0];
    expect(options.credentials).toBe('include');
  });

  it('regenerateStream swallows network errors without throwing', async () => {
    vi.useFakeTimers();
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Network error')));

    const { regenerateStream } = await import('@/lib/chat-api');
    const promise = regenerateStream({ thread_id: 'thread-xyz' }, {});
    await vi.advanceTimersByTimeAsync(8000);
    await expect(promise).resolves.toBeUndefined();
    vi.useRealTimers();
  });
});

describe('regenerateStream — retry logic', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('retries on network error and succeeds on second attempt', async () => {
    const mockFetch = vi.fn()
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce(makeDoneStream());
    vi.stubGlobal('fetch', mockFetch);

    const onReconnecting = vi.fn();
    const { regenerateStream } = await import('@/lib/chat-api');
    const promise = regenerateStream(
      { thread_id: 'test-thread' },
      { onReconnecting },
    );

    await vi.advanceTimersByTimeAsync(1100);
    await promise;

    expect(mockFetch).toHaveBeenCalledTimes(2);
    expect(onReconnecting).toHaveBeenCalledTimes(1);
    expect(onReconnecting).toHaveBeenCalledWith(1, 3);
  });

  it('does not retry on 401 (redirects to login)', async () => {
    const mockFetch = vi.fn().mockResolvedValue(
      new Response('Unauthorized', { status: 401 }),
    );
    vi.stubGlobal('fetch', mockFetch);
    const originalHref = window.location.href;
    Object.defineProperty(window, 'location', {
      value: { href: '' },
      writable: true,
    });

    const onReconnecting = vi.fn();
    const { regenerateStream } = await import('@/lib/chat-api');
    await regenerateStream({ thread_id: 'test-thread' }, { onReconnecting });

    expect(mockFetch).toHaveBeenCalledTimes(1);
    expect(onReconnecting).not.toHaveBeenCalled();
    window.location.href = originalHref;
  });
});

describe('getBranches', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('sends GET request to /threads/{threadId}/branches', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ branches: [{ checkpoint_id: 'b1', is_current: true }] }),
    });
    vi.stubGlobal('fetch', mockFetch);

    const result = await getBranches('test-thread');

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toContain('/threads/test-thread/branches');
    expect(options.credentials).toBe('include');
    expect(result).toHaveLength(1);
    expect(result[0].checkpoint_id).toBe('b1');
  });

  it('returns empty array on network failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Network error')));

    const result = await getBranches('thread-xyz');
    expect(result).toEqual([]);
  });

  it('returns empty array on non-ok response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 500 }));

    const result = await getBranches('thread-err');
    expect(result).toEqual([]);
  });
});
