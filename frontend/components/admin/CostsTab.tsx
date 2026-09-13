'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { DollarSign, TrendingUp, MessageSquare, Download, Loader2, AlertCircle, Activity, AlertTriangle } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { CostChart } from '@/components/admin/CostChart';
import { SubagentCostBreakdown } from '@/components/admin/SubagentCostBreakdown';
import { TopUsersTable } from '@/components/admin/TopUsersTable';
import { TokenEfficiencyTable } from '@/components/admin/TokenEfficiencyTable';
import FeedbackSummary from '@/components/admin/FeedbackSummary';
import { getFeedbackAggregate, type FeedbackAggregate } from '@/lib/feedback-api';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface CostStats {
  total_cost: number;
  total_conversations: number;
  avg_cost_per_conversation: number;
  total_input_tokens: number;
  total_output_tokens: number;
  per_day: { date: string; cost: number }[];
  per_subagent: { name: string; cost: number; input_tokens: number; output_tokens: number }[];
  top_users: { user_id: string; cost: number }[];
  poor_efficiency_sessions: { thread_id: string; user_id: string; efficiency_ratio: number; cost: number }[];
}

interface LiveCostData {
  hours: number;
  total_spend: number;
  per_hour: { hour: string; cost: number; requests: number; tokens_in: number; tokens_out: number }[];
  alert: {
    level: 'ok' | 'warning' | 'critical';
    daily_spend: number;
    daily_cap: number;
    percentage: number;
    message: string;
  };
}

export function CostsTab() {
  const t = useTranslations('admin');
  const [stats, setStats] = useState<CostStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [period, setPeriod] = useState<'day' | 'week' | 'month' | 'live'>('week');
  const [feedbackStats, setFeedbackStats] = useState<FeedbackAggregate | null>(null);
  const [liveData, setLiveData] = useState<LiveCostData | null>(null);

  const fetchStats = useCallback(async (p: 'day' | 'week' | 'month' | 'live') => {
    setLoading(true);
    setError(null);
    try {
      if (p === 'live') {
        const res = await fetch(`${API_BASE}/admin/costs/live?hours=24`, {
          credentials: 'include',
        });
        if (res.status === 401) {
          window.location.href = '/login';
        }
        if (!res.ok) throw new Error('Failed to fetch');
        const data = await res.json();
        setLiveData(data);
      } else {
        const res = await fetch(`${API_BASE}/admin/costs?period=${p}`, {
          credentials: 'include',
        });
        if (res.status === 401) {
          window.location.href = '/login';
        }
        if (!res.ok) throw new Error('Failed to fetch');
        const data = await res.json();
        setStats(data);
      }
    } catch {
      setError(t('loadError'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  const fetchFeedback = useCallback(async () => {
    try {
      const data = await getFeedbackAggregate();
      setFeedbackStats(data);
    } catch {
      // Silently fail
    }
  }, []);

  useEffect(() => {
    fetchStats(period);
    fetchFeedback();
  }, [period, fetchStats, fetchFeedback]);

  function handleExport() {
    window.open(`${API_BASE}/admin/costs/export`, '_blank');
  }

  return (
    <div className="space-y-6">
      {/* Period selector + Export */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex gap-2">
          {(['day', 'week', 'month', 'live'] as const).map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-sm transition-colors ${
                period === p
                  ? 'bg-blue-600 text-white'
                  : 'bg-neutral-800 text-neutral-400 hover:text-white'
              }`}
            >
              {p === 'live' ? (
                <>
                  <Activity className="w-3.5 h-3.5" />
                  Live 24h
                </>
              ) : (
                t(`period${p.charAt(0).toUpperCase() + p.slice(1)}`)
              )}
            </button>
          ))}
        </div>
        <button
          onClick={handleExport}
          className="flex items-center gap-2 px-4 py-2 bg-neutral-800 hover:bg-neutral-700 rounded-lg text-sm transition-colors"
        >
          <Download className="w-4 h-4" />
          {t('exportCsv')}
        </button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 animate-spin text-neutral-500" />
        </div>
      ) : error ? (
        <div className="text-center py-20">
          <AlertCircle className="w-8 h-8 text-red-400 mx-auto mb-2" />
          <p className="text-neutral-400">{error}</p>
        </div>
      ) : period === 'live' && liveData ? (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="space-y-6"
        >
          {liveData.alert && (
            <div
              className={`rounded-xl p-4 border flex items-center gap-3 ${
                liveData.alert.level === 'critical'
                  ? 'bg-red-950/50 border-red-800 text-red-200'
                  : liveData.alert.level === 'warning'
                  ? 'bg-yellow-950/50 border-yellow-800 text-yellow-200'
                  : 'bg-green-950/50 border-green-800 text-green-200'
              }`}
            >
              <AlertTriangle className="w-5 h-5 flex-shrink-0" />
              <div>
                <p className="font-semibold text-sm">
                  {liveData.alert.level === 'critical' ? 'Critical' : liveData.alert.level === 'warning' ? 'Warning' : 'All Good'}
                  {' — '}
                  {liveData.alert.percentage.toFixed(1)}% of daily cap
                </p>
                <p className="text-xs opacity-80">{liveData.alert.message}</p>
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <SummaryCard icon={<DollarSign className="w-5 h-5" />} label="24h Spend" value={`$${liveData.total_spend.toFixed(4)}`} />
            <SummaryCard icon={<TrendingUp className="w-5 h-5" />} label="Daily Cap" value={`$${liveData.alert?.daily_cap.toFixed(2) || '—'}`} />
            <SummaryCard icon={<Activity className="w-5 h-5" />} label="Cap Used" value={`${liveData.alert?.percentage.toFixed(1) || 0}%`} />
            <SummaryCard icon={<MessageSquare className="w-5 h-5" />} label="Requests (24h)" value={liveData.per_hour.reduce((sum, h) => sum + h.requests, 0).toString()} />
          </div>

          <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-6">
            <h2 className="text-lg font-semibold mb-4">Hourly Cost Breakdown (Last 24h)</h2>
            {liveData.per_hour.length > 0 ? (
              <div className="space-y-2">
                {liveData.per_hour.map((hour) => (
                  <div key={hour.hour} className="flex items-center gap-3">
                    <span className="text-xs text-neutral-400 w-20 font-mono">{hour.hour.slice(11)}</span>
                    <div className="flex-1 bg-neutral-800 rounded-full h-6 overflow-hidden">
                      <div
                        className="bg-blue-600 h-full rounded-full flex items-center justify-end pr-2"
                        style={{ width: `${Math.min((hour.cost / Math.max(...liveData.per_hour.map(h => h.cost), 0.01)) * 100, 100)}%` }}
                      >
                        {hour.cost > 0.001 && <span className="text-xs text-white font-medium">${hour.cost.toFixed(3)}</span>}
                      </div>
                    </div>
                    <span className="text-xs text-neutral-500 w-16 text-right">{hour.requests} req</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-neutral-500 text-sm">No cost data in the last 24 hours.</p>
            )}
          </div>
        </motion.div>
      ) : stats ? (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <SummaryCard icon={<DollarSign className="w-5 h-5" />} label={t('totalCost')} value={`$${stats.total_cost.toFixed(4)}`} />
            <SummaryCard icon={<TrendingUp className="w-5 h-5" />} label={t('avgCostPerConversation')} value={`$${stats.avg_cost_per_conversation.toFixed(4)}`} />
            <SummaryCard icon={<MessageSquare className="w-5 h-5" />} label={t('totalConversations')} value={stats.total_conversations.toString()} />
            <SummaryCard icon={<DollarSign className="w-5 h-5" />} label={t('tokensUsed')} value={`${(stats.total_input_tokens / 1000).toFixed(1)}k in · ${(stats.total_output_tokens / 1000).toFixed(1)}k out`} />
          </div>
          <CostChart data={stats.per_day} />
          <SubagentCostBreakdown data={stats.per_subagent} />
          <TopUsersTable data={stats.top_users} />
          <TokenEfficiencyTable data={stats.poor_efficiency_sessions} />
          <FeedbackSummary data={feedbackStats} />
        </motion.div>
      ) : null}
    </div>
  );
}

function SummaryCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-4">
      <div className="flex items-center gap-2 text-neutral-400 mb-2">
        {icon}
        <span className="text-sm">{label}</span>
      </div>
      <p className="text-lg font-semibold">{value}</p>
    </div>
  );
}
