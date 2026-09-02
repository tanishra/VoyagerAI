import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

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

describe('editStream', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('sends POST with thread_id and message to /chat/edit', async () => {
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

    const { editStream } = await import('@/lib/chat-api');
    await editStream(
      { thread_id: 'test-thread-123', message: 'edited content' },
      {},
    );

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toContain('/chat/edit');
    expect(options.method).toBe('POST');
    expect(options.credentials).toBe('include');
    expect(JSON.parse(options.body)).toEqual({
      thread_id: 'test-thread-123',
      message: 'edited content',
    });
  });

  it('includes credentials for auth cookies', async () => {
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

    const { editStream } = await import('@/lib/chat-api');
    await editStream({ thread_id: 'thread-abc', message: 'edited' }, {});

    const [, options] = mockFetch.mock.calls[0];
    expect(options.credentials).toBe('include');
  });

  it('swallows network errors without throwing', async () => {
    vi.useFakeTimers();
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Network error')));

    const { editStream } = await import('@/lib/chat-api');
    const promise = editStream({ thread_id: 'thread-xyz', message: 'edited' }, {});
    await vi.advanceTimersByTimeAsync(8000);
    await expect(promise).resolves.toBeUndefined();
    vi.useRealTimers();
  });
});

describe('editStream — retry logic', () => {
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
    const { editStream } = await import('@/lib/chat-api');
    const promise = editStream(
      { thread_id: 'test-thread', message: 'edited' },
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
    const { editStream } = await import('@/lib/chat-api');
    await editStream({ thread_id: 'test-thread', message: 'edited' }, { onReconnecting });

    expect(mockFetch).toHaveBeenCalledTimes(1);
    expect(onReconnecting).not.toHaveBeenCalled();
    window.location.href = originalHref;
  });
});
