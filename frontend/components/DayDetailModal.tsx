'use client';

import { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Bus, Home, DollarSign, Lightbulb } from 'lucide-react';
import { useTranslations } from 'next-intl';
import type { DayPlan } from '@/lib/types';
import { useLocale } from '@/lib/useLocale';
import { formatCurrency } from '@/lib/format';
import { asCurrency } from '@/lib/currency';
import { useCurrency } from '@/lib/useCurrency';
import ActivityCard from './ActivityCard';

interface DayDetailModalProps {
  day: DayPlan;
  dayNumber: number;
  destination: string;
  currency?: string;
  onClose: () => void;
}

const SLOTS = [
  { key: 'morning' as const, labelKey: 'morning' as const },
  { key: 'afternoon' as const, labelKey: 'afternoon' as const },
  { key: 'evening' as const, labelKey: 'evening' as const },
];

export default function DayDetailModal({ day, dayNumber, destination, currency: itineraryCurrency, onClose }: DayDetailModalProps) {
  const t = useTranslations('itinerary');
  const locale = useLocale();
  const [preferredCurrency] = useCurrency();
  const currency = asCurrency(itineraryCurrency) ?? preferredCurrency;
  const modalRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleEscape);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = '';
    };
  }, [onClose]);

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) onClose();
  };

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.2 }}
        className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm"
        onClick={handleBackdropClick}
        role="dialog"
        aria-modal="true"
        aria-label={t('dayN', { n: dayNumber })}
      >
        <motion.div
          ref={modalRef}
          initial={{ x: '100%' }}
          animate={{ x: 0 }}
          exit={{ x: '100%' }}
          transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
          className="absolute inset-y-0 right-0 w-full md:max-w-md lg:max-w-lg bg-card border-l border-border shadow-lg flex flex-col overflow-hidden"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
            <h2 className="font-semibold text-foreground text-base">
              {t('dayN', { n: dayNumber })}
              {day.theme ? ` — ${day.theme}` : ''}
            </h2>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors cursor-pointer"
              aria-label={t('closeDayDetails')}
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Scrollable content */}
          <div className="flex-1 overflow-y-auto">
            {/* Activity Cards */}
            <div className="p-4 space-y-3">
              {SLOTS.map(({ key }) => {
                const slot = day[key];
                if (!slot) return null;
                return (
                  <ActivityCard
                    key={key}
                    slot={slot}
                    slotKey={key}
                    destination={destination}
                    currency={currency}
                  />
                );
              })}

              {/* Hairline separator */}
              <div className="border-t border-border" />

              {/* Transport & Accommodation */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="text-[10px] text-muted-foreground uppercase tracking-widest mb-0.5">
                    {t('transport')}
                  </p>
                  <p className="text-xs text-foreground flex items-center gap-1">
                    <Bus className="w-3 h-3 text-muted-foreground" />
                    {day.transport ?? t('na')}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] text-muted-foreground uppercase tracking-widest mb-0.5">
                    {t('stay')}
                  </p>
                  <p className="text-xs text-foreground flex items-center gap-1">
                    <Home className="w-3 h-3 text-muted-foreground" />
                    {day.accommodation ?? t('na')}
                  </p>
                </div>
              </div>

              {/* Tips */}
              {day.tips && day.tips.length > 0 && (
                <div className="border-t border-border pt-3">
                  <p className="text-[10px] text-muted-foreground uppercase tracking-widest mb-1.5">
                    {t('tips')}
                  </p>
                  <ul className="space-y-1">
                    {day.tips.map((tip, i) => (
                      <li key={i} className="text-xs text-accent-foreground flex items-start gap-1.5">
                        <Lightbulb className="w-3 h-3 mt-0.5 shrink-0 text-accent-foreground" />
                        {tip}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Daily Cost Summary */}
              <div className="border-t border-border pt-3 flex items-center justify-between">
                <span className="text-xs text-muted-foreground">{t('dailyCostSummary')}</span>
                <span className="text-sm font-semibold text-primary">
                  {day.daily_cost_usd != null ? formatCurrency(day.daily_cost_usd, locale, undefined, currency) : t('na')}
                </span>
              </div>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
