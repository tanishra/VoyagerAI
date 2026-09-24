'use client';

import { useCallback, useRef, useState } from 'react';
import type { ActivityData, ClarifyData, ComparisonData, GeneratedChart, GeneratedImage, Itinerary } from '@/lib/types';

/**
 * Streaming accumulators for the chat page — the per-run state that gets
 * filled by SSE events and cleared on send/new-chat/thread-switch/done.
 * Extracted so the 12-line reset block exists exactly once.
 */
export function useStreamAccumulators() {
  const [streamingText, setStreamingText] = useState('');
  const [streamingItinerary, setStreamingItinerary] = useState<Itinerary | null>(null);
  const [streamingComparison, setStreamingComparison] = useState<ComparisonData | null>(null);
  const [streamingClarify, setStreamingClarify] = useState<ClarifyData | null>(null);
  const [streamingImages, setStreamingImages] = useState<GeneratedImage[]>([]);
  const [streamingCharts, setStreamingCharts] = useState<GeneratedChart[]>([]);
  const [partialResearch, setPartialResearch] = useState(false);
  const [streamingActivity, setStreamingActivity] = useState<ActivityData | null>(null);
  const [activeWorkers, setActiveWorkers] = useState<string[]>([]);
  const [progressMap, setProgressMap] = useState<Record<string, string>>({});
  const streamingActivityRef = useRef<ActivityData | null>(null);

  const updateActivity = useCallback((updater: (prev: ActivityData | null) => ActivityData) => {
    const next = updater(streamingActivityRef.current);
    streamingActivityRef.current = next;
    setStreamingActivity(next);
  }, []);

  const resetStreamAccumulators = useCallback(() => {
    setStreamingText('');
    setStreamingItinerary(null);
    setStreamingComparison(null);
    setStreamingClarify(null);
    setStreamingImages([]);
    setStreamingCharts([]);
    setStreamingActivity(null);
    streamingActivityRef.current = null;
    setActiveWorkers([]);
    setProgressMap({});
  }, []);

  return {
    streamingText, setStreamingText,
    streamingItinerary, setStreamingItinerary,
    streamingComparison, setStreamingComparison,
    streamingClarify, setStreamingClarify,
    streamingImages, setStreamingImages,
    streamingCharts, setStreamingCharts,
    partialResearch, setPartialResearch,
    streamingActivity, setStreamingActivity,
    streamingActivityRef,
    activeWorkers, setActiveWorkers,
    progressMap, setProgressMap,
    updateActivity,
    resetStreamAccumulators,
  };
}

export type StreamAccumulators = ReturnType<typeof useStreamAccumulators>;
