'use client';

import { useState, useEffect, useCallback } from 'react';
import { Loader2, AlertCircle, Coins, Hash, MessageSquare } from 'lucide-react';
import { useTranslations } from 'next-intl';
import {
  getUsage,
  type UsageData,
} from '@/lib/observability-api';
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';

export function UsagePanel() {
  const t = useTranslations('admin');
  const [data, setData] = useState<UsageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchUsage = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const usage = await getUsage();
      setData(usage);
    } catch {
      setError(t('loadError'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchUsage();
  }, [fetchUsage]);

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

  if (!data) return null;

  return (
    <div className="space-y-6">
      {/* Summary cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-card border border-border rounded-xl p-4">
          <div className="flex items-center gap-2 text-muted-foreground mb-2">
            <Coins className="w-5 h-5" />
            <span className="text-sm">{t('totalCost')}</span>
          </div>
          <p className="text-lg font-semibold text-foreground">${data.totals.cost.toFixed(4)}</p>
        </div>
        <div className="bg-card border border-border rounded-xl p-4">
          <div className="flex items-center gap-2 text-muted-foreground mb-2">
            <Hash className="w-5 h-5" />
            <span className="text-sm">{t('tokensUsed')}</span>
          </div>
          <p className="text-lg font-semibold text-foreground">
            {(data.totals.tokens_in / 1000).toFixed(1)}k / {(data.totals.tokens_out / 1000).toFixed(1)}k
          </p>
        </div>
        <div className="bg-card border border-border rounded-xl p-4">
          <div className="flex items-center gap-2 text-muted-foreground mb-2">
            <MessageSquare className="w-5 h-5" />
            <span className="text-sm">{t('totalConversations')}</span>
          </div>
          <p className="text-lg font-semibold text-foreground">{data.totals.sessions}</p>
        </div>
        <div className="bg-card border border-border rounded-xl p-4">
          <div className="flex items-center gap-2 text-muted-foreground mb-2">
            <span className="text-sm">{t('usagePerSubagent')}</span>
          </div>
          <p className="text-lg font-semibold text-foreground">{data.per_subagent.length}</p>
        </div>
      </div>

      {/* Daily usage chart */}
      {data.per_day.length > 0 && (
        <div className="bg-card border border-border rounded-xl p-6">
          <h2 className="text-lg font-semibold text-foreground mb-4">{t('usagePerDay')}</h2>
          <ResponsiveContainer width="100%" height={250}>
            <AreaChart data={data.per_day}>
              <defs>
                <linearGradient id="tokenGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--chart-1)" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="var(--chart-1)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="date" stroke="var(--muted-foreground)" fontSize={12} />
              <YAxis stroke="var(--muted-foreground)" fontSize={12} />
              <Tooltip
                contentStyle={{ backgroundColor: 'var(--card)', border: '1px solid var(--border)', borderRadius: '8px' }}
                labelStyle={{ color: 'var(--muted-foreground)' }}
              />
              <Area type="monotone" dataKey="tokens_in" stackId="1" stroke="var(--chart-1)" fill="url(#tokenGradient)" />
              <Area type="monotone" dataKey="tokens_out" stackId="1" stroke="var(--chart-4)" fill="var(--chart-4)" fillOpacity={0.2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Per-subagent bar chart */}
      {data.per_subagent.length > 0 && (
        <div className="bg-card border border-border rounded-xl p-6">
          <h2 className="text-lg font-semibold text-foreground mb-4">{t('usagePerSubagent')}</h2>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={data.per_subagent}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="name" stroke="var(--muted-foreground)" fontSize={11} />
              <YAxis stroke="var(--muted-foreground)" fontSize={12} />
              <Tooltip
                contentStyle={{ backgroundColor: 'var(--card)', border: '1px solid var(--border)', borderRadius: '8px' }}
                labelStyle={{ color: 'var(--muted-foreground)' }}
              />
              <Bar dataKey="cost" fill="var(--chart-1)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Per-user table */}
      {data.per_user.length > 0 && (
        <div className="bg-card border border-border rounded-xl p-6">
          <h2 className="text-lg font-semibold text-foreground mb-4">{t('usagePerUser')}</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-muted-foreground border-b border-border">
                <th className="text-left py-2 px-3 font-medium">{t('sessionUser')}</th>
                <th className="text-right py-2 px-3 font-medium">{t('totalConversations')}</th>
                <th className="text-right py-2 px-3 font-medium">{t('totalCost')}</th>
              </tr>
            </thead>
            <tbody>
              {data.per_user.map((u) => (
                <tr key={u.user_hash} className="border-b border-border/50">
                  <td className="py-2 px-3 text-foreground font-mono text-xs">{u.user_hash}</td>
                  <td className="py-2 px-3 text-right text-foreground">{u.sessions}</td>
                  <td className="py-2 px-3 text-right text-foreground">${u.cost.toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
