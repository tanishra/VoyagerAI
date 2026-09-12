'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { MapPin, Clock, DollarSign, ChevronRight, Bus, Train, Footprints, Car, Navigation } from 'lucide-react';
import { useTranslations } from 'next-intl';
import type { DayPlan } from '@/lib/types';
import { useLocale } from '@/lib/useLocale';
import { formatCurrency } from '@/lib/format';
import { useCurrency } from '@/lib/useCurrency';

interface TimelineViewProps {
  days: DayPlan[];
  destination: string;
  onDayClick: (day: DayPlan) => void;
  activeDay?: number | null;
  onDayExpand?: (day: number | null) => void;
}

const SLOTS = [
  { key: 'morning' as const, labelKey: 'morning' as const, colorClass: 'text-chart-1', bgClass: 'bg-chart-1' },
  { key: 'afternoon' as const, labelKey: 'afternoon' as const, colorClass: 'text-chart-2', bgClass: 'bg-chart-2' },
  { key: 'evening' as const, labelKey: 'evening' as const, colorClass: 'text-chart-3', bgClass: 'bg-chart-3' },
];

function getTransportIcon(transport: string) {
  const t = transport.toLowerCase();
  if (t.includes('walk')) return Footprints;
  if (t.includes('train')) return Train;
  if (t.includes('bus')) return Bus;
  if (t.includes('car') || t.includes('taxi')) return Car;
  return Navigation;
}

export default function TimelineView({ days, destination, onDayClick, activeDay, onDayExpand }: TimelineViewProps) {
  const t = useTranslations('itinerary');
  const locale = useLocale();
  const [currency] = useCurrency();
  const [internalExpandedDay, setInternalExpandedDay] = useState<number | null>(null);
  const isControlled = activeDay !== undefined;
  const expandedDay = isControlled ? activeDay : internalExpandedDay;

  const toggleDay = (dayNumber: number) => {
    const newExpanded = expandedDay === dayNumber ? null : dayNumber;
    if (onDayExpand) {
      onDayExpand(newExpanded);
    }
    if (!isControlled) {
      setInternalExpandedDay(newExpanded);
    }
  };

  return (
    <div className="relative">
      {/* Vertical timeline rail */}
      <div className="absolute left-3 top-2 bottom-2 w-px bg-border" />

      <div className="space-y-1">
        {days.map((day) => {
          const isExpanded = expandedDay === day.day;
          return (
            <div key={day.day} className="relative pl-8">
              {/* Day marker */}
              <div
                className={`absolute left-0 top-1.5 w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-mono font-bold transition-colors ${
                  isExpanded
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-card border border-border text-muted-foreground'
                }`}
              >
                {day.day}
              </div>

              {/* Day bar (collapsed) */}
              <button
                onClick={() => toggleDay(day.day)}
                aria-expanded={isExpanded}
                aria-label={`${t('dayN', { n: day.day })} — ${day.theme ?? ''}`}
                className={`w-full text-left p-2 rounded-lg transition-colors cursor-pointer ${
                  isExpanded ? 'bg-muted/60' : 'hover:bg-muted/50'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium text-foreground text-sm">
                    {t('dayN', { n: day.day })} — {day.theme ?? t('dayN', { n: day.day })}
                  </span>
                  <div className="flex items-center gap-2">
                    {/* Color dots */}
                    <div className="flex items-center gap-1">
                      {SLOTS.map(({ key, bgClass }) => (
                        <span
                          key={key}
                          className={`w-2 h-2 rounded-full ${bgClass}`}
                          aria-label={t(key)}
                        />
                      ))}
                    </div>
                    {/* Cost badge */}
                    {day.daily_cost_usd != null && (
                      <span className="text-xs text-muted-foreground tabular-nums">
                        {formatCurrency(day.daily_cost_usd, locale, undefined, currency)}
                      </span>
                    )}
                  </div>
                </div>
              </button>

              {/* Expanded day (accordion) */}
              <AnimatePresence initial={false}>
                {isExpanded && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
                    className="overflow-hidden"
                    role="region"
                    aria-label={`${t('dayN', { n: day.day })} details`}
                  >
                    <div className="pt-1 pb-2 space-y-3">
                      {SLOTS.map(({ key, labelKey, colorClass }, index) => {
                        const slot = day[key];
                        if (!slot) return null;
                        const TransportIcon = index > 0 && day.transport ? getTransportIcon(day.transport) : null;
                        return (
                          <div key={key}>
                            {/* Transport indicator between blocks */}
                            {TransportIcon && (
                              <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground py-1">
                                <TransportIcon className="w-3 h-3" />
                                <span>{day.transport}</span>
                              </div>
                            )}
                            <div className="space-y-0.5">
                              <p className={`text-[10px] font-medium uppercase tracking-widest ${colorClass}`}>
                                {t(labelKey)}
                              </p>
                              <p className="text-sm font-medium text-foreground">{slot.activity}</p>
                              {slot.location && (
                                <p className="text-xs text-muted-foreground flex items-center gap-1">
                                  <MapPin className="w-3 h-3 shrink-0" />
                                  {slot.location}
                                </p>
                              )}
                              <div className="flex items-center gap-3 text-xs text-muted-foreground">
                                {slot.duration && (
                                  <span className="flex items-center gap-1">
                                    <Clock className="w-3 h-3" />
                                    {slot.duration}
                                  </span>
                                )}
                                {slot.cost_usd != null && slot.cost_usd > 0 && (
                                  <span className="flex items-center gap-1">
                                    <DollarSign className="w-3 h-3" />
                                    {formatCurrency(slot.cost_usd, locale, undefined, currency)}
                                  </span>
                                )}
                              </div>
                            </div>
                          </div>
                        );
                      })}

                      {/* View Details button */}
                      <button
                        onClick={() => onDayClick(day)}
                        className="flex items-center gap-1 text-xs text-primary hover:text-primary/80 transition-colors cursor-pointer pt-1"
                      >
                        {t('viewDetails')}
                        <ChevronRight className="w-3 h-3" />
                      </button>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          );
        })}
      </div>
    </div>
  );
}
