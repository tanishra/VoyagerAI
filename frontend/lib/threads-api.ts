import type { Itinerary, ComparisonData } from '@/lib/types';
import { putThreads, getAllCachedThreads, putThreadHistory, getCachedThreadHistory, clearOldThreads } from './offline-db';

export interface ThreadMeta {
  thread_id: string;
  summary: string;
  created_at: number;
  updated_at: number;
  status: string;
  message_count: number;
}

export interface ThreadListResponse {
  threads: ThreadMeta[];
  has_more: boolean;
}

export interface ThreadMessage {
  role: 'user' | 'assistant';
  content: string;
  itinerary?: Itinerary;
  comparison?: ComparisonData;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function listThreads(offset: number = 0): Promise<ThreadListResponse> {
  try {
    const res = await fetch(`${API_URL}/threads?offset=${offset}`, {
      credentials: 'include',
    });
    if (res.status === 401) {
      window.location.href = '/login';
      return { threads: [], has_more: false };
    }
    if (!res.ok) return { threads: [], has_more: false };
    const data = await res.json();
    // Backward-compatible: if response is an array, wrap it
    const result = Array.isArray(data)
      ? { threads: data, has_more: false }
      : data;
    // Write-through cache: store threads in IndexedDB for offline access
    if (result.threads.length > 0) {
      putThreads(result.threads).catch(() => {});
      clearOldThreads().catch(() => {});
    }
    return result;
  } catch {
    // Network failure — fall back to cached threads
    const cached = await getAllCachedThreads();
    return { threads: cached, has_more: false };
  }
}

export async function getThreadHistory(threadId: string): Promise<ThreadMessage[]> {
  try {
    const res = await fetch(`${API_URL}/threads/${threadId}/history`, {
      credentials: 'include',
    });
    if (res.status === 401) {
      window.location.href = '/login';
      return [];
    }
    if (!res.ok) return [];
    const messages = await res.json();
    // Write-through cache: store history in IndexedDB for offline access
    putThreadHistory(threadId, messages).catch(() => {});
    return messages;
  } catch {
    // Network failure — fall back to cached history
    return getCachedThreadHistory(threadId);
  }
}

export async function deleteThread(threadId: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_URL}/threads/${threadId}`, {
      method: 'DELETE',
      credentials: 'include',
    });
    if (res.status === 401) {
      window.location.href = '/login';
      return false;
    }
    return res.ok;
  } catch {
    return false;
  }
}
