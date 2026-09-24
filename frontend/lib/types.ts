export interface TimeSlot {
  activity: string;
  location: string;
  cost_usd: number;
  duration: string;
  lat?: number;
  lng?: number;
  // Set by the backend enricher when the slot's own location failed to
  // geocode and lat/lng are the destination centroid instead — the map
  // renders these pins dashed + labeled, never as exact positions.
  geo_approx?: boolean;
}

export interface DayPlan {
  day: number;
  theme: string;
  morning: TimeSlot;
  afternoon: TimeSlot;
  evening: TimeSlot;
  transport: string;
  accommodation: string;
  daily_cost_usd: number;
  tips: string[];
}

export interface Itinerary {
  destination: string;
  total_days: number;
  estimated_total_cost_usd: number | null;
  // The 3-letter ISO code the cost fields are actually expressed in — may
  // differ from the app's currency preference (e.g. the user typed "₹" in
  // chat). Absent on older/legacy itineraries — treat as unknown, not USD.
  currency?: string;
  // Optional: the deterministic prose-fallback parser (untagged comparison
  // prose from the model) only fills destination/total_days/cost — these
  // fields are absent in that shape, not just empty.
  budget_status?: 'within' | 'over' | 'under';
  visa_note?: string;
  best_season_note?: string;
  days: DayPlan[];
  warnings?: string[];
  packing_essentials?: string[];
  // Set when a research specialist failed during generation — the plan was
  // built on partial live data; UI shows a limited-data badge.
  research_limited?: boolean;
  research_gaps?: string[];
}

export interface CostBreakdown {
  // Optional: prose-fallback comparisons only populate `total`.
  accommodation?: number;
  food?: number;
  activities?: number;
  transport?: number;
  total: number;
}

// Comparison cards only need a summary stub — the hybrid pipeline emits
// plans without day-by-day detail (days arrive later via the itinerary event
// for the selected tier). Legacy payloads still include `days`, so it stays
// optional rather than removed.
export type PlanItineraryStub = Omit<Itinerary, 'days'> & { days?: DayPlan[] };

export interface PlanTier {
  tier: 'budget' | 'balanced' | 'premium';
  itinerary: PlanItineraryStub;
  cost_breakdown: CostBreakdown;
  tradeoffs: string[];
}

export interface ComparisonMatrix {
  total_cost: Record<string, number>;
  accommodation_type: Record<string, string>;
  food_style: Record<string, string>;
  activity_count: Record<string, number>;
  transport_mode: Record<string, string>;
}

export interface ComparisonData {
  plans: PlanTier[];
  comparison_matrix: ComparisonMatrix;
  // Set when a research specialist failed — plans were generated from
  // partial live data; UI shows a limited-data badge.
  research_limited?: boolean;
  research_gaps?: string[];
}

// Clarify cards — the model asks for missing fields via
// ask_clarifying_questions; the payload delivers selectable options.
export interface ClarifyOption {
  label: string;
  value?: string;
  description?: string;
}

export interface ClarifyQuestion {
  field: string;
  header: string;
  question: string;
  options: ClarifyOption[];
  multi_select: boolean;
}

export interface ClarifyData {
  questions: ClarifyQuestion[];
}

export interface ThinkingBlock {
  text: string;
}

export interface ToolCallEntry {
  run_id: string;
  name: string;
  input?: string;
  output?: string;
  status: 'running' | 'done' | 'error';
  error?: string;
  started_at?: number;
  ended_at?: number;
  parent_run_id?: string;
  // Max generation attempts across pipeline stages (>1 means validation
  // retries happened) — surfaced as a chip on the tool row.
  generation_attempts?: number;
}

export interface UsageEntry {
  input_tokens: number;
  output_tokens: number;
  model: string;
}

export interface ActivityData {
  thinking: ThinkingBlock[];
  tool_calls: ToolCallEntry[];
  usage: UsageEntry[];
  total_input_tokens: number;
  total_output_tokens: number;
}

export interface BranchInfo {
  checkpoint_id: string;
  is_current: boolean;
  preview?: string;
}

export interface GeneratedImage {
  data_url: string;
  alt: string;
  prompt: string;
}

export interface ChartDataPoint {
  label: string;
  [key: string]: string | number;
}

export interface GeneratedChart {
  type: 'chart';
  chart_type: 'bar' | 'pie';
  title: string;
  data: ChartDataPoint[];
  series_keys: string[];
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  itinerary?: Itinerary;
  comparison?: ComparisonData;
  clarify?: ClarifyData;
  activity?: ActivityData;
  wasStopped?: boolean;
  editing?: boolean;
  feedback?: 'up' | 'down';
  branches?: BranchInfo[];
  activeBranchIndex?: number;
  attachments?: import('./upload-api').UploadedFile[];
  images?: GeneratedImage[];
  charts?: GeneratedChart[];
  partialResearch?: boolean;
}

export interface ChatStreamCallbacks {
  onToken?: (text: string) => void;
  onItinerary?: (itinerary: Itinerary) => void;
  onComparison?: (data: ComparisonData) => void;
  onClarify?: (data: ClarifyData) => void;
  onImage?: (image: GeneratedImage) => void;
  onChart?: (chart: GeneratedChart) => void;
  onStatus?: (status: { tool: string; status: string }) => void;
  onThreadId?: (threadId: string) => void;
  onDone?: (data?: { budget_reached?: boolean }) => void;
  onError?: (error: string) => void;
  onAbort?: () => void;
  onCancelled?: () => void;
  onThinking?: (text: string) => void;
  onToolStart?: (tool: { name: string; input?: string; run_id: string; parent_run_id?: string }) => void;
  onToolEnd?: (tool: { name: string; output?: string; run_id: string; parent_run_id?: string }) => void;
  onToolError?: (tool: { name: string; error?: string; run_id: string; parent_run_id?: string }) => void;
  onUsage?: (usage: UsageEntry) => void;
  onSubagentProgress?: (data: { run_id: string; description: string }) => void;
  onReconnecting?: (attempt: number, maxAttempts: number) => void;
  signal?: AbortSignal;
  errorMessages?: {
    serverResponse?: (status: number, detail: string) => string;
    responseBody?: string;
    parseFailed?: string;
    streamEnded?: string;
    unexpected?: string;
  };
}
