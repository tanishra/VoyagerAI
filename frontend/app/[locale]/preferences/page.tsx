'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Save, CheckCircle, AlertCircle, Loader2, FileText, ArrowLeft } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { getSession } from '@/lib/auth';
import { useLocale } from '@/lib/useLocale';
import Link from 'next/link';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function PreferencesPage() {
  const t = useTranslations('preferences');
  const locale = useLocale();
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  async function fetchPreferences() {
    setLoading(true);
    setMessage(null);
    try {
      const res = await fetch(`${API_BASE}/preferences`, {
        credentials: 'include',
      });
      if (res.status === 401) {
        window.location.href = '/login';
        return;
      }
      const text = await res.text();
      setContent(text);
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
      const res = await fetch(`${API_BASE}/preferences`, {
        method: 'PUT',
        headers: { 'Content-Type': 'text/plain' },
        body: content,
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
        setMessage({ type: 'error', text: errText || t('saveFailed') });
      }
    } catch {
      setMessage({ type: 'error', text: t('saveError') });
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="min-h-screen bg-background flex flex-col items-center pt-12 px-4">
      <div className="w-full max-w-2xl">
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
            className={`mb-4 p-3 rounded-xl border text-sm flex items-center gap-3 ${
              message.type === 'success'
                ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-600'
                : 'bg-red-500/10 border-red-500/20 text-red-600'
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
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
          >
            <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
              <div className="p-4 border-b border-border">
                <label className="text-sm font-medium text-foreground flex items-center gap-2">
                  <FileText className="w-4 h-4 text-muted-foreground" />
                  {t('fileLabel')}
                </label>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {t('fileHint')}
                </p>
              </div>
              <textarea
                id="preferences"
                value={content}
                onChange={(e) => setContent(e.target.value)}
                className="w-full min-h-[300px] p-4 bg-transparent text-sm text-foreground/90 font-mono outline-none resize-y border-0 focus:ring-0 placeholder:text-muted-foreground/40"
                placeholder={t('placeholder')}
                spellCheck={false}
              />
              <div className="p-4 border-t border-border flex items-center justify-between">
                <span className="text-xs text-muted-foreground">{t('characters', { count: content.length })}</span>
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
            </div>
          </motion.div>
        )}
      </div>
    </main>
  );
}
