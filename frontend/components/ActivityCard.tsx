'use client';

import { useState } from 'react';
import useSWR from 'swr';
import { motion, AnimatePresence } from 'framer-motion';
import { MapPin, Clock, ChevronDown } from 'lucide-react';
import { useTranslations } from 'next-intl';
import dynamic from 'next/dynamic';
import type { TimeSlot } from '@/lib/types';
import { useLocale } from '@/lib/useLocale';
import { formatCurrency } from '@/lib/format';
import { useCurrency } from '@/lib/useCurrency';
import type { Currency } from '@/lib/currency';
import { fetchActivityImage } from '@/lib/wikimedia';
import { fetchWikipediaDescription } from '@/lib/wikipedia';

const ItineraryMap = dynamic(() => import('./ItineraryMap'), { ssr: false });

interface ActivityCardProps {
  currency?: Currency;
  slot: TimeSlot;
  slotKey: 'morning' | 'afternoon' | 'evening';
  destination: string;
}

const SLOT_COLORS: Record<string, string> = {
  morning: 'text-chart-1',
  afternoon: 'text-chart-2',
  evening: 'text-chart-3',
};

export default function ActivityCard({ slot, slotKey, destination, currency: propCurrency }: ActivityCardProps) {
  const t = useTranslations('itinerary');
  const locale = useLocale();
  const [preferredCurrency] = useCurrency();
  const currency = propCurrency ?? preferredCurrency;
  const [expanded, setExpanded] = useState(false);

  const { data: imageUrl, isLoading: imageLoading } = useSWR(
    `activity-image:${slot.activity}:${slot.location}:${destination}`,
    () => fetchActivityImage(slot.activity, slot.location, destination),
    { revalidateOnFocus: false, dedupingInterval: 600000 }
  );

  const { data: description, isLoading: descLoading } = useSWR(
    expanded ? `wikipedia:${slot.activity}` : null,
    () => fetchWikipediaDescription(slot.activity),
    { revalidateOnFocus: false, dedupingInterval: 600000 }
  );

  const hasCoords = typeof slot.lat === 'number' && typeof slot.lng === 'number';

  return (
    <div
      className={`rounded-lg border border-border overflow-hidden transition-colors ${expanded ? 'bg-muted/30' : 'hover:bg-muted/30'}`}
    >
      <button
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
        aria-label={slot.activity}
        className="w-full text-left p-2 cursor-pointer"
      >
        <div className="flex items-start gap-3">
          {/* Thumbnail */}
          <div className="w-16 h-16 rounded-lg overflow-hidden shrink-0 bg-muted flex items-center justify-center">
            {imageLoading ? (
              <div className="w-full h-full animate-pulse bg-muted" />
            ) : imageUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={imageUrl} alt={slot.activity} className="w-full h-full object-cover" />
            ) : (
              <MapPin className="w-6 h-6 text-muted-foreground" />
            )}
          </div>

          {/* Info */}
          <div className="flex-1 min-w-0 space-y-0.5">
            <p className={`text-[10px] font-medium uppercase tracking-widest ${SLOT_COLORS[slotKey]}`}>
              {t(slotKey)}
            </p>
            <p className="text-sm font-medium text-foreground truncate">{slot.activity}</p>
            <div className="flex items-center gap-3 text-xs text-muted-foreground flex-wrap">
              {slot.location && (
                <span className="flex items-center gap-1">
                  <MapPin className="w-3 h-3 shrink-0" />
                  {slot.location}
                </span>
              )}
              {slot.duration && (
                <span className="flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {slot.duration}
                </span>
              )}
              {slot.cost_usd != null && slot.cost_usd > 0 && (
                <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full text-[10px] font-medium ${SLOT_COLORS[slotKey]} bg-current/5`}>
                  {formatCurrency(slot.cost_usd, locale, undefined, currency)}
                </span>
              )}
            </div>
          </div>

          {/* Expand chevron */}
          <ChevronDown className={`w-4 h-4 text-muted-foreground shrink-0 transition-transform mt-1 ${expanded ? 'rotate-180' : ''}`} />
        </div>
      </button>

      {/* Expanded section */}
      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
            className="overflow-hidden"
            role="region"
            aria-label={`${slot.activity} details`}
          >
            <div className="px-2 pb-2 space-y-3">
              {/* Full image */}
              {imageUrl && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={imageUrl} alt={slot.activity} className="w-full h-32 rounded-lg object-cover" />
              )}

              {/* Wikipedia description */}
              {descLoading && (
                <p className="text-xs text-muted-foreground animate-pulse">{t('loadingDescription')}</p>
              )}
              {description && !descLoading && (
                <p className="text-xs text-muted-foreground leading-relaxed">{description}</p>
              )}

              {/* Mini-map */}
              {hasCoords && (
                <div className="rounded-lg overflow-hidden border border-border">
                  <ItineraryMap
                    days={[{
                      day: 1,
                      theme: '',
                      morning: slot,
                      afternoon: {} as TimeSlot,
                      evening: {} as TimeSlot,
                      transport: '',
                      accommodation: '',
                      daily_cost_usd: 0,
                      tips: [],
                    }]}
                    destination={slot.location || destination}
                    currency={currency}
                  />
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
