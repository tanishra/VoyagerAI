'use client';

import { useEffect, useState, useRef } from 'react';
import { useParams } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { getShare, type ShareData } from '@/lib/share-api';
import ShareCard from '@/components/ShareCard';
import ShareActions from '@/components/ShareActions';
import ItineraryCard from '@/components/ItineraryCard';
import { formatCurrency } from '@/lib/format';
import { useLocale } from '@/lib/useLocale';
import { useCurrency } from '@/lib/useCurrency';
import { Loader2, AlertCircle } from 'lucide-react';
import Link from 'next/link';

export default function SharePage() {
  const params = useParams();
  const token = params.token as string;
  const t = useTranslations('share');
  const [data, setData] = useState<ShareData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const cardRef = useRef<HTMLDivElement>(null);
  const locale = useLocale();
  const [currency] = useCurrency();

  useEffect(() => {
    if (!token) return;
    getShare(token).then((result) => {
      if (result) {
        setData(result);
      } else {
        setError(true);
      }
      setLoading(false);
    });
  }, [token]);

  if (loading) {
    return (
      <main className="min-h-screen flex items-center justify-center bg-background">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </main>
    );
  }

  if (error || !data) {
    return (
      <main className="min-h-screen flex items-center justify-center px-4 bg-background">
        <div className="text-center max-w-sm">
          <AlertCircle className="w-10 h-10 text-destructive mx-auto mb-4" />
          <h1 className="text-xl font-semibold text-foreground mb-2">{t('linkExpired')}</h1>
          <p className="text-sm text-muted-foreground">
            {t('linkExpiredDesc')}
          </p>
        </div>
      </main>
    );
  }

  const days = data.itinerary.total_days ?? (data.itinerary.days ?? []).length;
  const cost = formatCurrency(data.itinerary.estimated_total_cost_usd ?? 0, locale, undefined, currency);
  const destinationImage = data.image_base64
    ? `data:image/png;base64,${data.image_base64}`
    : undefined;

  return (
    <main className="min-h-screen bg-background">
      <div className="max-w-3xl mx-auto px-4 py-12">
        <ShareCard
          ref={cardRef}
          itinerary={data.itinerary}
          destinationImage={destinationImage}
        />
        <ShareActions
          shareUrl={typeof window !== 'undefined' ? window.location.href : ''}
          destination={data.destination}
          days={days}
          cost={cost}
          cardRef={cardRef}
        />
        <div className="h-px bg-border w-full mt-10 mb-8" />
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-foreground mb-4">{t('fullItinerary')}</h2>
          <ItineraryCard itinerary={data.itinerary} printMode />
        </div>
        <div className="pt-8 border-t border-border text-center">
          <Link
            href="/"
            className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-primary transition-colors"
          >
            <div className="w-1 h-4 bg-primary rounded-full" />
            {t('cardPlanYourOwn')}
          </Link>
        </div>
      </div>
    </main>
  );
}
