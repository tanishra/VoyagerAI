'use client';

import { useState, useEffect, useCallback } from 'react';
import { Loader2, AlertCircle, Search, ChevronLeft, ChevronRight } from 'lucide-react';
import { useTranslations } from 'next-intl';
import {
  getSessions,
  type ObservabilitySession,
} from '@/lib/observability-api';

interface Props {
  onSelectSession: (threadId: string) => void;
}

const STATUS_COLORS: Record<string, string> = {
  running: 'bg-blue-950/50 text-blue-300 border-blue-800',
  completed: 'bg-green-950/50 text-green-300 border-green-800',
  error: 'bg-red-950/50 text-red-300 border-red-800',
  cancelled: 'bg-yellow-950/50 text-yellow-300 border-yellow-800',
  budget_reached: 'bg-orange-950/50 text-orange-300 border-orange-800',
};

export function SessionsTable({ onSelectSession }: Props) {
  const t = useTranslations('admin');
  const [sessions, setSessions] = useState<ObservabilitySession[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [statusFilter, setStatusFilter] = useState('');
  const [search, setSearch] = useState('');
  const pageSize = 20;

  const fetchSessions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getSessions({
        status: statusFilter || undefined,
        limit: pageSize,
        offset: page * pageSize,
      });
      let filtered = data.sessions;
      if (search) {
        filtered = filtered.filter((s) =>
          s.thread_id.toLowerCase().includes(search.toLowerCase()),
        );
      }
      setSessions(filtered);
      setTotal(data.total);
    } catch {
      setError(t('loadError'));
    } finally {
      setLoading(false);
    }
  }, [statusFilter, page, search, t]);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  function formatDate(ts: number) {
    if (!ts) return '—';
    return new Date(ts * 1000).toLocaleString();
  }

  function formatDuration(seconds: number | null) {
    if (!seconds) return '—';
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
  }

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <div className="relative flex-1 min-w-48">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-500" />
          <input
            type="text"
            placeholder={t('sessionSearch')}
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(0);
            }}
            className="w-full pl-10 pr-4 py-2 bg-neutral-900 border border-neutral-800 rounded-lg text-sm text-white placeholder-neutral-500 focus:border-blue-500 focus:outline-none"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(0);
          }}
          className="px-3 py-2 bg-neutral-900 border border-neutral-800 rounded-lg text-sm text-white focus:border-blue-500 focus:outline-none"
        >
          <option value="">{t('allStatuses')}</option>
          <option value="running">Running</option>
          <option value="completed">Completed</option>
          <option value="error">Error</option>
          <option value="cancelled">Cancelled</option>
        </select>
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin text-neutral-500" />
        </div>
      ) : error ? (
        <div className="text-center py-12">
          <AlertCircle className="w-6 h-6 text-red-400 mx-auto mb-2" />
          <p className="text-neutral-400 text-sm">{error}</p>
        </div>
      ) : sessions.length === 0 ? (
        <div className="text-center py-12 text-neutral-500 text-sm">
          {t('noSessions')}
        </div>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-neutral-400 border-b border-neutral-800">
                  <th className="text-left py-2 px-3 font-medium">{t('sessionStart')}</th>
                  <th className="text-left py-2 px-3 font-medium">{t('sessionUser')}</th>
                  <th className="text-left py-2 px-3 font-medium">{t('sessionDuration')}</th>
                  <th className="text-left py-2 px-3 font-medium">{t('sessionSubagents')}</th>
                  <th className="text-left py-2 px-3 font-medium">{t('sessionTokens')}</th>
                  <th className="text-left py-2 px-3 font-medium">{t('sessionCost')}</th>
                  <th className="text-left py-2 px-3 font-medium">{t('sessionStatus')}</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((s) => (
                  <tr
                    key={s.thread_id}
                    onClick={() => onSelectSession(s.thread_id)}
                    className="border-b border-neutral-800/50 hover:bg-neutral-900 cursor-pointer transition-colors"
                  >
                    <td className="py-2 px-3 text-neutral-300 text-xs">
                      {formatDate(s.start_time)}
                    </td>
                    <td className="py-2 px-3 text-neutral-400 font-mono text-xs">
                      {s.user_hash}
                    </td>
                    <td className="py-2 px-3 text-neutral-300">
                      {formatDuration(s.duration_seconds)}
                    </td>
                    <td className="py-2 px-3 text-neutral-300">{s.subagent_count}</td>
                    <td className="py-2 px-3 text-neutral-300 text-xs">
                      {(s.total_tokens_in / 1000).toFixed(1)}k / {(s.total_tokens_out / 1000).toFixed(1)}k
                    </td>
                    <td className="py-2 px-3 text-neutral-300">
                      ${s.total_cost_usd.toFixed(4)}
                    </td>
                    <td className="py-2 px-3">
                      <span
                        className={`inline-block px-2 py-0.5 rounded text-xs border ${
                          STATUS_COLORS[s.status] || 'bg-neutral-900 text-neutral-400 border-neutral-700'
                        }`}
                      >
                        {s.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between">
            <p className="text-xs text-neutral-500">
              {page * pageSize + 1}–{Math.min((page + 1) * pageSize, total)} of {total}
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="p-1.5 rounded-lg bg-neutral-800 hover:bg-neutral-700 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={(page + 1) * pageSize >= total}
                className="p-1.5 rounded-lg bg-neutral-800 hover:bg-neutral-700 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
