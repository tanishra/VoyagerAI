'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { getThreadHistory, type ThreadMessage } from '@/lib/threads-api';
import ItineraryCard from '@/components/ItineraryCard';
import type { Itinerary } from '@/lib/types';
import { Loader2, ArrowLeft, Printer } from 'lucide-react';
import Link from 'next/link';

export default function ExportPage() {
  const params = useParams();
  const threadId = params.threadId as string;
  const t = useTranslations('export');
  const [itinerary, setItinerary] = useState<Itinerary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!threadId) return;
    getThreadHistory(threadId).then((messages: ThreadMessage[]) => {
      for (let i = messages.length - 1; i >= 0; i--) {
        if (messages[i].itinerary) {
          setItinerary(messages[i].itinerary!);
          setLoading(false);
          return;
        }
      }
      setError(true);
      setLoading(false);
    });
  }, [threadId]);

  useEffect(() => {
    if (!loading && itinerary && !error) {
      const timer = setTimeout(() => window.print(), 500);
      return () => clearTimeout(timer);
    }
  }, [loading, itinerary, error]);

  if (loading) {
    return (
      <main className="min-h-screen flex items-center justify-center bg-white">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </main>
    );
  }

  if (error || !itinerary) {
    return (
      <main className="min-h-screen flex items-center justify-center bg-white px-4">
        <div className="text-center">
          <p className="text-sm text-muted-foreground mb-4">{t('noItinerary')}</p>
          <Link href="/chat" className="text-primary text-sm hover:underline">
            ← {t('backToChat')}
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-white">
      <div className="print-hidden max-w-3xl mx-auto px-4 py-6 flex items-center justify-between">
        <Link href="/chat" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors">
          <ArrowLeft className="w-4 h-4" />
          {t('backToChat')}
        </Link>
        <button
          onClick={() => window.print()}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors cursor-pointer"
        >
          <Printer className="w-3.5 h-3.5" />
          {t('print')}
        </button>
      </div>

      <div className="max-w-3xl mx-auto px-4 pb-12">
        <div className="mb-6 print-hidden">
          <h1 className="text-2xl font-bold text-foreground">{itinerary.destination}</h1>
          <p className="text-sm text-muted-foreground mt-1">{t('printOptimized')}</p>
        </div>
        <ItineraryCard itinerary={itinerary} printMode />
        <div className="mt-8 pt-6 border-t border-border text-center text-sm text-muted-foreground print-hidden">
          {t('printHint')}
        </div>
      </div>
    </main>
  );
}
