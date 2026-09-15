const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
import { withAuthParams } from './api-headers';

export interface ObservabilitySession {
  thread_id: string;
  user_hash: string;
  start_time: number;
  end_time: number | null;
  duration_seconds: number | null;
  status: string;
  subagent_count: number;
  tool_call_count: number;
  total_tokens_in: number;
  total_tokens_out: number;
  total_cost_usd: number;
  model_used: string;
}

export interface ObservabilityEvent {
  thread_id: string;
  event_type: string;
  run_id: string;
  name: string;
  parent_run_id: string;
  input: Record<string, unknown> | string | null;
  output: string;
  error: string;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  duration_ms: number;
  model: string;
  timestamp: number;
}

export interface SessionListResponse {
  sessions: ObservabilitySession[];
  total: number;
  limit: number;
  offset: number;
}

export interface SessionDetailResponse {
  session: ObservabilitySession;
  events: ObservabilityEvent[];
}

export interface ErrorEvent {
  thread_id: string;
  subagent_name: string;
  tool_name: string;
  error_message: string;
  timestamp: number;
}

export interface ErrorSummary {
  total_errors: number;
  by_subagent: { name: string; count: number }[];
  by_tool: { name: string; count: number }[];
  per_day: { date: string; count: number }[];
}

export interface UsageData {
  per_day: {
    date: string;
    tokens_in: number;
    tokens_out: number;
    cost: number;
    sessions: number;
  }[];
  per_subagent: {
    name: string;
    tokens_in: number;
    tokens_out: number;
    cost: number;
  }[];
  per_user: {
    user_hash: string;
    sessions: number;
    cost: number;
  }[];
  totals: {
    tokens_in: number;
    tokens_out: number;
    cost: number;
    sessions: number;
  };
}

async function _fetch<T>(path: string): Promise<T> {
  const res = await fetch(withAuthParams(`${API_BASE}${path}`), {
    credentials: 'include',
  });
  if (res.status === 401) {
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }
  if (res.status === 403) {
    throw new Error('Access denied');
  }
  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }
  return res.json();
}

export function getSessions(params?: {
  from_ts?: number;
  to_ts?: number;
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<SessionListResponse> {
  const qs = new URLSearchParams();
  if (params?.from_ts) qs.set('from_ts', String(params.from_ts));
  if (params?.to_ts) qs.set('to_ts', String(params.to_ts));
  if (params?.status) qs.set('status', params.status);
  if (params?.limit) qs.set('limit', String(params.limit));
  if (params?.offset) qs.set('offset', String(params.offset));
  return _fetch<SessionListResponse>(`/admin/observability/sessions?${qs}`);
}

export function getSessionDetail(threadId: string): Promise<SessionDetailResponse> {
  return _fetch<SessionDetailResponse>(`/admin/observability/sessions/${encodeURIComponent(threadId)}`);
}

export function getSessionEvents(threadId: string): Promise<ObservabilityEvent[]> {
  return _fetch<ObservabilityEvent[]>(`/admin/observability/sessions/${encodeURIComponent(threadId)}/events`);
}

export function getErrors(params?: {
  from_ts?: number;
  to_ts?: number;
  subagent?: string;
  tool?: string;
  limit?: number;
}): Promise<ErrorEvent[]> {
  const qs = new URLSearchParams();
  if (params?.from_ts) qs.set('from_ts', String(params.from_ts));
  if (params?.to_ts) qs.set('to_ts', String(params.to_ts));
  if (params?.subagent) qs.set('subagent', params.subagent);
  if (params?.tool) qs.set('tool', params.tool);
  if (params?.limit) qs.set('limit', String(params.limit));
  return _fetch<ErrorEvent[]>(`/admin/observability/errors?${qs}`);
}

export function getErrorSummary(params?: {
  from_ts?: number;
  to_ts?: number;
}): Promise<ErrorSummary> {
  const qs = new URLSearchParams();
  if (params?.from_ts) qs.set('from_ts', String(params.from_ts));
  if (params?.to_ts) qs.set('to_ts', String(params.to_ts));
  return _fetch<ErrorSummary>(`/admin/observability/errors/summary?${qs}`);
}

export function getUsage(params?: {
  from_ts?: number;
  to_ts?: number;
}): Promise<UsageData> {
  const qs = new URLSearchParams();
  if (params?.from_ts) qs.set('from_ts', String(params.from_ts));
  if (params?.to_ts) qs.set('to_ts', String(params.to_ts));
  return _fetch<UsageData>(`/admin/observability/usage?${qs}`);
}
