import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { cancelStream, streamChat } from '@/lib/chat-api';

function makeStreamResponse(chunks: string[] = []): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });
  return new Response(stream, { status: 200, headers: { 'Content-Type': 'text/event-stream' } });
}

function makeDoneStream(): Response {
  return makeStreamResponse([
    'event: thread_id\ndata: {"data":{"thread_id":"test-thread"}}\n\n',
    'event: done\ndata: {"data":null}\n\n',
  ]);
}

describe('cancelStream', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('sends POST with thread_id to /chat/cancel', async () => {
    const mockFetch = vi.fn().mockResolvedValue({ ok: true, status: 200 });
    vi.stubGlobal('fetch', mockFetch);

    await cancelStream('test-thread-123');

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toContain('/chat/cancel');
    expect(options.method).toBe('POST');
    expect(options.credentials).toBe('include');
    expect(JSON.parse(options.body)).toEqual({ thread_id: 'test-thread-123' });
  });

  it('includes credentials for auth cookies', async () => {
    const mockFetch = vi.fn().mockResolvedValue({ ok: true, status: 200 });
    vi.stubGlobal('fetch', mockFetch);

    await cancelStream('thread-abc');

    const [, options] = mockFetch.mock.calls[0];
    expect(options.credentials).toBe('include');
  });

  it('swallows network errors without throwing', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Network error')));

    await expect(cancelStream('thread-xyz')).resolves.toBeUndefined();
  });
});

describe('streamChat — retry logic', () => {
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
    const onDone = vi.fn();
    const promise = streamChat(
      { message: 'test' },
      { onReconnecting, onDone },
    );

    // Advance past the 1s retry delay
    await vi.advanceTimersByTimeAsync(1100);

    await promise;

    expect(mockFetch).toHaveBeenCalledTimes(2);
    expect(onReconnecting).toHaveBeenCalledTimes(1);
    expect(onReconnecting).toHaveBeenCalledWith(1, 3);
    expect(onDone).toHaveBeenCalledTimes(1);
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
    await streamChat({ message: 'test' }, { onReconnecting });

    expect(mockFetch).toHaveBeenCalledTimes(1);
    expect(onReconnecting).not.toHaveBeenCalled();
    window.location.href = originalHref;
  });

  it('does not retry on 400 (client error)', async () => {
    const mockFetch = vi.fn().mockResolvedValue(
      new Response('Bad Request', { status: 400 }),
    );
    vi.stubGlobal('fetch', mockFetch);

    const onReconnecting = vi.fn();
    const onError = vi.fn();
    await streamChat({ message: 'test' }, { onReconnecting, onError });

    expect(mockFetch).toHaveBeenCalledTimes(1);
    expect(onReconnecting).not.toHaveBeenCalled();
    expect(onError).toHaveBeenCalledTimes(1);
  });

  it('retries on 500 server error', async () => {
    const mockFetch = vi.fn()
      .mockResolvedValueOnce(new Response('Server Error', { status: 500 }))
      .mockResolvedValueOnce(makeDoneStream());
    vi.stubGlobal('fetch', mockFetch);

    const onReconnecting = vi.fn();
    const onDone = vi.fn();
    const promise = streamChat(
      { message: 'test' },
      { onReconnecting, onDone },
    );

    await vi.advanceTimersByTimeAsync(1100);
    await promise;

    expect(mockFetch).toHaveBeenCalledTimes(2);
    expect(onReconnecting).toHaveBeenCalledTimes(1);
    expect(onDone).toHaveBeenCalledTimes(1);
  });

  it('retries on 429 rate limit', async () => {
    const mockFetch = vi.fn()
      .mockResolvedValueOnce(new Response('Rate Limited', { status: 429 }))
      .mockResolvedValueOnce(makeDoneStream());
    vi.stubGlobal('fetch', mockFetch);

    const onReconnecting = vi.fn();
    const onDone = vi.fn();
    const promise = streamChat(
      { message: 'test' },
      { onReconnecting, onDone },
    );

    await vi.advanceTimersByTimeAsync(1100);
    await promise;

    expect(mockFetch).toHaveBeenCalledTimes(2);
    expect(onReconnecting).toHaveBeenCalledTimes(1);
  });

  it('exhausts all retries and calls onError', async () => {
    const mockFetch = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'));
    vi.stubGlobal('fetch', mockFetch);

    const onReconnecting = vi.fn();
    const onError = vi.fn();
    const promise = streamChat(
      { message: 'test' },
      { onReconnecting, onError },
    );

    // Advance through all 3 retry delays: 1s + 2s + 4s = 7s
    await vi.advanceTimersByTimeAsync(8000);
    await promise;

    // 1 initial + 3 retries = 4 total calls
    expect(mockFetch).toHaveBeenCalledTimes(4);
    expect(onReconnecting).toHaveBeenCalledTimes(3);
    expect(onError).toHaveBeenCalledTimes(1);
  });

  it('does not retry on AbortError (user clicked stop)', async () => {
    const controller = new AbortController();
    const mockFetch = vi.fn().mockRejectedValue(
      new DOMException('Aborted', 'AbortError'),
    );
    vi.stubGlobal('fetch', mockFetch);

    const onReconnecting = vi.fn();
    const onAbort = vi.fn();
    await streamChat(
      { message: 'test' },
      { onReconnecting, onAbort, signal: controller.signal },
    );

    expect(mockFetch).toHaveBeenCalledTimes(1);
    expect(onReconnecting).not.toHaveBeenCalled();
    expect(onAbort).toHaveBeenCalledTimes(1);
  });

  it('aborts during retry delay', async () => {
    const controller = new AbortController();
    const mockFetch = vi.fn()
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce(makeDoneStream());
    vi.stubGlobal('fetch', mockFetch);

    const onReconnecting = vi.fn();
    const onAbort = vi.fn();
    const promise = streamChat(
      { message: 'test' },
      { onReconnecting, onAbort, signal: controller.signal },
    );

    // Wait for first call to fail and onReconnecting to fire
    await vi.advanceTimersByTimeAsync(100);

    // Abort during the 1s delay
    controller.abort();

    await vi.advanceTimersByTimeAsync(2000);
    await promise;

    expect(mockFetch).toHaveBeenCalledTimes(1);
    expect(onAbort).toHaveBeenCalledTimes(1);
    expect(onReconnecting).toHaveBeenCalledTimes(1);
  });

  it('retries when stream ends without done event', async () => {
    const emptyStream = makeStreamResponse([
      'event: thread_id\ndata: {"data":{"thread_id":"test-thread"}}\n\n',
    ]);
    const mockFetch = vi.fn()
      .mockResolvedValueOnce(emptyStream)
      .mockResolvedValueOnce(makeDoneStream());
    vi.stubGlobal('fetch', mockFetch);

    const onReconnecting = vi.fn();
    const onDone = vi.fn();
    const promise = streamChat(
      { message: 'test' },
      { onReconnecting, onDone },
    );

    await vi.advanceTimersByTimeAsync(1100);
    await promise;

    expect(mockFetch).toHaveBeenCalledTimes(2);
    expect(onReconnecting).toHaveBeenCalledTimes(1);
    expect(onDone).toHaveBeenCalledTimes(1);
  });
});
