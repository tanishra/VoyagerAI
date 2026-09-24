import { describe, it, expect, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { mergeThreads } from '@/hooks/chat/useThreads';
import { useGenerationProgress } from '@/hooks/chat/useGenerationProgress';
import type { ThreadMeta } from '@/lib/threads-api';

const meta = (id: string, updated = 0, pinned_at = 0): ThreadMeta => ({
  thread_id: id, summary: id, created_at: 0, updated_at: updated,
  status: 'done', pinned: pinned_at > 0, pinned_at, message_count: 1,
});

describe('mergeThreads', () => {
  it('dedupes by thread_id and sorts pinned first then recency', () => {
    const prev = [meta('a', 100), meta('b', 200)];
    const next = [meta('b', 300), meta('c', 50)];
    const out = mergeThreads(prev, next);
    expect(out.map(t => t.thread_id)).toEqual(['b', 'a', 'c']);
    expect(out[0].updated_at).toBe(300);
  });

  it('pinned threads sort ahead regardless of recency', () => {
    const out = mergeThreads([meta('old', 999)], [meta('pin', 1, 5)]);
    expect(out[0].thread_id).toBe('pin');
  });
});

describe('useGenerationProgress', () => {
  it('tracks pipeline run ids so inner tool_end cannot clear skeletons', () => {
    const { result } = renderHook(() => useGenerationProgress());
    act(() => {
      result.current.trackPipelineToolStart({ name: 'generate_trip_plans', run_id: 'r1' });
    });
    expect(result.current.generatingPlans).toBe(true);

    // Inner tool call ends — skeleton stays
    act(() => result.current.trackPipelineToolEnd({ run_id: 'inner' }));
    expect(result.current.generatingPlans).toBe(true);

    act(() => result.current.trackPipelineToolEnd({ run_id: 'r1' }));
    expect(result.current.generatingPlans).toBe(false);
  });

  it('ignores child tools (parent_run_id set)', () => {
    const { result } = renderHook(() => useGenerationProgress());
    act(() => {
      result.current.trackPipelineToolStart({ name: 'generate_trip_plans', run_id: 'r1', parent_run_id: 'p' });
    });
    expect(result.current.generatingPlans).toBe(false);
  });

  it('tracks itinerary build independently', () => {
    const { result } = renderHook(() => useGenerationProgress());
    act(() => result.current.trackPipelineToolStart({ name: 'refine_itinerary', run_id: 'i1' }));
    expect(result.current.buildingItinerary).toBe(true);
    act(() => result.current.resetGenerationUI());
    expect(result.current.buildingItinerary).toBe(false);
    expect(result.current.generatingPlans).toBe(false);
  });
});
