'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown, ChevronUp, Wallet, Scale, Sparkles, TrendingUp, TrendingDown, BadgeCheck, RotateCcw } from 'lucide-react';
import { useTranslations } from 'next-intl';
import useSWR from 'swr';
import type { ComparisonData, PlanTier } from '@/lib/types';
import { useLocale } from '@/lib/useLocale';
import { formatCurrency } from '@/lib/format';
import { useCurrency } from '@/lib/useCurrency';
import { useCountUp } from '@/lib/useCountUp';
import { fetchWikimediaImage } from '@/lib/wikimedia';

const TIER_KEYS: Record<string, string> = {
  budget: 'budget',
  balanced: 'balanced',
  premium: 'premium',
};

const TIER_CONFIG: Record<string, { icon: typeof Wallet; color: string; dot: string }> = {
  budget: { icon: Wallet, color: 'text-chart-2', dot: 'bg-chart-2' },
  balanced: { icon: Scale, color: 'text-primary', dot: 'bg-primary' },
  premium: { icon: Sparkles, color: 'text-accent-foreground', dot: 'bg-accent-foreground' },
};

const RECOMMENDED_TIER = 'balanced';

const SACRIFICE_RE = /\b(?:no\b|only|shared|basic|miss|crowded|expensive|extra cost|long|late|limited|fewer|without)\b/i;

function planTotal(plan: PlanTier): number | null {
  return plan.itinerary.estimated_total_cost_usd ?? plan.cost_breakdown?.total ?? null;
}

function PlanCard({
  plan,
  index,
  onSelect,
  onRegenerateTier,
  regeneratingTier,
}: {
  plan: PlanTier;
  index: number;
  onSelect: (tier: string) => void;
  onRegenerateTier?: (tier: string) => void;
  regeneratingTier?: string | null;
}) {
  const t = useTranslations('comparison');
  const tItin = useTranslations('itinerary');
  const locale = useLocale();
  const [currency] = useCurrency();
  const [expanded, setExpanded] = useState(false);
  const tierKey = TIER_KEYS[plan.tier] ?? 'balanced';
  const cfg = TIER_CONFIG[plan.tier] ?? TIER_CONFIG.balanced;
  const Icon = cfg.icon;
  const itinerary = plan.itinerary;
  const days = itinerary.days ?? [];
  const dayCount = days.length > 0 ? days.length : itinerary.total_days ?? 0;
  const breakdown = plan.cost_breakdown;
  // The deterministic prose-fallback parser (when the model skips <comparison>
  // JSON) only fills cost_breakdown.total — no per-category split. Render
  // only categories we actually have data for, never "NaN".
  const hasCategoryBreakdown =
    breakdown != null &&
    [breakdown.accommodation, breakdown.food, breakdown.activities, breakdown.transport].some(
      (v) => v != null
    );
  const total = planTotal(plan);
  const isRecommended = plan.tier === RECOMMENDED_TIER;
  const animatedTotal = useCountUp(total ?? 0);
  const isRegenerating = regeneratingTier === plan.tier;
  // dayCount falls back to total_days so summary-only stubs (no days array)
  // still show a per-day figure.
  const perDay = total != null && dayCount > 0 ? total / dayCount : null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.12, duration: 0.4, ease: 'easeOut' }}
      className="relative"
    >
      {isRecommended && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2 z-10">
          <span className="inline-flex items-center gap-1 rounded-full bg-primary px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-primary-foreground shadow-sm">
            <BadgeCheck className="w-3 h-3" />
            {t('recommended')}
          </span>
        </div>
      )}
      <div
        onClick={() => onSelect(plan.tier)}
        className={`relative rounded-xl border overflow-hidden flex flex-col bg-card cursor-pointer transition-all hover:-translate-y-0.5 ${
          isRecommended
            ? 'border-primary/40 ring-1 ring-primary/20 shadow-lg shadow-primary/10 md:-translate-y-1'
            : 'border-border hover:border-primary/30'
        } ${isRegenerating ? 'pointer-events-none' : ''}`}
      >
        {onRegenerateTier && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onRegenerateTier(plan.tier);
            }}
            disabled={isRegenerating}
            aria-label={t('regenerateTier')}
            title={t('regenerateTier')}
            className="absolute top-2.5 right-2.5 z-20 p-1.5 rounded-md text-muted-foreground/60 hover:text-foreground hover:bg-muted transition-colors cursor-pointer disabled:cursor-default"
          >
            <RotateCcw className={`w-3.5 h-3.5 ${isRegenerating ? 'animate-spin' : ''}`} />
          </button>
        )}
        {isRegenerating && (
          <div className="absolute inset-0 z-10 shimmer bg-muted/50" aria-hidden="true" />
        )}
        {/* Tier header + hero price */}
        <div className="px-4 pt-4 pb-3 border-b border-border/60">
          <div className="flex items-center gap-2 mb-2">
            <Icon className={`w-4 h-4 ${cfg.color}`} />
            <span className={`font-semibold text-sm capitalize ${cfg.color}`}>{t(tierKey)}</span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-mono font-semibold tracking-tight text-foreground tabular-nums">
              {total != null
                ? formatCurrency(animatedTotal, locale, undefined, currency)
                : tItin('na')}
            </span>
            {perDay != null && (
              <span className="text-xs text-muted-foreground font-mono tabular-nums">
                {t('perDay', { cost: formatCurrency(Math.round(perDay), locale, undefined, currency) })}
              </span>
            )}
          </div>
        </div>

        {/* Cost breakdown — only when we have real per-category numbers */}
        {hasCategoryBreakdown && breakdown && (
          <div className="px-4 py-2.5 border-b border-border/60">
            <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
              <div className="flex justify-between">
                <span className="text-muted-foreground">{t('stayType')}</span>
                <span className="text-foreground/80 font-mono tabular-nums">{breakdown.accommodation != null ? formatCurrency(breakdown.accommodation, locale, undefined, currency) : tItin('na')}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">{t('foodStyle')}</span>
                <span className="text-foreground/80 font-mono tabular-nums">{breakdown.food != null ? formatCurrency(breakdown.food, locale, undefined, currency) : tItin('na')}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">{t('activities')}</span>
                <span className="text-foreground/80 font-mono tabular-nums">{breakdown.activities != null ? formatCurrency(breakdown.activities, locale, undefined, currency) : tItin('na')}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">{t('transportMode')}</span>
                <span className="text-foreground/80 font-mono tabular-nums">{breakdown.transport != null ? formatCurrency(breakdown.transport, locale, undefined, currency) : tItin('na')}</span>
              </div>
            </div>
          </div>
        )}

        {/* Tradeoffs — gains vs sacrifices */}
        {plan.tradeoffs && plan.tradeoffs.length > 0 && (
          <div className="px-4 py-2.5 border-b border-border/60">
            <ul className="space-y-1">
              {plan.tradeoffs.slice(0, 3).map((tradeoff, i) => {
                const sacrifice = SACRIFICE_RE.test(tradeoff);
                const TIcon = sacrifice ? TrendingDown : TrendingUp;
                return (
                  <li key={i} className="text-xs text-muted-foreground flex items-start gap-1.5">
                    <TIcon className={`w-3 h-3 mt-0.5 shrink-0 ${sacrifice ? 'text-destructive/70' : 'text-chart-2'}`} />
                    <span>{tradeoff}</span>
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        {/* Day summary (expandable — only when day-by-day content exists) */}
        <div className="flex-1">
          {days.length > 0 ? (
            <button
              onClick={(e) => {
                e.stopPropagation();
                setExpanded(!expanded);
              }}
              className="w-full px-4 py-2 flex items-center justify-between text-xs text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
            >
              <span>{t('daysDestination', { count: dayCount, destination: itinerary.destination })}</span>
              {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            </button>
          ) : (
            <div className="w-full px-4 py-2 text-xs text-muted-foreground">
              {t('daysDestination', { count: dayCount, destination: itinerary.destination })}
            </div>
          )}
          <AnimatePresence>
            {expanded && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="overflow-hidden"
              >
                <div className="px-4 pb-3 space-y-1.5">
                  {days.map((day) => (
                    <div key={day.day} className="p-2 rounded-lg bg-muted border border-border flex gap-2">
                      <span className="w-5 h-5 shrink-0 rounded bg-background border border-border font-mono text-[10px] flex items-center justify-center text-muted-foreground">
                        {day.day}
                      </span>
                      <div className="min-w-0">
                        <p className="font-medium text-foreground/90 text-xs truncate">
                          {day.theme ?? tItin('dayN', { n: day.day })}
                        </p>
                        <p className="text-muted-foreground text-[10px] mt-0.5 truncate">
                          {day.morning?.activity ?? '—'} → {day.afternoon?.activity ?? '—'} → {day.evening?.activity ?? '—'}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Select button */}
        <div className="p-3 border-t border-border/60">
          <button
            onClick={(e) => {
              e.stopPropagation();
              onSelect(plan.tier);
            }}
            className={`w-full py-2 rounded-lg text-xs font-medium transition-all cursor-pointer ${
              isRecommended
                ? 'bg-primary text-primary-foreground hover:bg-primary/90 shadow-sm'
                : 'bg-transparent border border-border text-foreground/70 hover:border-primary/40 hover:text-foreground'
            }`}
          >
            {t('select', { tier: t(tierKey) })}
          </button>
        </div>
      </div>
    </motion.div>
  );
}

export default function ComparisonView({
  data,
  onSelect,
  onRegenerateTier,
  regeneratingTier,
}: {
  data: ComparisonData;
  onSelect: (tier: string) => void;
  onRegenerateTier?: (tier: string) => void;
  regeneratingTier?: string | null;
}) {
  const t = useTranslations('comparison');
  const locale = useLocale();
  const [currency] = useCurrency();
  const matrix = data.comparison_matrix;
  const tiers = ['budget', 'balanced', 'premium'] as const;
  const destination = data.plans[0]?.itinerary?.destination ?? '';

  const { data: destImage, isLoading: destImageLoading } = useSWR(
    destination ? `wikimedia:${destination}` : null,
    () => fetchWikimediaImage(destination),
    { revalidateOnFocus: false, dedupingInterval: 600000 }
  );

  return (
    <div className="mt-3 rounded-xl border border-border bg-card overflow-hidden shadow-sm">
      {/* Destination banner */}
      <div className="relative w-full" style={{ aspectRatio: '16 / 5' }}>
        {destImageLoading ? (
          <div className="w-full h-full animate-pulse bg-muted" />
        ) : destImage ? (
          <>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={destImage} alt={destination} className="w-full h-full object-cover" />
            <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/20 to-transparent" />
            <div className="absolute bottom-3 left-4">
              <h3 className="text-xl font-bold text-white drop-shadow-lg">{destination}</h3>
              <p className="text-white/80 text-xs">{t('title')}</p>
            </div>
          </>
        ) : (
          <div className="w-full h-full bg-accent flex flex-col items-start justify-end p-4">
            <h3 className="text-xl font-bold text-accent-foreground tracking-tight">{destination}</h3>
            <p className="text-accent-foreground/70 text-xs">{t('title')}</p>
          </div>
        )}
      </div>

      {/* Comparison matrix strip */}
      {matrix && (
        <div className="px-4 py-3 border-b border-border overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-muted-foreground">
                <th className="text-left font-normal py-1 pr-3"></th>
                {tiers.map((tier) => (
                  <th key={tier} className="text-left font-normal py-1 px-2">
                    <span className="inline-flex items-center gap-1.5 capitalize">
                      <span className={`w-2 h-2 rounded-full ${TIER_CONFIG[tier].dot}`} />
                      {tier}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {([
                { label: t('cost'), key: 'total_cost' as const, isCurrency: true },
                { label: t('stayType'), key: 'accommodation_type' as const, isCurrency: false },
                { label: t('foodStyle'), key: 'food_style' as const, isCurrency: false },
                { label: t('transportMode'), key: 'transport_mode' as const, isCurrency: false },
              ]).map((row) => (
                <tr key={row.key} className="border-t border-border/60">
                  <td className="py-1.5 pr-3 text-[10px] uppercase tracking-wider text-muted-foreground">{row.label}</td>
                  {tiers.map((tier) => (
                    <td key={tier} className="py-1.5 px-2 text-foreground/80 font-mono tabular-nums">
                      {row.isCurrency && matrix[row.key]?.[tier] != null
                        ? formatCurrency(Number(matrix[row.key]?.[tier]), locale, undefined, currency)
                        : (matrix[row.key]?.[tier] ?? '—')}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Plan cards */}
      <div className="p-4 grid grid-cols-1 md:grid-cols-3 gap-3 md:gap-4">
        {data.plans.map((plan, i) => (
          <PlanCard
            key={plan.tier}
            plan={plan}
            index={i}
            onSelect={onSelect}
            onRegenerateTier={onRegenerateTier}
            regeneratingTier={regeneratingTier}
          />
        ))}
      </div>
    </div>
  );
}
