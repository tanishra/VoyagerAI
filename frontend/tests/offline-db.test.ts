import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock idb with in-memory store
const memStore: Record<string, Map<string, Record<string, unknown>>> = {
  threads: new Map(),
  history: new Map(),
  queue: new Map(),
};

vi.mock('idb', () => ({
  openDB: vi.fn(() => Promise.resolve({
    put: vi.fn(async (store: string, value: Record<string, unknown>, key?: string) => {
      if (key !== undefined) {
        memStore[store].set(key, value);
      } else if (value && value.thread_id) {
        memStore[store].set(value.thread_id as string, value);
      } else if (value && value.id) {
        memStore[store].set(value.id as string, value);
      }
    }),
    putMany: vi.fn(),
    get: vi.fn(async (store: string, key: string) => memStore[store].get(key) ?? null),
    getAll: vi.fn(async (store: string) => Array.from(memStore[store].values())),
    delete: vi.fn(async (store: string, key: string) => { memStore[store].delete(key); }),
    transaction: vi.fn(() => ({
      store: {
        put: vi.fn(async (value: Record<string, unknown>) => {
          if (value && value.thread_id) {
            memStore.threads.set(value.thread_id as string, value);
          }
        }),
        delete: vi.fn(async (key: string) => { memStore.threads.delete(key); }),
      },
      done: Promise.resolve(),
    })),
  })),
}));

import {
  putThread,
  putThreads,
  getAllCachedThreads,
  clearOldThreads,
  putThreadHistory,
  getCachedThreadHistory,
  putQueuedMessage,
  getQueuedMessages,
  deleteQueuedMessage,
  type QueuedMessage,
} from '@/lib/offline-db';
import type { ThreadMeta, ThreadMessage } from '@/lib/threads-api';

function makeThread(id: string, updated: number): ThreadMeta {
  return { thread_id: id, summary: `Thread ${id}`, created_at: 100, updated_at: updated, status: 'idle', message_count: 1 };
}

beforeEach(() => {
  memStore.threads.clear();
  memStore.history.clear();
  memStore.queue.clear();
});

describe('offline-db', () => {
  it('putThread and getAllCachedThreads round trip', async () => {
    const t = makeThread('t1', 200);
    await putThread(t);
    const all = await getAllCachedThreads();
    expect(all).toHaveLength(1);
    expect(all[0].thread_id).toBe('t1');
  });

  it('getAllCachedThreads sorts by updated_at desc', async () => {
    await putThread(makeThread('old', 100));
    await putThread(makeThread('new', 300));
    await putThread(makeThread('mid', 200));
    const all = await getAllCachedThreads();
    expect(all[0].thread_id).toBe('new');
    expect(all[1].thread_id).toBe('mid');
    expect(all[2].thread_id).toBe('old');
  });

  it('putThreads batches multiple threads', async () => {
    await putThreads([makeThread('a', 100), makeThread('b', 200)]);
    const all = await getAllCachedThreads();
    expect(all).toHaveLength(2);
  });

  it('clearOldThreads evicts beyond keepCount', async () => {
    await putThreads([
      makeThread('t1', 500),
      makeThread('t2', 400),
      makeThread('t3', 300),
    ]);
    await clearOldThreads(2);
    const all = await getAllCachedThreads();
    expect(all).toHaveLength(2);
    expect(all.find((t) => t.thread_id === 't3')).toBeUndefined();
  });

  it('putThreadHistory and getCachedThreadHistory round trip', async () => {
    const msgs: ThreadMessage[] = [
      { role: 'user', content: 'Hello' },
      { role: 'assistant', content: 'Hi there' },
    ];
    await putThreadHistory('t1', msgs);
    const cached = await getCachedThreadHistory('t1');
    expect(cached).toHaveLength(2);
    expect(cached[0].content).toBe('Hello');
  });

  it('getCachedThreadHistory returns empty for missing thread', async () => {
    const cached = await getCachedThreadHistory('nonexistent');
    expect(cached).toEqual([]);
  });

  it('putQueuedMessage and getQueuedMessages round trip', async () => {
    const msg: QueuedMessage = { id: 'q1', thread_id: 't1', content: 'Test', created_at: 100 };
    await putQueuedMessage(msg);
    const all = await getQueuedMessages();
    expect(all).toHaveLength(1);
    expect(all[0].content).toBe('Test');
  });

  it('getQueuedMessages sorts by created_at asc', async () => {
    await putQueuedMessage({ id: 'q2', thread_id: null, content: 'Second', created_at: 200 });
    await putQueuedMessage({ id: 'q1', thread_id: null, content: 'First', created_at: 100 });
    const all = await getQueuedMessages();
    expect(all[0].id).toBe('q1');
    expect(all[1].id).toBe('q2');
  });

  it('deleteQueuedMessage removes from store', async () => {
    await putQueuedMessage({ id: 'q1', thread_id: null, content: 'Test', created_at: 100 });
    await deleteQueuedMessage('q1');
    const all = await getQueuedMessages();
    expect(all).toHaveLength(0);
  });
});
