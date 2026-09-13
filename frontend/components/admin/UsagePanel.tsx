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
    fetchUsage();
  }, [fetchUsage]);

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

  if (!data) return null;

  return (
    <div className="space-y-6">
      {/* Summary cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-4">
          <div className="flex items-center gap-2 text-neutral-400 mb-2">
            <Coins className="w-5 h-5" />
            <span className="text-sm">{t('totalCost')}</span>
          </div>
          <p className="text-lg font-semibold">${data.totals.cost.toFixed(4)}</p>
        </div>
        <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-4">
          <div className="flex items-center gap-2 text-neutral-400 mb-2">
            <Hash className="w-5 h-5" />
            <span className="text-sm">{t('tokensUsed')}</span>
          </div>
          <p className="text-lg font-semibold">
            {(data.totals.tokens_in / 1000).toFixed(1)}k / {(data.totals.tokens_out / 1000).toFixed(1)}k
          </p>
        </div>
        <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-4">
          <div className="flex items-center gap-2 text-neutral-400 mb-2">
            <MessageSquare className="w-5 h-5" />
            <span className="text-sm">{t('totalConversations')}</span>
          </div>
          <p className="text-lg font-semibold">{data.totals.sessions}</p>
        </div>
        <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-4">
          <div className="flex items-center gap-2 text-neutral-400 mb-2">
            <span className="text-sm">{t('usagePerSubagent')}</span>
          </div>
          <p className="text-lg font-semibold">{data.per_subagent.length}</p>
        </div>
      </div>

      {/* Daily usage chart */}
      {data.per_day.length > 0 && (
        <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-4">{t('usagePerDay')}</h2>
          <ResponsiveContainer width="100%" height={250}>
            <AreaChart data={data.per_day}>
              <defs>
                <linearGradient id="tokenGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
              <XAxis dataKey="date" stroke="#737373" fontSize={12} />
              <YAxis stroke="#737373" fontSize={12} />
              <Tooltip
                contentStyle={{ backgroundColor: '#171717', border: '1px solid #404040', borderRadius: '8px' }}
                labelStyle={{ color: '#a3a3a3' }}
              />
              <Area type="monotone" dataKey="tokens_in" stackId="1" stroke="#3b82f6" fill="url(#tokenGradient)" />
              <Area type="monotone" dataKey="tokens_out" stackId="1" stroke="#8b5cf6" fill="#8b5cf6" fillOpacity={0.2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Per-subagent bar chart */}
      {data.per_subagent.length > 0 && (
        <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-4">{t('usagePerSubagent')}</h2>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={data.per_subagent}>
              <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
              <XAxis dataKey="name" stroke="#737373" fontSize={11} />
              <YAxis stroke="#737373" fontSize={12} />
              <Tooltip
                contentStyle={{ backgroundColor: '#171717', border: '1px solid #404040', borderRadius: '8px' }}
                labelStyle={{ color: '#a3a3a3' }}
              />
              <Bar dataKey="cost" fill="#3b82f6" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Per-user table */}
      {data.per_user.length > 0 && (
        <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-4">{t('usagePerUser')}</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-neutral-400 border-b border-neutral-800">
                <th className="text-left py-2 px-3 font-medium">{t('sessionUser')}</th>
                <th className="text-right py-2 px-3 font-medium">{t('totalConversations')}</th>
                <th className="text-right py-2 px-3 font-medium">{t('totalCost')}</th>
              </tr>
            </thead>
            <tbody>
              {data.per_user.map((u) => (
                <tr key={u.user_hash} className="border-b border-neutral-800/50">
                  <td className="py-2 px-3 text-neutral-300 font-mono text-xs">{u.user_hash}</td>
                  <td className="py-2 px-3 text-right text-neutral-300">{u.sessions}</td>
                  <td className="py-2 px-3 text-right text-neutral-300">${u.cost.toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
