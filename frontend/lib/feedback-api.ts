const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface FeedbackPayload {
  thread_id: string;
  message_id: string;
  rating: 'up' | 'down';
  comment?: string;
}

export interface FeedbackAggregate {
  total_up: number;
  total_down: number;
  total_ratings: number;
  satisfaction_ratio: number;
  recent_comments: { comment: string; thread_id: string; created_at: number }[];
}

export async function submitFeedback(
  payload: FeedbackPayload,
): Promise<{ status: string; rating: string }> {
  const res = await fetch(`${API_BASE}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(payload),
  });

  if (res.status === 401) {
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }
  if (!res.ok) {
    throw new Error(`Failed to submit feedback: ${res.status}`);
  }
  return res.json();
}

export async function getFeedbackAggregate(): Promise<FeedbackAggregate> {
  const res = await fetch(`${API_BASE}/admin/feedback`, {
    credentials: 'include',
  });

  if (res.status === 403) {
    throw new Error('Access denied');
  }
  if (res.status === 401) {
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }
  if (!res.ok) {
    throw new Error(`Failed to fetch feedback: ${res.status}`);
  }
  return res.json();
}
