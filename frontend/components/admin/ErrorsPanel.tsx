'use client';

import { useState, useEffect, useCallback } from 'react';
import { Loader2, AlertCircle, AlertTriangle } from 'lucide-react';
import { useTranslations } from 'next-intl';
import {
  getErrorSummary,
  getErrors,
  type ErrorSummary,
  type ErrorEvent,
} from '@/lib/observability-api';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';

export function ErrorsPanel() {
  const t = useTranslations('admin');
  const [summary, setSummary] = useState<ErrorSummary | null>(null);
  const [errors, setErrors] = useState<ErrorEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [sum, errs] = await Promise.all([
        getErrorSummary(),
        getErrors({ limit: 50 }),
      ]);
      setSummary(sum);
      setErrors(errs);
    } catch {
      setError(t('loadError'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchAll();
  }, [fetchAll]);

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

  return (
    <div className="space-y-6">
      {/* Summary cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-card border border-border rounded-xl p-4">
          <div className="flex items-center gap-2 text-muted-foreground mb-2">
            <AlertTriangle className="w-5 h-5" />
            <span className="text-sm">{t('totalErrors')}</span>
          </div>
          <p className="text-lg font-semibold text-foreground">{summary?.total_errors || 0}</p>
        </div>
        <div className="bg-card border border-border rounded-xl p-4">
          <div className="flex items-center gap-2 text-muted-foreground mb-2">
            <span className="text-sm">{t('errorSubagents')}</span>
          </div>
          <p className="text-lg font-semibold text-foreground">{summary?.by_subagent.length || 0}</p>
        </div>
        <div className="bg-card border border-border rounded-xl p-4">
          <div className="flex items-center gap-2 text-muted-foreground mb-2">
            <span className="text-sm">{t('errorTools')}</span>
          </div>
          <p className="text-lg font-semibold text-foreground">{summary?.by_tool.length || 0}</p>
        </div>
      </div>

      {/* Error rate trend chart */}
      {summary && summary.per_day.length > 0 && (
        <div className="bg-card border border-border rounded-xl p-6">
          <h2 className="text-lg font-semibold text-foreground mb-4">{t('errorRateTrend')}</h2>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={summary.per_day}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="date" stroke="var(--muted-foreground)" fontSize={12} />
              <YAxis stroke="var(--muted-foreground)" fontSize={12} allowDecimals={false} />
              <Tooltip
                contentStyle={{ backgroundColor: 'var(--card)', border: '1px solid var(--border)', borderRadius: '8px' }}
                labelStyle={{ color: 'var(--muted-foreground)' }}
              />
              <Line type="monotone" dataKey="count" stroke="var(--destructive)" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Error breakdown */}
      {summary && summary.by_subagent.length > 0 && (
        <div className="bg-card border border-border rounded-xl p-6">
          <h2 className="text-lg font-semibold text-foreground mb-4">{t('errorBreakdown')}</h2>
          <div className="space-y-2">
            {summary.by_subagent.map((item) => (
              <div key={item.name} className="flex items-center justify-between py-1.5 border-b border-border/50">
                <span className="text-sm text-foreground font-mono">{item.name}</span>
                <span className="text-sm text-destructive">{item.count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent errors */}
      <div className="bg-card border border-border rounded-xl p-6">
        <h2 className="text-lg font-semibold text-foreground mb-4">{t('errorRecent')}</h2>
        {errors.length === 0 ? (
          <p className="text-muted-foreground text-sm">{t('noErrors')}</p>
        ) : (
          <div className="space-y-3">
            {errors.map((err, idx) => (
              <div key={idx} className="border border-border rounded-lg p-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-muted-foreground font-mono">
                    {err.subagent_name || err.tool_name || 'unknown'}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {new Date(err.timestamp * 1000).toLocaleString()}
                  </span>
                </div>
                <p className="text-xs text-destructive font-mono break-all">
                  {err.error_message}
                </p>
                <p className="text-xs text-muted-foreground/60 mt-1 font-mono">
                  {err.thread_id}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
