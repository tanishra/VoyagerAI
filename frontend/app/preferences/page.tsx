'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Sparkles, Save, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import { getUserId } from '@/lib/user-id';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function PreferencesPage() {
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  async function fetchPreferences() {
    setLoading(true);
    setMessage(null);
    try {
      const res = await fetch(`${API_BASE}/preferences`, {
        headers: { 'X-User-Id': getUserId() },
      });
      const text = await res.text();
      setContent(text);
    } catch {
      setMessage({ type: 'error', text: 'Could not load preferences. Is the backend running?' });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchPreferences();
    }, 0);
    return () => clearTimeout(timer);
  }, []);

  async function handleSave() {
    setSaving(true);
    setMessage(null);
    try {
      const res = await fetch(`${API_BASE}/preferences`, {
        method: 'PUT',
        headers: { 'Content-Type': 'text/plain', 'X-User-Id': getUserId() },
        body: content,
      });
      if (res.ok) {
        setMessage({ type: 'success', text: 'Preferences saved!' });
      } else {
        const errText = await res.text().catch(() => '');
        setMessage({ type: 'error', text: errText || 'Failed to save preferences.' });
      }
    } catch {
      setMessage({ type: 'error', text: 'Could not save preferences. Is the backend running?' });
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="relative min-h-screen overflow-hidden pt-16">
      <div className="pointer-events-none fixed inset-0">
        <div className="absolute top-0 left-1/4 w-[600px] h-[600px] bg-sky-500/[0.07] rounded-full blur-[120px]" />
        <div className="absolute bottom-0 right-1/4 w-[500px] h-[500px] bg-blue-500/[0.05] rounded-full blur-[100px]" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[400px] bg-indigo-500/[0.03] rounded-full blur-[140px]" />
      </div>

      <div
        className="pointer-events-none fixed inset-0 opacity-[0.015]"
        style={{
          backgroundImage: `linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)`,
          backgroundSize: '60px 60px',
        }}
      />

      <div className="relative z-10 max-w-2xl mx-auto px-4 pt-8 pb-12">
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
          className="text-center mb-8"
        >
          <div className="flex items-center justify-center gap-2.5 mb-3">
            <motion.div
              animate={{ rotate: [0, 10, -10, 0] }}
              transition={{ repeat: Infinity, duration: 6, ease: 'easeInOut' }}
              className="p-2 rounded-xl bg-gradient-to-br from-sky-500/20 to-blue-500/20 border border-sky-500/15"
            >
              <Sparkles className="w-6 h-6 text-sky-400" />
            </motion.div>
            <h1 className="text-3xl md:text-4xl font-bold bg-gradient-to-r from-white via-white/90 to-white/60 bg-clip-text text-transparent">
              Your Preferences
            </h1>
          </div>
          <p className="text-sm md:text-base text-muted-foreground max-w-md mx-auto">
            The agent reads these preferences at the start of every planning session to personalize your itineraries.
          </p>
        </motion.div>

        {message && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className={`mb-6 p-4 rounded-xl border text-sm flex items-center gap-3 ${
              message.type === 'success'
                ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300'
                : 'bg-red-500/10 border-red-500/20 text-red-300'
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
            <Loader2 className="w-8 h-8 text-sky-400 animate-spin" />
          </div>
        ) : (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
          >
            <div className="rounded-xl border border-white/10 bg-black/40 backdrop-blur-xl overflow-hidden">
              <div className="p-4 border-b border-white/5">
                <label htmlFor="preferences" className="text-sm font-medium text-white/80">
                  Preferences file
                </label>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Edit the YAML content below. The format is defined by the agent.
                </p>
              </div>
              <textarea
                id="preferences"
                value={content}
                onChange={(e) => setContent(e.target.value)}
                className="w-full min-h-[300px] p-4 bg-transparent text-sm text-white/90 font-mono outline-none resize-y border-0 focus:ring-0 placeholder:text-white/20"
                placeholder="No preferences saved yet. The agent will create them on your first planning session."
                spellCheck={false}
              />
              <div className="p-4 border-t border-white/5 flex items-center justify-between">
                <span className="text-xs text-muted-foreground">
                  {content.length} characters
                </span>
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="inline-flex items-center gap-2 px-5 py-2 text-sm font-medium rounded-lg bg-sky-500/20 text-sky-300 border border-sky-500/30 hover:bg-sky-500/30 hover:text-sky-200 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                >
                  {saving ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Save className="w-4 h-4" />
                  )}
                  {saving ? 'Saving...' : 'Save Preferences'}
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </div>
    </main>
  );
}
