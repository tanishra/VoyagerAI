'use client';

import { useState, lazy, Suspense, useCallback, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Globe, Sparkles, XCircle, RotateCcw } from 'lucide-react';
import TripWizard from '@/components/TripWizard';
import LoadingSkeleton from '@/components/LoadingSkeleton';
import ErrorBoundary from '@/components/ErrorBoundary';
import { fetchWithTimeout, isFetchError } from '@/lib/api';
import { saveItinerary, loadItinerary, clearItinerary } from '@/lib/storage';
import type { Itinerary, PlanRequest } from '@/lib/types';
import type { FetchError } from '@/lib/api';

const ItineraryView = lazy(() => import('@/components/ItineraryView'));

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const TIMEOUT_WARNING_SECONDS = 90;

export default function PlanPage() {
  const [itinerary, setItinerary] = useState<Itinerary | null>(() => loadItinerary());
  const [formData, setFormData] = useState<PlanRequest | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [replanningDay, setReplanningDay] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (loading || replanningDay !== null) {
      setElapsed(0);
      intervalRef.current = setInterval(() => {
        setElapsed(prev => prev + 1);
      }, 1000);
    } else {
      if (intervalRef.current) clearInterval(intervalRef.current);
      intervalRef.current = null;
      setElapsed(0);
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [loading, replanningDay]);

  useEffect(() => {
    if (itinerary) {
      saveItinerary(itinerary);
    }
  }, [itinerary]);

  const handleAbort = () => {
    abortRef.current?.abort();
  };

  const handlePlan = async (data: PlanRequest) => {
    setFormData(data);
    setLoading(true);
    setError(null);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const result = await fetchWithTimeout<{ success: boolean; itinerary?: Itinerary; error?: string }>(
        `${API_BASE}/plan`, data,
        { signal: controller.signal },
      );
      if (result.success && result.itinerary) {
        setItinerary(result.itinerary);
      } else {
        setError(result.error || 'Failed to generate itinerary.');
      }
    } catch (exc) {
      if (isFetchError(exc) && exc.isAborted) {
        setError(null);
        return;
      }
      setError(
        isFetchError(exc)
          ? exc.message
          : String(exc),
      );
    } finally {
      abortRef.current = null;
      setLoading(false);
    }
  };

  const handleReplanDay = useCallback(async (dayNumber: number, reason: string) => {
    if (!itinerary) return;
    setReplanningDay(dayNumber);
    setError(null);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const result = await fetchWithTimeout<{ success: boolean; itinerary?: Itinerary; error?: string }>(
        `${API_BASE}/replan-day`, { itinerary, day_number: dayNumber, reason },
        { signal: controller.signal },
      );
      if (result.success && result.itinerary) {
        setItinerary(result.itinerary);
      } else {
        setError(result.error || 'Failed to replan day.');
      }
    } catch (exc) {
      if (isFetchError(exc) && exc.isAborted) return;
      setError(
        isFetchError(exc)
          ? exc.message
          : String(exc),
      );
    } finally {
      abortRef.current = null;
      setReplanningDay(null);
    }
  }, [itinerary]);

  const handleReset = () => {
    setItinerary(null);
    setError(null);
    clearItinerary();
  };

  const handleRetry = () => {
    if (formData) handlePlan(formData);
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
          {error && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="max-w-2xl mx-auto mb-6"
            >
              <div
                className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-300 text-sm"
                role="alert"
              >
                <div className="flex items-start gap-3">
                  <span className="text-red-400 text-lg leading-none shrink-0">⚠</span>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium mb-0.5">Something went wrong</p>
                    <p className="text-red-300/70 break-words">{error}</p>
                  </div>
                  <button
                    onClick={() => setError(null)}
                    className="text-red-400 hover:text-red-300 transition-colors shrink-0 cursor-pointer"
                    aria-label="Dismiss error"
                  >
                    ✕
                  </button>
                </div>
                <div className="flex items-center gap-3 mt-3 pt-3 border-t border-red-500/10">
                  <button
                    onClick={handleRetry}
                    className="inline-flex items-center gap-1.5 text-xs font-medium text-red-300 hover:text-red-200 transition-colors cursor-pointer"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                    Try again
                  </button>
                  <button
                    onClick={handleReset}
                    className="text-xs text-red-300/60 hover:text-red-300 transition-colors cursor-pointer"
                  >
                    Start over
                  </button>
                </div>
              </div>
            </motion.div>
          )}

          <AnimatePresence mode="wait">
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
                  <p className="text-xs text-muted-foreground/60 mt-2">
                    This typically takes 60–90 seconds{' '}
                    <span className="text-white/40">(waiting {elapsed}s…)</span>
                  </p>
                  {elapsed > TIMEOUT_WARNING_SECONDS && (
                    <motion.div
                      initial={{ opacity: 0, y: 5 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="mt-4"
                    >
                      <p className="text-xs text-amber-400/80 mb-2">
                        This is taking longer than expected.
                      </p>
                      <button
                        onClick={handleAbort}
                        className="inline-flex items-center gap-1.5 text-xs font-medium text-red-400 hover:text-red-300 transition-colors cursor-pointer"
                      >
                        <XCircle className="w-3.5 h-3.5" />
                        Cancel request
                      </button>
                    </motion.div>
                  )}
                </div>
                <LoadingSkeleton />
              </motion.div>
            )}

            {!loading && replanningDay !== null && (
              <motion.div
                key="replan-loading"
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
                    Replanning day{' '}
                    <span className="text-white font-medium">{replanningDay}</span>
                    {' '}with Gemini…
                  </p>
                  <p className="text-xs text-muted-foreground/60 mt-2">
                    This typically takes 30–60 seconds{' '}
                    <span className="text-white/40">(waiting {elapsed}s…)</span>
                  </p>
                </div>
                <LoadingSkeleton />
              </motion.div>
            )}

            {!loading && replanningDay === null && itinerary && (
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

            {!loading && replanningDay === null && !itinerary && (
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
