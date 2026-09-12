'use client';

import { forwardRef } from 'react';
import { useTranslations } from 'next-intl';
import { formatCurrency } from '@/lib/format';
import { useLocale } from '@/lib/useLocale';
import { useCurrency } from '@/lib/useCurrency';
import type { Itinerary } from '@/lib/types';

interface ShareCardProps {
  itinerary: Itinerary;
  destinationImage?: string;
}

function pickHighlights(itinerary: Itinerary, max: number = 3): { activity: string; location: string }[] {
  const highlights: { activity: string; location: string }[] = [];
  for (const day of itinerary.days ?? []) {
    for (const slot of [day.morning, day.afternoon, day.evening]) {
      if (slot && slot.activity && highlights.length < max) {
        highlights.push({ activity: slot.activity, location: slot.location });
      }
    }
    if (highlights.length >= max) break;
  }
  return highlights;
}

const ShareCard = forwardRef<HTMLDivElement, ShareCardProps>(function ShareCard(
  { itinerary, destinationImage },
  ref,
) {
  const t = useTranslations('share');
  const locale = useLocale();
  const [currency] = useCurrency();

  const days = itinerary.total_days ?? (itinerary.days ?? []).length;
  const cost = itinerary.estimated_total_cost_usd ?? 0;
  const highlights = pickHighlights(itinerary);

  return (
    <div
      ref={ref}
      className="bg-card rounded-xl overflow-hidden border border-border"
      style={{ width: '100%', maxWidth: '1200px' }}
    >
      {/* Destination hero image */}
      <div className="relative w-full" style={{ aspectRatio: '1200 / 480' }}>
        {destinationImage ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={destinationImage}
            alt={itinerary.destination}
            className="w-full h-full object-cover"
            crossOrigin="anonymous"
          />
        ) : (
          <div className="w-full h-full bg-accent flex items-center justify-center">
            <span className="text-4xl md:text-6xl font-bold text-accent-foreground tracking-tight">
              {itinerary.destination}
            </span>
          </div>
        )}
      </div>

      {/* Cinnabar hairline rule */}
      <div className="h-px bg-primary/40 w-full" />

      {/* Trip identity section */}
      <div className="px-8 md:px-10 py-8 md:py-10">
        <div className="flex items-end justify-between gap-4 mb-6">
          <div>
            <h1 className="text-3xl md:text-4xl font-bold text-foreground tracking-tight leading-tight">
              {itinerary.destination}
            </h1>
            <p className="font-mono text-sm text-primary tracking-widest mt-2 uppercase">
              {t('cardDays', { count: days })}
            </p>
          </div>
          <div className="text-right shrink-0">
            <p className="font-mono text-2xl md:text-3xl text-foreground tabular-nums">
              {formatCurrency(cost, locale, undefined, currency)}
            </p>
            <p className="font-mono text-xs text-muted-foreground tracking-wide mt-1">
              {t('cardTotalCost')}
            </p>
          </div>
        </div>

        {/* Cinnabar hairline divider */}
        <div className="h-px bg-border w-full mb-6" />

        {/* Highlights */}
        {highlights.length > 0 && (
          <div>
            <p className="font-mono text-xs text-muted-foreground tracking-widest uppercase mb-3">
              {t('cardHighlights')}
            </p>
            <ul className="space-y-2">
              {highlights.map((h, i) => (
                <li key={i} className="flex items-center gap-2 text-sm text-foreground">
                  <span className="w-1 h-1 rounded-full bg-primary shrink-0" />
                  <span className="font-medium">{h.activity}</span>
                  {h.location && (
                    <>
                      <span className="text-muted-foreground">·</span>
                      <span className="text-muted-foreground">{h.location}</span>
                    </>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Powered by watermark */}
      <div className="px-8 md:px-10 pb-6 flex items-center justify-end gap-2">
        <div className="w-1 h-4 bg-primary rounded-full" />
        <span className="font-mono text-xs text-muted-foreground tracking-wide">
          {t('cardPoweredBy')}
        </span>
      </div>
    </div>
  );
});

export default ShareCard;
