'use client';

import { useTranslations } from 'next-intl';
import type { DayPlan, TimeSlot } from '@/lib/types';
import { useLocale } from '@/lib/useLocale';
import { formatCurrency } from '@/lib/format';
import { useCurrency } from '@/lib/useCurrency';
import { asCurrency } from '@/lib/currency';

interface TimelineViewProps {
  days: DayPlan[];
  destination: string;
  // The itinerary's currency — wins over the app preference when provided.
  currency?: string;
  onDayClick: (day: DayPlan) => void;
}

const SLOT_KEYS = ['morning', 'afternoon', 'evening'] as const;

function hasSlot(slot: TimeSlot | undefined): slot is TimeSlot {
  return !!slot && !!slot.activity;
}

export default function TimelineView({ days, currency: itineraryCurrency, onDayClick }: TimelineViewProps) {
  const t = useTranslations('itinerary');
  const locale = useLocale();
  const [preferredCurrency] = useCurrency();
  const currency = asCurrency(itineraryCurrency) ?? preferredCurrency;

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <div className="px-3 py-2 border-b border-border bg-muted/40 flex items-center justify-between">
        <span className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground">
          {t('dayByDay')}
        </span>
        <button
          onClick={() => days[0] && onDayClick(days[0])}
          className="text-[11px] text-primary hover:underline cursor-pointer"
        >
          {t('viewFull')}
        </button>
      </div>
      <div>
        {days.map((day) => {
          const route = SLOT_KEYS
            .map((k) => day[k])
            .filter(hasSlot)
            .map((s) => s.activity)
            .join(' → ');
          return (
            <button
              key={day.day}
              onClick={() => onDayClick(day)}
              aria-label={t('dayN', { n: day.day })}
              className="w-full text-left py-2 px-3 border-b border-border last:border-b-0 hover:bg-muted/50 transition-colors cursor-pointer"
            >
              <p className="text-sm font-medium text-foreground">
                {t('dayN', { n: day.day })} — {day.theme ?? t('dayN', { n: day.day })}
                {day.daily_cost_usd != null && (
                  <span className="float-right text-xs text-muted-foreground font-mono tabular-nums font-normal">
                    {formatCurrency(day.daily_cost_usd, locale, undefined, currency)}
                  </span>
                )}
              </p>
              {route && (
                <p className="text-[11px] text-muted-foreground mt-0.5 truncate">
                  {route}
                </p>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
