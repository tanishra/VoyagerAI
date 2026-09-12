'use client';

import { useState, useRef, useEffect } from 'react';
import { Check } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useLocale } from '@/lib/useLocale';
import { useCurrency } from '@/lib/useCurrency';
import { SUPPORTED_CURRENCIES, CURRENCY_SYMBOLS, CURRENCY_NAMES, type Currency } from '@/lib/currency';

export default function CurrencySwitcher() {
  const [open, setOpen] = useState(false);
  const locale = useLocale();
  const [currency, setCurrency] = useCurrency();
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
        aria-label="Change currency"
      >
        <span className="text-sm font-medium text-muted-foreground">{CURRENCY_SYMBOLS[currency]}</span>
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
            {SUPPORTED_CURRENCIES.map((c: Currency) => (
              <button
                key={c}
                onClick={() => {
                  setCurrency(c);
                  setOpen(false);
                }}
                className={`w-full flex items-center justify-between px-3 py-2 text-sm transition-colors cursor-pointer ${
                  c === currency
                    ? 'bg-primary/10 text-primary font-medium'
                    : 'text-foreground hover:bg-muted'
                }`}
              >
                <span className="flex items-center gap-2">
                  <span className="font-medium">{CURRENCY_SYMBOLS[c]}</span>
                  {CURRENCY_NAMES[c]}
                </span>
                {c === currency && <Check className="w-3.5 h-3.5" />}
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
