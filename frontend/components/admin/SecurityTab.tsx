'use client';

import { useState, useEffect, useCallback } from 'react';
import { Loader2, AlertCircle, Shield, ShieldAlert, Clock, UserX } from 'lucide-react';
import { useTranslations } from 'next-intl';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface SecurityFlag {
  flag_id: string;
  user_hash: string;
  category: string;
  confidence: string;
  source: string;
  thread_id: string;
  reasoning_snippet: string;
  created_at: number;
}

interface Cooldown {
  user_hash: string;
  cooldown_until: number;
}

export function SecurityTab() {
  const t = useTranslations('admin');
  const [flags, setFlags] = useState<SecurityFlag[]>([]);
  const [cooldowns, setCooldowns] = useState<Cooldown[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [flagsRes, cooldownsRes] = await Promise.all([
        fetch(`${API_BASE}/admin/security/flags?period=week`, { credentials: 'include' }),
        fetch(`${API_BASE}/admin/security/cooldowns`, { credentials: 'include' }),
      ]);
      if (flagsRes.status === 401) window.location.href = '/login';
      if (!flagsRes.ok) throw new Error('Failed to fetch flags');
      const flagsData = await flagsRes.json();
      setFlags(flagsData.flags || []);

      if (cooldownsRes.ok) {
        const cooldownsData = await cooldownsRes.json();
        setCooldowns(cooldownsData.cooldowns || []);
      }
    } catch {
      setError(t('loadError'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  async function removeCooldown(userHash: string) {
    try {
      await fetch(`${API_BASE}/admin/security/cooldowns/${userHash}`, {
        method: 'DELETE',
        credentials: 'include',
      });
      setCooldowns((prev) => prev.filter((c) => c.user_hash !== userHash));
    } catch {
      // Silently fail
    }
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

  return (
    <div className="space-y-6">
      {/* Summary */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-4">
          <div className="flex items-center gap-2 text-neutral-400 mb-2">
            <ShieldAlert className="w-5 h-5" />
            <span className="text-sm">{t('securityFlags')}</span>
          </div>
          <p className="text-lg font-semibold">{flags.length}</p>
        </div>
        <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-4">
          <div className="flex items-center gap-2 text-neutral-400 mb-2">
            <Clock className="w-5 h-5" />
            <span className="text-sm">{t('activeCooldowns')}</span>
          </div>
          <p className="text-lg font-semibold">{cooldowns.length}</p>
        </div>
      </div>

      {/* Security flags */}
      <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-6">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Shield className="w-5 h-5 text-neutral-400" />
          {t('securityFlags')}
        </h2>
        {flags.length === 0 ? (
          <p className="text-neutral-500 text-sm">{t('noFlags')}</p>
        ) : (
          <div className="space-y-3">
            {flags.map((flag) => (
              <div key={flag.flag_id} className="border border-neutral-800 rounded-lg p-3">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className={`inline-block px-2 py-0.5 rounded text-xs border ${
                      flag.confidence === 'high'
                        ? 'bg-red-950/50 text-red-300 border-red-800'
                        : 'bg-yellow-950/50 text-yellow-300 border-yellow-800'
                    }`}>
                      {flag.confidence}
                    </span>
                    <span className="text-xs text-neutral-400 font-mono">{flag.category}</span>
                  </div>
                  <span className="text-xs text-neutral-500">
                    {new Date(flag.created_at * 1000).toLocaleString()}
                  </span>
                </div>
                <p className="text-xs text-neutral-300">{flag.reasoning_snippet}</p>
                <p className="text-xs text-neutral-600 mt-1 font-mono">
                  user: {flag.user_hash} · thread: {flag.thread_id}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Active cooldowns */}
      <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-6">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <UserX className="w-5 h-5 text-neutral-400" />
          {t('activeCooldowns')}
        </h2>
        {cooldowns.length === 0 ? (
          <p className="text-neutral-500 text-sm">{t('noCooldowns')}</p>
        ) : (
          <div className="space-y-2">
            {cooldowns.map((cd) => (
              <div key={cd.user_hash} className="flex items-center justify-between border border-neutral-800 rounded-lg p-3">
                <div>
                  <span className="text-sm text-neutral-300 font-mono">{cd.user_hash}</span>
                  <p className="text-xs text-neutral-500 mt-0.5">
                    Until {new Date(cd.cooldown_until * 1000).toLocaleString()}
                  </p>
                </div>
                <button
                  onClick={() => removeCooldown(cd.user_hash)}
                  className="px-3 py-1 bg-neutral-800 hover:bg-red-900 text-neutral-300 hover:text-red-300 rounded-lg text-xs transition-colors"
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
