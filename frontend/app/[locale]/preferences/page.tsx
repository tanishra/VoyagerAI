'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Save, CheckCircle, AlertCircle, Loader2, FileText, Sparkles, ArrowLeft } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { getSession } from '@/lib/auth';
import { friendlyHttpError } from '@/lib/errors';
import { withAuthParams } from '@/lib/api-headers';
import { useLocale } from '@/lib/useLocale';
import Link from 'next/link';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function PreferencesPage() {
  const t = useTranslations('preferences');
  const locale = useLocale();
  const [userInstructions, setUserInstructions] = useState('');
  const [learnedPreferences, setLearnedPreferences] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  async function fetchPreferences() {
    setLoading(true);
    setMessage(null);
    try {
      const res = await fetch(withAuthParams(`${API_BASE}/preferences`), {
        credentials: 'include',
      });
      if (res.status === 401) {
        window.location.href = '/login';
        return;
      }
      const data = await res.json();
      setUserInstructions(data.user_instructions || '');
      setLearnedPreferences(data.learned_preferences || {});
    } catch {
      setMessage({ type: 'error', text: t('loadError') });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    getSession().then(async (user) => {
      if (cancelled) return;
      if (!user) {
        await new Promise((r) => setTimeout(r, 1500));
        if (cancelled) return;
        user = await getSession();
      }
      if (!user) {
        window.location.href = '/login';
        return;
      }
      const timer = setTimeout(() => {
        fetchPreferences();
      }, 0);
      return () => clearTimeout(timer);
    });
    return () => { cancelled = true; };
  }, []);

  async function handleSave() {
    setSaving(true);
    setMessage(null);
    try {
      const res = await fetch(withAuthParams(`${API_BASE}/preferences`), {
        method: 'PUT',
        body: JSON.stringify({ user_instructions: userInstructions }),
        credentials: 'include',
      });
      if (res.status === 401) {
        window.location.href = '/login';
        return;
      }
      if (res.ok) {
        setMessage({ type: 'success', text: t('saved') });
      } else {
        const errText = await res.text().catch(() => '');
        setMessage({
          type: 'error',
          text: friendlyHttpError(res.status, errText, { server: t('saveError'), request: t('saveFailed') }),
        });
      }
    } catch {
      setMessage({ type: 'error', text: t('saveError') });
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="min-h-screen bg-background flex flex-col items-center pt-12 px-4">
      <div className="w-full max-w-5xl">
        {/* Back to chat link */}
        <Link
          href={`/${locale}/chat`}
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors mb-6"
        >
          <ArrowLeft className="w-4 h-4" />
          {t('title')}
        </Link>

        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="mb-6"
        >
          <h1 className="text-2xl font-bold text-foreground mb-1">
            {t('title')}
          </h1>
          <p className="text-sm text-muted-foreground">
            {t('subtitle')}
          </p>
        </motion.div>

        {message && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className={`mb-4 p-3 rounded-lg border text-sm flex items-center gap-3 ${
              message.type === 'success'
                ? 'bg-accent/50 border-accent text-accent-foreground'
                : 'bg-destructive/10 border-destructive/20 text-destructive'
            }`}
          >
            {message.type === 'success' ? (
              <CheckCircle className="w-5 h-5 shrink-0" />
            ) : (
              <AlertCircle className="w-5 h-5 shrink-0" />
            )}
            <span>{message.text}</span>
          </motion.div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 text-primary animate-spin" />
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-[1fr_1px_1fr] gap-0">
            {/* Left card — User Instructions */}
            <motion.div
              initial={{ opacity: 0, filter: 'blur(4px)', y: 12 }}
              animate={{ opacity: 1, filter: 'blur(0)', y: 0 }}
              transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
              className="rounded-xl border border-border bg-card shadow-sm overflow-hidden md:rounded-r-none md:border-r-0"
            >
              <div className="p-4 border-b border-border">
                <label className="text-sm font-medium text-foreground flex items-center gap-2">
                  <FileText className="w-4 h-4 text-muted-foreground" />
                  {t('instructionsLabel')}
                </label>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {t('instructionsHint')}
                </p>
              </div>
              <textarea
                id="preferences"
                value={userInstructions}
                onChange={(e) => setUserInstructions(e.target.value)}
                className="w-full min-h-[300px] p-4 bg-transparent text-sm text-foreground/90 font-sans outline-none resize-y border-0 focus:ring-0 placeholder:text-muted-foreground/40"
                placeholder={t('instructionsPlaceholder')}
                spellCheck={true}
              />
              <div className="p-4 border-t border-border flex items-center justify-between">
                <span className={`text-xs ${userInstructions.length > 5000 ? 'text-destructive' : 'text-muted-foreground'}`}>{t('characters', { count: userInstructions.length, max: 5000 })}</span>
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="inline-flex items-center gap-2 px-5 py-2 text-sm font-medium rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                >
                  {saving ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Save className="w-4 h-4" />
                  )}
                  {saving ? t('saving') : t('save')}
                </button>
              </div>
            </motion.div>

            {/* Cinnabar hairline gutter (desktop only) */}
            <div className="hidden md:block w-px bg-primary/40" />

            {/* Right card — Learned by Agent */}
            <motion.div
              initial={{ opacity: 0, filter: 'blur(4px)', y: 12 }}
              animate={{ opacity: 1, filter: 'blur(0)', y: 0 }}
              transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1], delay: 0.15 }}
              className="rounded-xl border border-border bg-card shadow-sm overflow-hidden md:rounded-l-none md:border-l-0"
            >
              <div className="p-4 border-b border-border">
                <label className="text-sm font-medium text-foreground flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-muted-foreground" />
                  {t('learnedLabel')}
                </label>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {t('learnedHint')}
                </p>
              </div>
              <div className="p-4 min-h-[300px] flex flex-col gap-2">
                {Object.keys(learnedPreferences).length > 0 ? (
                  Object.entries(learnedPreferences).map(([key, value], i) => (
                    <motion.div
                      key={key}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.3, delay: 0.3 + i * 0.05 }}
                      className="inline-flex items-center gap-2 bg-accent/50 rounded-full px-3 py-1.5 text-sm w-fit"
                    >
                      <span className="text-muted-foreground font-mono text-xs uppercase tracking-wide">{key.replace(/_/g, ' ')}</span>
                      <span className="text-accent-foreground font-medium">{value}</span>
                    </motion.div>
                  ))
                ) : (
                  <p className="text-sm text-muted-foreground italic mt-8 text-center">
                    {t('learnedEmpty')}
                  </p>
                )}
              </div>
            </motion.div>
          </div>
        )}
      </div>
    </main>
  );
}
