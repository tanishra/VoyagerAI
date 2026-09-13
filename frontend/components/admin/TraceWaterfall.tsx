'use client';

import { useState, useEffect, useCallback, Fragment } from 'react';
import { Loader2, AlertCircle, ChevronDown, ChevronRight, ExternalLink, Clock, Coins, Hash } from 'lucide-react';
import { useTranslations } from 'next-intl';
import {
  getSessionDetail,
  type ObservabilityEvent,
  type ObservabilitySession,
} from '@/lib/observability-api';

interface Props {
  threadId: string | null;
}

const EVENT_COLORS: Record<string, string> = {
  token: 'bg-blue-600',
  tool_start: 'bg-yellow-600',
  tool_end: 'bg-green-600',
  tool_error: 'bg-red-600',
  error: 'bg-red-600',
  done: 'bg-green-600',
  cancelled: 'bg-yellow-600',
  status: 'bg-neutral-600',
  usage: 'bg-purple-600',
  thinking: 'bg-indigo-600',
  subagent_progress: 'bg-cyan-600',
};

const STATUS_BADGE: Record<string, string> = {
  done: 'text-green-400',
  error: 'text-red-400',
  running: 'text-blue-400',
  cancelled: 'text-yellow-400',
};

export function TraceWaterfall({ threadId }: Props) {
  const t = useTranslations('admin');
  const [session, setSession] = useState<ObservabilitySession | null>(null);
  const [events, setEvents] = useState<ObservabilityEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());

  const fetchDetail = useCallback(async () => {
    if (!threadId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getSessionDetail(threadId);
      setSession(data.session);
      setEvents(data.events);
    } catch {
      setError(t('loadError'));
    } finally {
      setLoading(false);
    }
  }, [threadId, t]);

  useEffect(() => {
    fetchDetail();
  }, [fetchDetail]);

  function toggleRow(idx: number) {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  }

  if (!threadId) {
    return (
      <div className="text-center py-12 text-neutral-500 text-sm">
        {t('selectSessionPrompt')}
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-6 h-6 animate-spin text-neutral-500" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <AlertCircle className="w-6 h-6 text-red-400 mx-auto mb-2" />
        <p className="text-neutral-400 text-sm">{error}</p>
      </div>
    );
  }

  // Calculate max duration for bar scaling
  const maxDuration = Math.max(...events.map((e) => e.duration_ms || 0), 1);
  const sessionStart = session?.start_time || 0;
  const sessionEnd = session?.end_time || Date.now() / 1000;
  const totalDuration = (sessionEnd - sessionStart) * 1000; // ms

  return (
    <div className="space-y-4">
      {/* Session summary */}
      {session && (
        <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-neutral-300">
              {t('traceWaterfall')}
            </h2>
            <div className="flex items-center gap-3 text-xs text-neutral-400">
              <span className="flex items-center gap-1">
                <Clock className="w-3.5 h-3.5" />
                {session.duration_seconds ? `${session.duration_seconds.toFixed(1)}s` : '—'}
              </span>
              <span className="flex items-center gap-1">
                <Hash className="w-3.5 h-3.5" />
                {session.total_tokens_in + session.total_tokens_out} tokens
              </span>
              <span className="flex items-center gap-1">
                <Coins className="w-3.5 h-3.5" />
                ${session.total_cost_usd.toFixed(4)}
              </span>
              <a
                href={`https://smith.langchain.com/o/default/projects/p/${process.env.NEXT_PUBLIC_LANGSMITH_PROJECT || 'voyagerai'}/sessions?thread_id=${encodeURIComponent(threadId)}`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-blue-400 hover:text-blue-300"
              >
                {t('traceViewLangSmith')}
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>
          </div>
          <div className="text-xs text-neutral-500 font-mono">
            {threadId}
          </div>
        </div>
      )}

      {/* Waterfall */}
      {events.length === 0 ? (
        <div className="text-center py-12 text-neutral-500 text-sm">
          {t('noEvents')}
        </div>
      ) : (
        <div className="bg-neutral-900 border border-neutral-800 rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-neutral-400 border-b border-neutral-800 bg-neutral-900/50">
                  <th className="text-left py-2 px-3 font-medium w-8"></th>
                  <th className="text-left py-2 px-2 font-medium">{t('traceName')}</th>
                  <th className="text-left py-2 px-2 font-medium">{t('traceType')}</th>
                  <th className="text-left py-2 px-2 font-medium w-40">{t('traceTimeline')}</th>
                  <th className="text-right py-2 px-2 font-medium">{t('traceDuration')}</th>
                  <th className="text-right py-2 px-2 font-medium">{t('traceTokens')}</th>
                  <th className="text-right py-2 px-2 font-medium">{t('traceCost')}</th>
                  <th className="text-left py-2 px-2 font-medium">{t('traceStatus')}</th>
                </tr>
              </thead>
              <tbody>
                {events.map((evt, idx) => {
                  const isExpanded = expandedRows.has(idx);
                  const hasDetail = evt.input || evt.output || evt.error;
                  const barWidth = totalDuration > 0
                    ? ((evt.timestamp - sessionStart) * 1000 / totalDuration) * 100
                    : 0;
                  const barSize = Math.min((evt.duration_ms / maxDuration) * 100, 100);
                  const status = evt.error ? 'error' : evt.event_type === 'done' ? 'done' : evt.event_type === 'tool_end' ? 'done' : 'running';
                  return (
                    <Fragment key={idx}>
                      <tr
                        className={`border-b border-neutral-800/30 hover:bg-neutral-800/30 ${hasDetail ? 'cursor-pointer' : ''}`}
                        onClick={() => hasDetail && toggleRow(idx)}
                      >
                        <td className="py-1.5 px-3">
                          {hasDetail && (
                            isExpanded ? <ChevronDown className="w-3.5 h-3.5 text-neutral-500" /> : <ChevronRight className="w-3.5 h-3.5 text-neutral-500" />
                          )}
                        </td>
                        <td className="py-1.5 px-2 text-neutral-300 font-mono">
                          {evt.name || evt.event_type}
                        </td>
                        <td className="py-1.5 px-2">
                          <span className={`inline-block w-2 h-2 rounded-full ${EVENT_COLORS[evt.event_type] || 'bg-neutral-600'}`} />
                          <span className="ml-2 text-neutral-400">{evt.event_type}</span>
                        </td>
                        <td className="py-1.5 px-2">
                          <div className="relative h-4 bg-neutral-800 rounded">
                            <div
                              className={`absolute h-full rounded ${EVENT_COLORS[evt.event_type] || 'bg-neutral-600'}`}
                              style={{
                                left: `${Math.min(barWidth, 100)}%`,
                                width: `${Math.max(barSize, 2)}%`,
                                opacity: 0.7,
                              }}
                            />
                          </div>
                        </td>
                        <td className="py-1.5 px-2 text-right text-neutral-400">
                          {evt.duration_ms > 0 ? `${evt.duration_ms}ms` : '—'}
                        </td>
                        <td className="py-1.5 px-2 text-right text-neutral-400">
                          {evt.tokens_in + evt.tokens_out > 0 ? `${evt.tokens_in}/${evt.tokens_out}` : '—'}
                        </td>
                        <td className="py-1.5 px-2 text-right text-neutral-400">
                          {evt.cost_usd > 0 ? `$${evt.cost_usd.toFixed(4)}` : '—'}
                        </td>
                        <td className="py-1.5 px-2">
                          <span className={`text-xs ${STATUS_BADGE[status] || 'text-neutral-400'}`}>
                            {status}
                          </span>
                        </td>
                      </tr>
                      {isExpanded && hasDetail && (
                        <tr className="border-b border-neutral-800/30 bg-neutral-950/50">
                          <td colSpan={8} className="py-2 px-6">
                            <div className="space-y-2 text-xs">
                              {evt.input && (
                                <div>
                                  <span className="text-neutral-500 font-medium">{t('traceInput')}:</span>
                                  <pre className="mt-1 p-2 bg-neutral-900 rounded text-neutral-300 overflow-x-auto max-h-40">
                                    {typeof evt.input === 'string' ? evt.input : JSON.stringify(evt.input, null, 2)}
                                  </pre>
                                </div>
                              )}
                              {evt.output && (
                                <div>
                                  <span className="text-neutral-500 font-medium">{t('traceOutput')}:</span>
                                  <pre className="mt-1 p-2 bg-neutral-900 rounded text-neutral-300 overflow-x-auto max-h-40">
                                    {evt.output}
                                  </pre>
                                </div>
                              )}
                              {evt.error && (
                                <div>
                                  <span className="text-red-400 font-medium">Error:</span>
                                  <pre className="mt-1 p-2 bg-red-950/30 rounded text-red-300 overflow-x-auto max-h-40">
                                    {evt.error}
                                  </pre>
                                </div>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
