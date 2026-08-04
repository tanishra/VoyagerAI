import { getUserId } from '@/lib/user-id';

export interface ThreadMeta {
  thread_id: string;
  summary: string;
  created_at: number;
  updated_at: number;
}

export interface ThreadMessage {
  role: 'user' | 'assistant';
  content: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function listThreads(): Promise<ThreadMeta[]> {
  try {
    const res = await fetch(`${API_URL}/threads`, {
      headers: { 'X-User-Id': getUserId() },
    });
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
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
