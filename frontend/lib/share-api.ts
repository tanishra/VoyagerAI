import type { Itinerary } from '@/lib/types';
import { getApiHeaders } from './api-headers';

export interface ShareLink {
  token: string;
  thread_id: string;
  destination: string;
  created_at: number;
  expires_at: number;
  share_url: string;
}

export interface ShareData {
  itinerary: Itinerary;
  destination: string;
  created_at: number;
  expires_at: number;
  image_base64?: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function createShare(threadId: string): Promise<{ share_url: string; expires_at: number; destination: string }> {
  const res = await fetch(`${API_URL}/share/${threadId}`, {
    method: 'POST',
    headers: getApiHeaders(),
    credentials: 'include',
  });
  if (res.status === 401) {
    window.location.href = '/login';
    throw new Error('Not authenticated');
  }
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(text || 'Failed to create share link');
  }
  return res.json();
}

export async function getShare(token: string): Promise<ShareData | null> {
  const res = await fetch(`${API_URL}/share/${token}`, {
    headers: getApiHeaders(),
  });
  if (!res.ok) return null;
  return res.json();
}

export async function revokeShare(token: string): Promise<boolean> {
  const res = await fetch(`${API_URL}/share/${token}`, {
    method: 'DELETE',
    headers: getApiHeaders(),
    credentials: 'include',
  });
  if (res.status === 401) {
    window.location.href = '/login';
    return false;
  }
  return res.ok;
}

export async function listShares(): Promise<ShareLink[]> {
  const res = await fetch(`${API_URL}/shares`, {
    headers: getApiHeaders(),
    credentials: 'include',
  });
  if (res.status === 401) {
    window.location.href = '/login';
    return [];
  }
  if (!res.ok) return [];
  return res.json();
}

export async function exportItinerary(threadId: string, format: 'json' | 'markdown' | 'ical'): Promise<Blob> {
  const res = await fetch(`${API_URL}/export/${threadId}?fmt=${format}`, {
    headers: getApiHeaders(),
    credentials: 'include',
  });
  if (res.status === 401) {
    window.location.href = '/login';
    throw new Error('Not authenticated');
  }
  if (!res.ok) {
    throw new Error('Failed to export itinerary');
  }
  return res.blob();
}
