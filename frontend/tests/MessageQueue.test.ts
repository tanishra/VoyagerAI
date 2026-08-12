import { describe, it, expect, vi, beforeEach } from 'vitest';

// In-memory queue store
const queueStore = new Map<string, Record<string, unknown>>();

vi.mock('@/lib/offline-db', () => ({
  putQueuedMessage: vi.fn(async (msg: Record<string, unknown>) => { queueStore.set(msg.id as string, msg); }),
  getQueuedMessages: vi.fn(async () =>
    Array.from(queueStore.values()).sort((a, b) => (a.created_at as number) - (b.created_at as number)),
  ),
  deleteQueuedMessage: vi.fn(async (id: string) => { queueStore.delete(id); }),
}));

import { queueMessage, replayQueuedMessages, getQueuedCount } from '@/lib/message-queue';

beforeEach(() => {
  queueStore.clear();
});

describe('message-queue', () => {
  it('queueMessage stores message and returns it with an id', async () => {
    const msg = await queueMessage('t1', 'Hello');
    expect(msg.id).toBeTruthy();
    expect(msg.content).toBe('Hello');
    expect(msg.thread_id).toBe('t1');
    expect(msg.created_at).toBeGreaterThan(0);

    const count = await getQueuedCount();
    expect(count).toBe(1);
  });

  it('replayQueuedMessages sends all queued messages in order', async () => {
    await queueMessage('t1', 'First');
    await queueMessage('t1', 'Second');

    const sent: string[] = [];
    const sentCount = await replayQueuedMessages(async (msg) => {
      sent.push(msg.content);
      return true;
    });

    expect(sentCount).toBe(2);
    expect(sent).toEqual(['First', 'Second']);
  });

  it('replayQueuedMessages deletes successfully sent messages', async () => {
    await queueMessage('t1', 'Hello');

    await replayQueuedMessages(async () => true);

    const count = await getQueuedCount();
    expect(count).toBe(0);
  });

  it('replayQueuedMessages stops on first failure and keeps unsent messages', async () => {
    await queueMessage('t1', 'First');
    await queueMessage('t1', 'Second');
    await queueMessage('t1', 'Third');

    let callCount = 0;
    const sentCount = await replayQueuedMessages(async () => {
      callCount++;
      if (callCount === 2) return false;
      return true;
    });

    expect(sentCount).toBe(1);
    // Second message failed, so it and Third should still be queued
    const count = await getQueuedCount();
    expect(count).toBe(2);
  });

  it('replayQueuedMessages stops on exception and keeps unsent messages', async () => {
    await queueMessage('t1', 'First');
    await queueMessage('t1', 'Second');

    const sentCount = await replayQueuedMessages(async (msg) => {
      if (msg.content === 'Second') throw new Error('network error');
      return true;
    });

    expect(sentCount).toBe(1);
    const count = await getQueuedCount();
    expect(count).toBe(1);
  });

  it('replayQueuedMessages returns 0 when queue is empty', async () => {
    const sentCount = await replayQueuedMessages(async () => true);
    expect(sentCount).toBe(0);
  });
});
