import { openDB, type DBSchema, type IDBPDatabase } from 'idb';
import type { ThreadMeta, ThreadMessage } from './threads-api';

export interface QueuedMessage {
  id: string;
  thread_id: string | null;
  content: string;
  created_at: number;
}

interface VoyagerDB extends DBSchema {
  threads: {
    key: string;
    value: ThreadMeta;
  };
  history: {
    key: string;
    value: ThreadMessage[];
  };
  queue: {
    key: string;
    value: QueuedMessage;
  };
}

const DB_NAME = 'voyagerai_offline';
const DB_VERSION = 1;
const MAX_CACHED_THREADS = 10;

let dbPromise: Promise<IDBPDatabase<VoyagerDB>> | null = null;

function getDB(): Promise<IDBPDatabase<VoyagerDB>> {
  if (typeof window === 'undefined') {
    return Promise.reject(new Error('IndexedDB not available on server'));
  }
  if (!dbPromise) {
    dbPromise = openDB<VoyagerDB>(DB_NAME, DB_VERSION, {
      upgrade(db) {
        if (!db.objectStoreNames.contains('threads')) {
          db.createObjectStore('threads', { keyPath: 'thread_id' });
        }
        if (!db.objectStoreNames.contains('history')) {
          db.createObjectStore('history');
        }
        if (!db.objectStoreNames.contains('queue')) {
          db.createObjectStore('queue', { keyPath: 'id' });
        }
      },
    });
  }
  return dbPromise;
}

// ─── Thread metadata ──────────────────────────────────────────

export async function putThread(thread: ThreadMeta): Promise<void> {
  try {
    const db = await getDB();
    await db.put('threads', thread);
  } catch {
    // IndexedDB unavailable — silently skip
  }
}

export async function putThreads(threads: ThreadMeta[]): Promise<void> {
  try {
    const db = await getDB();
    const tx = db.transaction('threads', 'readwrite');
    for (const t of threads) {
      await tx.store.put(t);
    }
    await tx.done;
  } catch {
    // silently skip
  }
}

export async function getAllCachedThreads(): Promise<ThreadMeta[]> {
  try {
    const db = await getDB();
    const all = await db.getAll('threads');
    return all
      .sort((a, b) => b.updated_at - a.updated_at)
      .slice(0, MAX_CACHED_THREADS);
  } catch {
    return [];
  }
}

export async function clearOldThreads(keepCount: number = MAX_CACHED_THREADS): Promise<void> {
  try {
    const db = await getDB();
    const all = await db.getAll('threads');
    const sorted = all.sort((a, b) => b.updated_at - a.updated_at);
    const toRemove = sorted.slice(keepCount);
    const tx = db.transaction('threads', 'readwrite');
    for (const t of toRemove) {
      await tx.store.delete(t.thread_id);
    }
    await tx.done;
  } catch {
    // silently skip
  }
}

// ─── Thread history ───────────────────────────────────────────

export async function putThreadHistory(threadId: string, messages: ThreadMessage[]): Promise<void> {
  try {
    const db = await getDB();
    await db.put('history', messages, threadId);
  } catch {
    // silently skip
  }
}

export async function getCachedThreadHistory(threadId: string): Promise<ThreadMessage[]> {
  try {
    const db = await getDB();
    return (await db.get('history', threadId)) ?? [];
  } catch {
    return [];
  }
}

// ─── Message queue ────────────────────────────────────────────

export async function putQueuedMessage(msg: QueuedMessage): Promise<void> {
  try {
    const db = await getDB();
    await db.put('queue', msg);
  } catch {
    // silently skip
  }
}

export async function getQueuedMessages(): Promise<QueuedMessage[]> {
  try {
    const db = await getDB();
    const all = await db.getAll('queue');
    return all.sort((a, b) => a.created_at - b.created_at);
  } catch {
    return [];
  }
}

export async function deleteQueuedMessage(id: string): Promise<void> {
  try {
    const db = await getDB();
    await db.delete('queue', id);
  } catch {
    // silently skip
  }
}
