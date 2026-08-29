'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { DollarSign, TrendingUp, MessageSquare, Download, Loader2, AlertCircle, ArrowLeft } from 'lucide-react';
import { useTranslations } from 'next-intl';
import Link from 'next/link';
import { CostChart } from '@/components/admin/CostChart';
import { SubagentCostBreakdown } from '@/components/admin/SubagentCostBreakdown';
import { TopUsersTable } from '@/components/admin/TopUsersTable';
import { TokenEfficiencyTable } from '@/components/admin/TokenEfficiencyTable';

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

export default function AdminCostsPage() {
  const t = useTranslations('admin');
  const [stats, setStats] = useState<CostStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [period, setPeriod] = useState<'day' | 'week' | 'month'>('week');
  const [accessDenied, setAccessDenied] = useState(false);

  const fetchStats = useCallback(async (p: 'day' | 'week' | 'month') => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/admin/costs?period=${p}`, {
        credentials: 'include',
      });
      if (res.status === 403) {
        setAccessDenied(true);
        return;
      }
      if (res.status === 401) {
        window.location.href = '/login';
        return;
      }
      if (!res.ok) throw new Error('Failed to fetch');
      const data = await res.json();
      setStats(data);
    } catch {
      setError(t('loadError'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    fetchStats(period);
  }, [period, fetchStats]);

  function handleExport() {
    window.open(`${API_BASE}/admin/costs/export`, '_blank');
  }

  if (accessDenied) {
    return (
      <div className="min-h-screen bg-neutral-950 flex items-center justify-center p-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center"
        >
          <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
          <h1 className="text-xl font-semibold text-white mb-2">{t('accessDenied')}</h1>
          <Link href="/" className="text-blue-400 hover:text-blue-300 text-sm">
            {t('backHome')}
          </Link>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-neutral-950 text-white p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
            <Link href="/" className="text-neutral-400 hover:text-white">
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <h1 className="text-2xl font-bold">{t('title')}</h1>
          </div>
          <button
            onClick={handleExport}
            className="flex items-center gap-2 px-4 py-2 bg-neutral-800 hover:bg-neutral-700 rounded-lg text-sm transition-colors"
          >
            <Download className="w-4 h-4" />
            {t('exportCsv')}
          </button>
        </div>

        {/* Period selector */}
        <div className="flex gap-2 mb-6">
          {(['day', 'week', 'month'] as const).map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-4 py-1.5 rounded-lg text-sm transition-colors ${
                period === p
                  ? 'bg-blue-600 text-white'
                  : 'bg-neutral-800 text-neutral-400 hover:text-white'
              }`}
            >
              {t(`period${p.charAt(0).toUpperCase() + p.slice(1)}`)}
            </button>
          ))}
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
        ) : stats ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="space-y-6"
          >
            {/* Summary cards */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <SummaryCard
                icon={<DollarSign className="w-5 h-5" />}
                label={t('totalCost')}
                value={`$${stats.total_cost.toFixed(4)}`}
              />
              <SummaryCard
                icon={<TrendingUp className="w-5 h-5" />}
                label={t('avgCostPerConversation')}
                value={`$${stats.avg_cost_per_conversation.toFixed(4)}`}
              />
              <SummaryCard
                icon={<MessageSquare className="w-5 h-5" />}
                label={t('totalConversations')}
                value={stats.total_conversations.toString()}
              />
              <SummaryCard
                icon={<DollarSign className="w-5 h-5" />}
                label={t('tokensUsed')}
                value={`${(stats.total_input_tokens / 1000).toFixed(1)}k in · ${(stats.total_output_tokens / 1000).toFixed(1)}k out`}
              />
            </div>

            {/* Daily cost chart */}
            <CostChart data={stats.per_day} />

            {/* Subagent breakdown */}
            <SubagentCostBreakdown data={stats.per_subagent} />

            {/* Top users */}
            <TopUsersTable data={stats.top_users} />

            {/* Poor efficiency sessions */}
            <TokenEfficiencyTable data={stats.poor_efficiency_sessions} />
          </motion.div>
        ) : null}
      </div>
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
