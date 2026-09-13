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
    // eslint-disable-next-line react-hooks/set-state-in-effect
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
      {/* Summary */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-card border border-border rounded-xl p-4">
          <div className="flex items-center gap-2 text-muted-foreground mb-2">
            <ShieldAlert className="w-5 h-5" />
            <span className="text-sm">{t('securityFlags')}</span>
          </div>
          <p className="text-lg font-semibold text-foreground">{flags.length}</p>
        </div>
        <div className="bg-card border border-border rounded-xl p-4">
          <div className="flex items-center gap-2 text-muted-foreground mb-2">
            <Clock className="w-5 h-5" />
            <span className="text-sm">{t('activeCooldowns')}</span>
          </div>
          <p className="text-lg font-semibold text-foreground">{cooldowns.length}</p>
        </div>
      </div>

      {/* Security flags */}
      <div className="bg-card border border-border rounded-xl p-6">
        <h2 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
          <Shield className="w-5 h-5 text-muted-foreground" />
          {t('securityFlags')}
        </h2>
        {flags.length === 0 ? (
          <p className="text-muted-foreground text-sm">{t('noFlags')}</p>
        ) : (
          <div className="space-y-3">
            {flags.map((flag) => (
              <div key={flag.flag_id} className="border border-border rounded-lg p-3">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className={`inline-block px-2 py-0.5 rounded text-xs border ${
                      flag.confidence === 'high'
                        ? 'bg-destructive/10 text-destructive border-destructive/30'
                        : 'bg-accent text-accent-foreground border-accent-foreground/30'
                    }`}>
                      {flag.confidence}
                    </span>
                    <span className="text-xs text-muted-foreground font-mono">{flag.category}</span>
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {new Date(flag.created_at * 1000).toLocaleString()}
                  </span>
                </div>
                <p className="text-xs text-foreground">{flag.reasoning_snippet}</p>
                <p className="text-xs text-muted-foreground/60 mt-1 font-mono">
                  user: {flag.user_hash} · thread: {flag.thread_id}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Active cooldowns */}
      <div className="bg-card border border-border rounded-xl p-6">
        <h2 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
          <UserX className="w-5 h-5 text-muted-foreground" />
          {t('activeCooldowns')}
        </h2>
        {cooldowns.length === 0 ? (
          <p className="text-muted-foreground text-sm">{t('noCooldowns')}</p>
        ) : (
          <div className="space-y-2">
            {cooldowns.map((cd) => (
              <div key={cd.user_hash} className="flex items-center justify-between border border-border rounded-lg p-3">
                <div>
                  <span className="text-sm text-foreground font-mono">{cd.user_hash}</span>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Until {new Date(cd.cooldown_until * 1000).toLocaleString()}
                  </p>
                </div>
                <button
                  onClick={() => removeCooldown(cd.user_hash)}
                  className="px-3 py-1 bg-muted hover:bg-destructive/20 text-foreground hover:text-destructive rounded-lg text-xs transition-colors"
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
