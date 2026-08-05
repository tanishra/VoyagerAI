import { getUserId } from '@/lib/user-id';
import type { Itinerary, ComparisonData } from '@/lib/types';

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
      headers: { 'X-User-Id': getUserId() },
    });
    if (!res.ok) return { threads: [], has_more: false };
    const data = await res.json();
    // Backward-compatible: if response is an array, wrap it
    if (Array.isArray(data)) {
      return { threads: data, has_more: false };
    }
    return data;
  } catch {
    return { threads: [], has_more: false };
  }
}

export async function getThreadHistory(threadId: string): Promise<ThreadMessage[]> {
  try {
    const res = await fetch(`${API_URL}/threads/${threadId}/history`, {
      headers: { 'X-User-Id': getUserId() },
    });
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

export async function deleteThread(threadId: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_URL}/threads/${threadId}`, {
      method: 'DELETE',
      headers: { 'X-User-Id': getUserId() },
    });
    return res.ok;
  } catch {
    return false;
  }
}
