import type { ToolCallEntry } from './types';

/**
 * Pipeline/stage name -> `status` i18n key. Top-level tool calls with these
 * names own a "stage" the user cares about; inner tool calls (parent_run_id
 * set) are details, not stages.
 */
export const STAGE_LABEL_KEYS: Record<string, string> = {
  researcher: 'researching',
  risk_detector: 'checkingRisks',
  constraint_analyzer: 'checkingConstraints',
  validator: 'validating',
  enricher: 'addingTips',
  cost_optimizer: 'optimizingBudget',
  multi_plan_generator: 'generatingPlans',
  quality_scorer: 'scoringQuality',
  generate_trip_plans: 'generatingPlans',
  refine_itinerary: 'buildingItinerary',
};

export interface StageInfo {
  runId: string;
  labelKey: string;
}

/**
 * The stage currently in flight: the last top-level (no parent_run_id)
 * running tool call that maps to a label key. Returns null when nothing
 * stage-worthy is running so the caller can hide the status line.
 */
export function deriveStage(toolCalls: ToolCallEntry[]): StageInfo | null {
  for (let i = toolCalls.length - 1; i >= 0; i--) {
    const tc = toolCalls[i];
    if (tc.status !== 'running' || tc.parent_run_id) continue;
    const labelKey = STAGE_LABEL_KEYS[tc.name];
    if (labelKey) return { runId: tc.run_id, labelKey };
  }
  return null;
}

/**
 * Detail text for the status line: the newest progress description for the
 * running stage's run_id, else the newest description overall (covers
 * synthetic run_ids like "edit-validation" that have no tool_call entry).
 */
export function deriveStageDetail(
  progressMap: Record<string, string>,
  runId?: string,
): string | null {
  if (runId && progressMap[runId]) return progressMap[runId];
  const values = Object.values(progressMap);
  return values.length > 0 ? values[values.length - 1] : null;
}
