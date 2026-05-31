'use client';

import { useState, lazy, Suspense, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Globe, Sparkles } from 'lucide-react';
import TripWizard from '@/components/TripWizard';
import LoadingSkeleton from '@/components/LoadingSkeleton';
import ErrorBoundary from '@/components/ErrorBoundary';
import type { Itinerary, PlanRequest } from '@/lib/types';

const ItineraryView = lazy(() => import('@/components/ItineraryView'));

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const CONNECTION_ERROR = 'Unable to connect to the server. Make sure it is running.';

async function fetchJSON<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`Server responded with status ${res.status}`);
  }
  return res.json();
}

export default function PlanPage() {
  const [itinerary, setItinerary] = useState<Itinerary | null>(null);
  const [formData, setFormData] = useState<PlanRequest | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [replanningDay, setReplanningDay] = useState<number | null>(null);

  const handlePlan = async (data: PlanRequest) => {
    setFormData(data);
    setLoading(true);
    setError(null);

    try {
      const result = await fetchJSON<{ success: boolean; itinerary?: Itinerary; error?: string }>(
        `${API_BASE}/plan`, data
      );
      if (result.success && result.itinerary) {
        setItinerary(result.itinerary);
      } else {
        setError(result.error || 'Failed to generate itinerary.');
      }
    } catch (exc) {
      setError(exc instanceof TypeError ? CONNECTION_ERROR : String(exc));
    } finally {
      setLoading(false);
    }
  };

  const handleReplanDay = useCallback(async (dayNumber: number, reason: string) => {
    if (!itinerary) return;
    setReplanningDay(dayNumber);

    try {
      const result = await fetchJSON<{ success: boolean; itinerary?: Itinerary; error?: string }>(
        `${API_BASE}/replan-day`, { itinerary, day_number: dayNumber, reason }
      );
      if (result.success && result.itinerary) {
        setItinerary(result.itinerary);
      } else {
        setError(result.error || 'Failed to replan day.');
      }
    } catch (exc) {
      setError(exc instanceof TypeError ? CONNECTION_ERROR : String(exc));
    } finally {
      setReplanningDay(null);
    }
  }, [itinerary]);

  const handleReset = () => {
    setItinerary(null);
    setError(null);
  };

  return (
    <main className="relative min-h-screen overflow-hidden pt-16">
      {/* Background gradients */}
      <div className="pointer-events-none fixed inset-0">
        <div className="absolute top-0 left-1/4 w-[600px] h-[600px] bg-sky-500/[0.07] rounded-full blur-[120px]" />
        <div className="absolute bottom-0 right-1/4 w-[500px] h-[500px] bg-blue-500/[0.05] rounded-full blur-[100px]" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[400px] bg-indigo-500/[0.03] rounded-full blur-[140px]" />
      </div>

      {/* Grid overlay */}
      <div
        className="pointer-events-none fixed inset-0 opacity-[0.015]"
        style={{
          backgroundImage: `linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)`,
          backgroundSize: '60px 60px',
        }}
      />

      <div className="relative z-10 flex flex-col min-h-screen">
        {/* Header */}
        <header className="px-4 pt-8 pb-6 md:pt-12 md:pb-8">
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
            className="text-center"
          >
            <div className="flex items-center justify-center gap-2.5 mb-3">
              <motion.div
                animate={{ rotate: [0, 10, -10, 0] }}
                transition={{ repeat: Infinity, duration: 6, ease: 'easeInOut' }}
                className="p-2 rounded-xl bg-gradient-to-br from-sky-500/20 to-blue-500/20 border border-sky-500/15"
              >
                <Globe className="w-6 h-6 text-sky-400" />
              </motion.div>
              <h1 className="text-3xl md:text-4xl font-bold bg-gradient-to-r from-white via-white/90 to-white/60 bg-clip-text text-transparent">
                Plan Your Trip
              </h1>
              <Sparkles className="w-5 h-5 text-amber-400/60" />
            </div>
            <p className="text-sm md:text-base text-muted-foreground max-w-md mx-auto">
              Gemini AI-powered trip planning — personalized itineraries in seconds
            </p>
          </motion.div>
        </header>

        {/* Main content */}
        <div className="flex-1 px-4 pb-12">
          <AnimatePresence mode="wait">
            {error && (
              <motion.div
                key="error"
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="max-w-2xl mx-auto mb-6"
              >
                <div
                  className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-300 text-sm flex items-start gap-3"
                  role="alert"
                >
                  <span className="text-red-400 text-lg leading-none">⚠</span>
                  <div className="flex-1">
                    <p className="font-medium mb-0.5">Something went wrong</p>
                    <p className="text-red-300/70">{error}</p>
                  </div>
                  <button
                    onClick={() => setError(null)}
                    className="ml-auto text-red-400 hover:text-red-300 transition-colors shrink-0 cursor-pointer"
                    aria-label="Dismiss error"
                  >
                    ✕
                  </button>
                </div>
              </motion.div>
            )}

            {loading && (
              <motion.div
                key="loading"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.3 }}
              >
                <div className="text-center mb-6">
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ repeat: Infinity, duration: 2, ease: 'linear' }}
                    className="inline-block mb-3"
                  >
                    <Globe className="w-8 h-8 text-sky-400" />
                  </motion.div>
                  <p className="text-sm text-muted-foreground">
                    Crafting your perfect itinerary for{' '}
                    <span className="text-white font-medium">{formData?.destination}</span>…
                  </p>
                </div>
                <LoadingSkeleton />
              </motion.div>
            )}

            {!loading && itinerary && (
              <motion.div
                key="itinerary"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.4 }}
              >
                <ErrorBoundary>
                  <Suspense fallback={<LoadingSkeleton />}>
                    <ItineraryView
                      itinerary={itinerary}
                      onReplanDay={handleReplanDay}
                      replanLoading={replanningDay !== null}
                      onReset={handleReset}
                      budget={formData?.budget_usd}
                    />
                  </Suspense>
                </ErrorBoundary>
              </motion.div>
            )}

            {!loading && !itinerary && (
              <motion.div
                key="form"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.4 }}
              >
                <TripWizard onSubmit={handlePlan} loading={loading} />
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </main>
  );
}
