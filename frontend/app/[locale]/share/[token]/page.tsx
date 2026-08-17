'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { getShare, type ShareData } from '@/lib/share-api';
import ItineraryCard from '@/components/ItineraryCard';
import { Loader2, AlertCircle, Sparkles } from 'lucide-react';

export default function SharePage() {
  const params = useParams();
  const token = params.token as string;
  const t = useTranslations('share');
  const [data, setData] = useState<ShareData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

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
          <AlertCircle className="w-10 h-10 text-red-500 mx-auto mb-4" />
          <h1 className="text-xl font-semibold text-foreground mb-2">{t('linkExpired')}</h1>
          <p className="text-sm text-muted-foreground">
            {t('linkExpiredDesc')}
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-background">
      <div className="max-w-3xl mx-auto px-4 py-12">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-foreground">{data.destination}</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {t('sharedItinerary')}
          </p>
        </div>
        <ItineraryCard itinerary={data.itinerary} printMode />
        <div className="mt-8 pt-6 border-t border-border flex items-center justify-center gap-2 text-sm text-muted-foreground">
          <Sparkles className="w-4 h-4 text-primary" />
          {t('poweredBy')}
        </div>
      </div>
    </main>
  );
}
