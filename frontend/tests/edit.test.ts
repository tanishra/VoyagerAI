import { describe, it, expect, vi, beforeEach } from 'vitest';

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
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Network error')));

    const { editStream } = await import('@/lib/chat-api');
    await expect(
      editStream({ thread_id: 'thread-xyz', message: 'edited' }, {}),
    ).resolves.toBeUndefined();
  });
});
