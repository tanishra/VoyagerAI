'use client';

import { useTranslations } from 'next-intl';
import { useLocale } from '@/lib/useLocale';
import { formatCurrency } from '@/lib/format';
import type { CostBreakdown } from '@/lib/types';
import type { Currency } from '@/lib/currency';

interface BudgetDonutProps {
  breakdown: CostBreakdown | null;
  currency?: Currency;
}

const SEGMENT_COLORS = [
  'var(--color-chart-1)',
  'var(--color-chart-2)',
  'var(--color-chart-3)',
  'var(--color-chart-4, var(--color-muted-foreground))',
];

const SEGMENT_KEYS = ['accommodation', 'food', 'activities', 'transport'] as const;

export default function BudgetDonut({ breakdown, currency }: BudgetDonutProps) {
  const t = useTranslations('itinerary');
  const locale = useLocale();

  if (!breakdown || breakdown.total === 0) {
    return (
      <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
        {t('na')}
      </div>
    );
  }

  const segments = SEGMENT_KEYS.map((key, i) => ({
    key,
    label: t(key),
    value: breakdown[key] ?? 0,
    color: SEGMENT_COLORS[i],
  })).filter((s) => s.value > 0);

  const total = breakdown.total;
  const radius = 60;
  const circumference = 2 * Math.PI * radius;
  const segmentData = segments.reduce(
    (acc, seg) => {
      const fraction = seg.value / total;
      const dash = fraction * circumference;
      const result = { seg, dash, offset: acc.currentOffset };
      acc.items.push(result);
      acc.currentOffset += dash;
      return acc;
    },
    { items: [] as { seg: (typeof segments)[number]; dash: number; offset: number }[], currentOffset: 0 },
  ).items;

  return (
    <div className="flex flex-col items-center gap-4">
      <div className="relative">
        <svg width="160" height="160" viewBox="0 0 160 160" className="-rotate-90">
          <circle
            cx="80"
            cy="80"
            r={radius}
            fill="none"
            stroke="var(--color-muted)"
            strokeWidth="16"
          />
          {segmentData.map(({ seg, dash, offset }) => (
            <circle
              key={seg.key}
              cx="80"
              cy="80"
              r={radius}
              fill="none"
              stroke={seg.color}
              strokeWidth="16"
              strokeDasharray={`${dash} ${circumference - dash}`}
              strokeDashoffset={-offset}
              style={{ transition: 'stroke-dasharray 0.6s ease' }}
            />
          ))}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-xs text-muted-foreground">{t('total')}</span>
          <span className="text-lg font-bold text-foreground tabular-nums">
            {formatCurrency(total, locale, undefined, currency)}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 w-full">
        {segments.map((seg) => (
          <div key={seg.key} className="flex items-center justify-between text-xs">
            <span className="flex items-center gap-1.5 text-muted-foreground">
              <span
                className="inline-block w-2.5 h-2.5 rounded-full"
                style={{ backgroundColor: seg.color }}
              />
              {seg.label}
            </span>
            <span className="text-foreground/80 tabular-nums">
              {formatCurrency(seg.value, locale, undefined, currency)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
