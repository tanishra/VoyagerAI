'use client';

import { useState, useRef, useEffect } from 'react';
import { Globe, Check } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useLocale, setLocale, locales, type Locale } from '@/lib/useLocale';
import { localeNames, localeFlags } from '@/lib/i18n-config';

export default function LanguageSwitcher() {
  const [open, setOpen] = useState(false);
  const currentLocale = useLocale();
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-2 py-1.5 rounded-lg hover:bg-muted transition-colors cursor-pointer"
        aria-label="Change language"
      >
        <Globe className="w-4 h-4 text-muted-foreground" />
        <span className="text-sm text-muted-foreground">{localeFlags[currentLocale]}</span>
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.15 }}
            className="absolute right-0 top-full mt-2 w-44 rounded-xl border border-border bg-white shadow-lg overflow-hidden z-50"
          >
            {(locales as readonly Locale[]).map((l) => (
              <button
                key={l}
                onClick={() => {
                  setLocale(l);
                  setOpen(false);
                }}
                className={`w-full flex items-center justify-between px-3 py-2 text-sm transition-colors cursor-pointer ${
                  l === currentLocale
                    ? 'bg-primary/10 text-primary font-medium'
                    : 'text-foreground hover:bg-muted'
                }`}
              >
                <span className="flex items-center gap-2">
                  <span>{localeFlags[l]}</span>
                  {localeNames[l]}
                </span>
                {l === currentLocale && <Check className="w-3.5 h-3.5" />}
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
