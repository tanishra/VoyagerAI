'use client';

import { useTranslations } from 'next-intl';
import { useLocale } from '@/lib/useLocale';
import { formatCurrency } from '@/lib/format';
import type { Currency } from '@/lib/currency';

interface BudgetStatusProps {
  status: 'within' | 'over' | 'under';
  totalCost: number | null;
  budget?: number | null;
  currency?: Currency;
}

export default function BudgetStatus({ status, totalCost, budget, currency }: BudgetStatusProps) {
  const t = useTranslations('itinerary');
  const locale = useLocale();

  const config = {
    within: { color: 'text-chart-2', bg: 'bg-chart-2/10', border: 'border-chart-2/20', label: t('withinBudget') },
    over: { color: 'text-chart-1', bg: 'bg-chart-1/10', border: 'border-chart-1/20', label: t('overBudget') },
    under: { color: 'text-chart-3', bg: 'bg-chart-3/10', border: 'border-chart-3/20', label: t('underBudget') },
  };

  const cfg = config[status] ?? config.within;

  const diff = budget && totalCost != null ? Math.abs(budget - totalCost) : null;
  const isOver = status === 'over';

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${cfg.bg} ${cfg.color} ${cfg.border} border`}
    >
      <span className={`inline-block w-1.5 h-1.5 rounded-full ${cfg.color.replace('text-', 'bg-')}`} />
      {cfg.label}
      {diff != null && (
        <span className="text-muted-foreground/80 font-normal">
          ({isOver ? '+' : '-'}{formatCurrency(diff, locale, undefined, currency)})
        </span>
      )}
    </span>
  );
}
