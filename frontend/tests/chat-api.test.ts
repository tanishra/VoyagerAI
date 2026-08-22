import { describe, it, expect, vi, beforeEach } from 'vitest';
import { cancelStream } from '@/lib/chat-api';

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
