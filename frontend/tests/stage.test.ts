import { describe, it, expect } from 'vitest';
import { deriveStage, deriveStageDetail } from '@/lib/stage';
import type { ToolCallEntry } from '@/lib/types';

const tc = (over: Partial<ToolCallEntry>): ToolCallEntry => ({
  run_id: 'r1',
  name: 'x',
  status: 'running',
  ...over,
});

describe('deriveStage', () => {
  it('returns null with no tool calls', () => {
    expect(deriveStage([])).toBeNull();
  });

  it('returns null when nothing stage-worthy is running', () => {
    expect(deriveStage([tc({ name: 'internet_search' })])).toBeNull();
  });

  it('maps pipeline tools to stage labels', () => {
    const s = deriveStage([tc({ name: 'generate_trip_plans', run_id: 'p1' })]);
    expect(s).toEqual({ runId: 'p1', labelKey: 'generatingPlans' });
  });

  it('maps refine_itinerary to buildingItinerary', () => {
    const s = deriveStage([tc({ name: 'refine_itinerary', run_id: 'p2' })]);
    expect(s?.labelKey).toBe('buildingItinerary');
  });

  it('ignores nested (parent_run_id) tool calls', () => {
    const s = deriveStage([
      tc({ name: 'generate_trip_plans', run_id: 'p1' }),
      tc({ name: 'refine_itinerary', run_id: 'c1', parent_run_id: 'p1' }),
    ]);
    expect(s?.runId).toBe('p1');
  });

  it('picks the latest running top-level stage', () => {
    const s = deriveStage([
      tc({ name: 'researcher', run_id: 'r1', status: 'done' }),
      tc({ name: 'refine_itinerary', run_id: 'r2' }),
    ]);
    expect(s?.labelKey).toBe('buildingItinerary');
  });

  it('skips finished stages', () => {
    expect(
      deriveStage([tc({ name: 'generate_trip_plans', status: 'done' })]),
    ).toBeNull();
  });
});

describe('deriveStageDetail', () => {
  it('prefers the running stage run_id description', () => {
    const map = { other: 'x', p1: 'Searching: hotels' };
    expect(deriveStageDetail(map, 'p1')).toBe('Searching: hotels');
  });

  it('falls back to latest description (synthetic run_ids)', () => {
    const map = { 'edit-validation': 'Validating your edits...' };
    expect(deriveStageDetail(map, undefined)).toBe('Validating your edits...');
  });

  it('returns null when empty', () => {
    expect(deriveStageDetail({}, 'p1')).toBeNull();
  });
});
