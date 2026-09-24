'use client';

import { useCallback, useRef, useState } from 'react';

/**
 * Tracks which pipeline skeleton should be showing: comparison cards between
 * generate_trip_plans tool_start and its payload; itinerary skeleton between
 * refine_itinerary start and its payload. Run-ids are tracked so unrelated
 * tool_end events (inner tool calls) never clear a skeleton early.
 */
export function useGenerationProgress() {
  const [generatingPlans, setGeneratingPlans] = useState(false);
  const [buildingItinerary, setBuildingItinerary] = useState(false);
  const plansRunIdRef = useRef<string | null>(null);
  const itinRunIdRef = useRef<string | null>(null);

  const trackPipelineToolStart = useCallback((tool: { name: string; run_id: string; parent_run_id?: string }) => {
    if (tool.parent_run_id) return;
    if (tool.name === 'generate_trip_plans') {
      plansRunIdRef.current = tool.run_id;
      setGeneratingPlans(true);
    } else if (tool.name === 'refine_itinerary') {
      itinRunIdRef.current = tool.run_id;
      setBuildingItinerary(true);
    }
  }, []);

  const trackPipelineToolEnd = useCallback((tool: { run_id: string }) => {
    if (tool.run_id === plansRunIdRef.current) {
      plansRunIdRef.current = null;
      setGeneratingPlans(false);
    }
    if (tool.run_id === itinRunIdRef.current) {
      itinRunIdRef.current = null;
      setBuildingItinerary(false);
    }
  }, []);

  const resetGenerationUI = useCallback(() => {
    plansRunIdRef.current = null;
    itinRunIdRef.current = null;
    setGeneratingPlans(false);
    setBuildingItinerary(false);
  }, []);

  return {
    generatingPlans,
    buildingItinerary,
    setGeneratingPlans,
    setBuildingItinerary,
    trackPipelineToolStart,
    trackPipelineToolEnd,
    resetGenerationUI,
  };
}
