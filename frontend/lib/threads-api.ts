import type { Itinerary, ComparisonData, ActivityData, BranchInfo } from '@/lib/types';
import { putThreads, getAllCachedThreads, putThreadHistory, getCachedThreadHistory, clearOldThreads } from './offline-db';

export interface ThreadMeta {
  thread_id: string;
  summary: string;
  created_at: number;
  updated_at: number;
  status: string;
  message_count: number;
  pinned?: boolean;
  pinned_at?: number;
}

export interface ThreadListResponse {
  threads: ThreadMeta[];
  has_more: boolean;
}

export interface SearchResult {
  thread_id: string;
  summary: string;
  snippet: string;
  updated_at: number;
  message_count: number;
}

export interface SearchResponse {
  results: SearchResult[];
  total: number;
  has_more: boolean;
}

export interface ThreadMessage {
  role: 'user' | 'assistant';
  content: string;
  itinerary?: Itinerary;
  comparison?: ComparisonData;
  activity?: ActivityData;
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

export async function getThreadHistory(threadId: string, checkpointId?: string): Promise<ThreadMessage[]> {
  try {
    const url = new URL(`${API_URL}/threads/${threadId}/history`);
    if (checkpointId) {
      url.searchParams.set('checkpoint_id', checkpointId);
    }
    const res = await fetch(url.toString(), {
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

export async function getBranches(threadId: string): Promise<BranchInfo[]> {
  try {
    const res = await fetch(`${API_URL}/threads/${threadId}/branches`, {
      credentials: 'include',
    });
    if (res.status === 401) {
      window.location.href = '/login';
      return [];
    }
    if (!res.ok) return [];
    const data = await res.json();
    return data.branches ?? [];
  } catch {
    return [];
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

export async function searchThreads(query: string, offset: number = 0): Promise<SearchResponse> {
  try {
    const params = new URLSearchParams({ q: query, offset: String(offset) });
    const res = await fetch(`${API_URL}/threads/search?${params}`, {
      credentials: 'include',
    });
    if (res.status === 401) {
      window.location.href = '/login';
      return { results: [], total: 0, has_more: false };
    }
    if (!res.ok) return { results: [], total: 0, has_more: false };
    return await res.json();
  } catch {
    return { results: [], total: 0, has_more: false };
  }
}

export async function updateThread(threadId: string, pinned: boolean): Promise<boolean> {
  try {
    const res = await fetch(`${API_URL}/threads/${threadId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ pinned }),
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
