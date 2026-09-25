'use client';

import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Bus, Home, Lightbulb, Sun, Utensils, ChevronLeft, ChevronRight } from 'lucide-react';
import { useTranslations } from 'next-intl';
import dynamic from 'next/dynamic';
import type { DayPlan } from '@/lib/types';
import { useLocale } from '@/lib/useLocale';
import { formatCurrency } from '@/lib/format';
import { asCurrency } from '@/lib/currency';
import { useCurrency } from '@/lib/useCurrency';
import ActivityCard from './ActivityCard';

const ItineraryMap = dynamic(() => import('./ItineraryMap'), { ssr: false });

interface DayDetailPanelProps {
  days: DayPlan[];
  destination: string;
  currency?: string;
  /** Day to scroll to when the panel opens. */
  initialDay?: number;
  onClose: () => void;
}

const SLOTS = [
  { key: 'morning' as const, labelKey: 'morning' as const },
  { key: 'afternoon' as const, labelKey: 'afternoon' as const },
  { key: 'evening' as const, labelKey: 'evening' as const },
];

// Trips longer than this mount each day's full content (map + cards +
// logistics) lazily as it nears the viewport — a 14-day panel otherwise
// renders every heavy section on open.
const LAZY_CONTENT_DAYS = 8;

export default function DayDetailPanel({ days, destination, currency: itineraryCurrency, initialDay, onClose }: DayDetailPanelProps) {
  const t = useTranslations('itinerary');
  const locale = useLocale();
  const [preferredCurrency] = useCurrency();
  const currency = asCurrency(itineraryCurrency) ?? preferredCurrency;
  const scrollRef = useRef<HTMLDivElement>(null);
  const pillStripRef = useRef<HTMLDivElement>(null);
  const [canScrollPills, setCanScrollPills] = useState(false);
  const [activeDay, setActiveDay] = useState(initialDay ?? days[0]?.day ?? 1);
  const isLongTrip = days.length > LAZY_CONTENT_DAYS;
  // Maps (and, on long trips, whole day sections) mount lazily — one
  // google.maps.Map per day section is too heavy to create all at once; a
  // day's content activates when its section nears the viewport (or is the
  // initially-opened day), then stays mounted.
  const [activatedDays, setActivatedDays] = useState<Set<number>>(
    () => new Set([initialDay ?? days[0]?.day ?? 1])
  );

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

  // Jump to the tapped day once the panel has mounted.
  useEffect(() => {
    const target = initialDay ?? days[0]?.day;
    if (target == null) return;
    const el = scrollRef.current?.querySelector(`[data-day="${target}"]`);
    if (typeof el?.scrollIntoView === 'function') el.scrollIntoView({ block: 'start' });
  }, [initialDay, days]);

  // Track the visible day so the pill strip stays in sync while scrolling.
  useEffect(() => {
    const root = scrollRef.current;
    if (!root || typeof IntersectionObserver === 'undefined') return;
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            const n = Number((e.target as HTMLElement).dataset.day);
            if (n) {
              setActiveDay(n);
              setActivatedDays((prev) => (prev.has(n) ? prev : new Set(prev).add(n)));
            }
          }
        }
      },
      { root, rootMargin: '-40% 0px -55% 0px' }
    );
    root.querySelectorAll('[data-day]').forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, [days]);

  // Prefetch observer — mounts a day's content ~a viewport before the user
  // reaches it, so lazy sections never flash blank while scrolling.
  useEffect(() => {
    if (!isLongTrip) return;
    const root = scrollRef.current;
    if (!root || typeof IntersectionObserver === 'undefined') return;
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (!e.isIntersecting) continue;
          const n = Number((e.target as HTMLElement).dataset.day);
          if (n) setActivatedDays((prev) => (prev.has(n) ? prev : new Set(prev).add(n)));
        }
      },
      { root, rootMargin: '80% 0px' }
    );
    root.querySelectorAll('[data-day]').forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, [days, isLongTrip]);

  // Keep the active pill visible in the horizontal strip.
  useEffect(() => {
    const el = pillStripRef.current?.querySelector(`[data-pill="${activeDay}"]`);
    if (typeof el?.scrollIntoView === 'function') {
      el.scrollIntoView({ inline: 'nearest', block: 'nearest' });
    }
  }, [activeDay]);

  // Show strip arrows only when the pills actually overflow.
  useEffect(() => {
    const el = pillStripRef.current;
    if (!el) return;
    const update = () => setCanScrollPills(el.scrollWidth > el.clientWidth + 1);
    update();
    if (typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, [days]);

  const jumpTo = (n: number) => {
    setActiveDay(n);
    setActivatedDays((prev) => (prev.has(n) ? prev : new Set(prev).add(n)));
    const el = scrollRef.current?.querySelector(`[data-day="${n}"]`);
    if (typeof el?.scrollIntoView === 'function') {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

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
        aria-label={destination}
      >
        <motion.div
          initial={{ x: '100%' }}
          animate={{ x: 0 }}
          exit={{ x: '100%' }}
          transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
          className="absolute inset-y-0 right-0 w-full md:max-w-md lg:max-w-lg bg-card border-l border-border shadow-lg flex flex-col overflow-hidden"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
            <h2 className="font-semibold text-foreground text-base">
              {destination} — {t('days', { count: days.length })}
            </h2>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors cursor-pointer"
              aria-label={t('closeDayDetails')}
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Pinned day pills */}
          <div className="flex items-center border-b border-border shrink-0 bg-card">
            {canScrollPills && (
              <button
                onClick={() => pillStripRef.current?.scrollBy({ left: -160, behavior: 'smooth' })}
                className="shrink-0 p-1.5 text-muted-foreground hover:text-foreground cursor-pointer"
                aria-label={t('prevDays')}
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
            )}
            <div
              ref={pillStripRef}
              className="flex-1 px-4 py-2 flex gap-1.5 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
            >
              {days.map((d) => (
                <button
                  key={d.day}
                  data-pill={d.day}
                  onClick={() => jumpTo(d.day)}
                  aria-label={t('dayN', { n: d.day })}
                  className={`shrink-0 px-3 py-1.5 rounded-full border text-xs font-mono transition-colors cursor-pointer ${
                    activeDay === d.day
                      ? 'bg-primary text-primary-foreground border-primary'
                      : 'border-border hover:bg-muted'
                  }`}
                >
                  {d.day}
                  <span className="hidden sm:inline text-muted-foreground"> · {d.theme?.split(' ')[0]}</span>
                </button>
              ))}
            </div>
            {canScrollPills && (
              <button
                onClick={() => pillStripRef.current?.scrollBy({ left: 160, behavior: 'smooth' })}
                className="shrink-0 p-1.5 text-muted-foreground hover:text-foreground cursor-pointer"
                aria-label={t('nextDays')}
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            )}
          </div>

          {/* Scrollable day sections */}
          <div ref={scrollRef} className="flex-1 overflow-y-auto">
            {days.map((day) => (
              <section
                key={day.day}
                data-day={day.day}
                className="px-4 pt-3 pb-2 border-b border-border last:border-b-0"
              >
                <div className="flex items-baseline justify-between mb-2">
                  <p className="text-sm font-semibold text-foreground">
                    {t('dayN', { n: day.day })}
                    {day.theme ? ` — ${day.theme}` : ''}
                    {day.date ? <span className="text-muted-foreground font-normal"> · {day.date}</span> : null}
                  </p>
                  {day.daily_cost_usd != null && (
                    <span className="text-xs text-muted-foreground font-mono tabular-nums">
                      {formatCurrency(day.daily_cost_usd, locale, undefined, currency)}
                    </span>
                  )}
                </div>

                {/* Long trips: mount a day's heavy content only once it nears
                    the viewport — the header + a sized shell keep scroll-spy
                    and jumpTo working before activation. */}
                {isLongTrip && !activatedDays.has(day.day) ? (
                  <div className="rounded-lg border border-border bg-muted/30 min-h-[420px] mb-1 shimmer" aria-hidden />
                ) : (
                <>
                {/* Per-day map — this day's markers only; mounts lazily on
                    first scroll-into-view so the panel doesn't spin up N
                    map instances at once. */}
                {activatedDays.has(day.day) ? (
                  <div className="rounded-lg overflow-hidden border border-border mb-1">
                    <ItineraryMap
                      days={[day]}
                      destination={destination}
                      currency={currency}
                      activeDay={day.day}
                    />
                  </div>
                ) : (
                  <div className="rounded-lg border border-border bg-muted/30 h-[120px] mb-1 shimmer" aria-hidden />
                )}

                {/* Activity cards */}
                <div className="py-1 space-y-2">
                  {SLOTS.map(({ key }) => {
                    const slot = day[key];
                    if (!slot?.activity) return null;
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
                </div>

                {/* Logistics */}
                <div className="grid grid-cols-2 gap-3 py-3 border-t border-border text-xs">
                  <p className="flex items-center gap-1.5 text-muted-foreground">
                    <Bus className="w-3 h-3 shrink-0" />
                    {day.transport ?? t('na')}
                    {day.walking_km != null && ` · ~${day.walking_km} km`}
                  </p>
                  <p className="flex items-center gap-1.5 text-muted-foreground">
                    <Home className="w-3 h-3 shrink-0" />
                    {day.accommodation ?? t('na')}
                  </p>
                  {day.weather && (
                    <p className="flex items-center gap-1.5 text-muted-foreground">
                      <Sun className="w-3 h-3 shrink-0" />
                      {day.weather}
                    </p>
                  )}
                  {day.morning?.food || day.afternoon?.food || day.evening?.food ? (
                    <p className="flex items-center gap-1.5 text-muted-foreground col-span-2">
                      <Utensils className="w-3 h-3 shrink-0" />
                      {day.morning?.food ?? day.afternoon?.food ?? day.evening?.food}
                    </p>
                  ) : null}
                </div>

                {/* Tips */}
                {day.tips && day.tips.length > 0 && (
                  <div className="py-3 border-t border-border space-y-1">
                    <p className="text-[10px] text-muted-foreground uppercase tracking-widest mb-1">
                      {t('tips')}
                    </p>
                    {day.tips.map((tip, i) => (
                      <p key={i} className="text-xs text-accent-foreground flex items-start gap-1.5">
                        <Lightbulb className="w-3 h-3 mt-0.5 shrink-0" />
                        {tip}
                      </p>
                    ))}
                  </div>
                )}

                {/* Day total */}
                <div className="py-3 border-t border-border flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">{t('dailyCostSummary')}</span>
                  <span className="text-sm font-semibold text-primary">
                    {day.daily_cost_usd != null ? formatCurrency(day.daily_cost_usd, locale, undefined, currency) : t('na')}
                  </span>
                </div>
                </>
                )}
              </section>
            ))}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
