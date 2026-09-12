'use client';

import { useTranslations } from 'next-intl';
import { useLocale } from '@/lib/useLocale';
import { formatCurrency } from '@/lib/format';
import { computeAverageDailyCost } from '@/lib/budget-utils';
import type { DayPlan } from '@/lib/types';
import type { Currency } from '@/lib/currency';

interface DailyCostChartProps {
  days: DayPlan[];
  currency?: Currency;
  onBarClick?: (day: DayPlan) => void;
}

export default function DailyCostChart({ days, currency, onBarClick }: DailyCostChartProps) {
  const t = useTranslations('itinerary');
  const locale = useLocale();

  if (!days || days.length === 0) return null;

  const avgCost = computeAverageDailyCost(days);
  const maxCost = Math.max(...days.map((d) => d.daily_cost_usd ?? 0), avgCost, 1);
  const barHeight = 24;
  const gap = 6;
  const chartWidth = 100;
  const labelWidth = 48;
  const valueWidth = 60;
  const svgWidth = labelWidth + chartWidth + valueWidth;
  const svgHeight = days.length * (barHeight + gap) + 20;

  return (
    <div className="w-full">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-muted-foreground">{t('dailyCost')}</span>
        <span className="text-xs text-muted-foreground">
          {t('averageCost')}: <span className="font-medium text-foreground/80 tabular-nums">{formatCurrency(Math.round(avgCost), locale, undefined, currency)}</span>
        </span>
      </div>
      <svg width="100%" viewBox={`0 0 ${svgWidth} ${svgHeight}`} preserveAspectRatio="xMidYMid meet">
        {days.map((day, i) => {
          const cost = day.daily_cost_usd ?? 0;
          const width = (cost / maxCost) * chartWidth;
          const y = i * (barHeight + gap);
          const isOverAvg = cost > avgCost;
          const barColor = isOverAvg ? 'var(--color-chart-1)' : 'var(--color-chart-2)';

          return (
            <g
              key={day.day}
              onClick={onBarClick ? () => onBarClick(day) : undefined}
              style={onBarClick ? { cursor: 'pointer' } : undefined}
            >
              <text
                x={0}
                y={y + barHeight / 2 + 4}
                className="fill-muted-foreground text-[10px]"
                style={{ fontSize: '10px' }}
              >
                {t('dayN', { n: day.day })}
              </text>
              <rect
                x={labelWidth}
                y={y}
                width={chartWidth}
                height={barHeight}
                rx="3"
                fill="var(--color-muted)"
                opacity="0.3"
              />
              <rect
                x={labelWidth}
                y={y}
                width={width}
                height={barHeight}
                rx="3"
                fill={barColor}
                style={{ transition: 'width 0.5s ease' }}
              />
              <text
                x={labelWidth + chartWidth + 6}
                y={y + barHeight / 2 + 4}
                className="fill-foreground/80 text-[10px] tabular-nums"
                style={{ fontSize: '10px' }}
              >
                {formatCurrency(cost, locale, undefined, currency)}
              </text>
            </g>
          );
        })}
        {/* Average line */}
        {(() => {
          const avgX = labelWidth + (avgCost / maxCost) * chartWidth;
          return (
            <>
              <line
                x1={avgX}
                y1={0}
                x2={avgX}
                y2={days.length * (barHeight + gap) - gap}
                stroke="var(--color-primary)"
                strokeWidth="1"
                strokeDasharray="3 3"
                opacity="0.6"
              />
              <text
                x={avgX - 2}
                y={days.length * (barHeight + gap) + 4}
                className="fill-primary text-[9px]"
                style={{ fontSize: '9px', textAnchor: 'end' }}
              >
                {t('averageCost')}
              </text>
            </>
          );
        })()}
      </svg>
    </div>
  );
}
