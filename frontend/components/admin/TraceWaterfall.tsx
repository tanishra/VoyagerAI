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
  token: 'bg-primary',
  tool_start: 'bg-accent-foreground',
  tool_end: 'bg-chart-2',
  tool_error: 'bg-destructive',
  error: 'bg-destructive',
  done: 'bg-chart-2',
  cancelled: 'bg-accent-foreground',
  status: 'bg-muted-foreground',
  usage: 'bg-chart-3',
  thinking: 'bg-chart-4',
  subagent_progress: 'bg-chart-1',
};

const STATUS_BADGE: Record<string, string> = {
  done: 'text-chart-2',
  error: 'text-destructive',
  running: 'text-primary',
  cancelled: 'text-accent-foreground',
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
      <div className="text-center py-12 text-muted-foreground text-sm">
        {t('selectSessionPrompt')}
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-6 h-6 animate-spin text-primary" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <AlertCircle className="w-6 h-6 text-destructive mx-auto mb-2" />
        <p className="text-muted-foreground text-sm">{error}</p>
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
        <div className="bg-card border border-border rounded-xl p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-foreground">
              {t('traceWaterfall')}
            </h2>
            <div className="flex items-center gap-3 text-xs text-muted-foreground">
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
                className="flex items-center gap-1 text-primary hover:text-primary/80"
              >
                {t('traceViewLangSmith')}
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>
          </div>
          <div className="text-xs text-muted-foreground font-mono">
            {threadId}
          </div>
        </div>
      )}

      {/* Waterfall */}
      {events.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground text-sm">
          {t('noEvents')}
        </div>
      ) : (
        <div className="bg-card border border-border rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-muted-foreground border-b border-border bg-muted/30">
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
                        className={`border-b border-border/30 hover:bg-muted/30 ${hasDetail ? 'cursor-pointer' : ''}`}
                        onClick={() => hasDetail && toggleRow(idx)}
                      >
                        <td className="py-1.5 px-3">
                          {hasDetail && (
                            isExpanded ? <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" /> : <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" />
                          )}
                        </td>
                        <td className="py-1.5 px-2 text-foreground font-mono">
                          {evt.name || evt.event_type}
                        </td>
                        <td className="py-1.5 px-2">
                          <span className={`inline-block w-2 h-2 rounded-full ${EVENT_COLORS[evt.event_type] || 'bg-muted-foreground'}`} />
                          <span className="ml-2 text-muted-foreground">{evt.event_type}</span>
                        </td>
                        <td className="py-1.5 px-2">
                          <div className="relative h-4 bg-muted rounded">
                            <div
                              className={`absolute h-full rounded ${EVENT_COLORS[evt.event_type] || 'bg-muted-foreground'}`}
                              style={{
                                left: `${Math.min(barWidth, 100)}%`,
                                width: `${Math.max(barSize, 2)}%`,
                                opacity: 0.7,
                              }}
                            />
                          </div>
                        </td>
                        <td className="py-1.5 px-2 text-right text-muted-foreground">
                          {evt.duration_ms > 0 ? `${evt.duration_ms}ms` : '—'}
                        </td>
                        <td className="py-1.5 px-2 text-right text-muted-foreground">
                          {evt.tokens_in + evt.tokens_out > 0 ? `${evt.tokens_in}/${evt.tokens_out}` : '—'}
                        </td>
                        <td className="py-1.5 px-2 text-right text-muted-foreground">
                          {evt.cost_usd > 0 ? `$${evt.cost_usd.toFixed(4)}` : '—'}
                        </td>
                        <td className="py-1.5 px-2">
                          <span className={`text-xs ${STATUS_BADGE[status] || 'text-muted-foreground'}`}>
                            {status}
                          </span>
                        </td>
                      </tr>
                      {isExpanded && hasDetail && (
                        <tr className="border-b border-border/30 bg-muted/20">
                          <td colSpan={8} className="py-2 px-6">
                            <div className="space-y-2 text-xs">
                              {evt.input && (
                                <div>
                                  <span className="text-muted-foreground font-medium">{t('traceInput')}:</span>
                                  <pre className="mt-1 p-2 bg-card rounded text-foreground overflow-x-auto max-h-40">
                                    {typeof evt.input === 'string' ? evt.input : JSON.stringify(evt.input, null, 2)}
                                  </pre>
                                </div>
                              )}
                              {evt.output && (
                                <div>
                                  <span className="text-muted-foreground font-medium">{t('traceOutput')}:</span>
                                  <pre className="mt-1 p-2 bg-card rounded text-foreground overflow-x-auto max-h-40">
                                    {evt.output}
                                  </pre>
                                </div>
                              )}
                              {evt.error && (
                                <div>
                                  <span className="text-destructive font-medium">Error:</span>
                                  <pre className="mt-1 p-2 bg-destructive/10 rounded text-destructive overflow-x-auto max-h-40">
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
