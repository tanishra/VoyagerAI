export interface TimeSlot {
  activity: string;
  location: string;
  cost_usd: number;
  duration: string;
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
  budget_status: 'within' | 'over' | 'under';
  visa_note: string;
  best_season_note: string;
  days: DayPlan[];
  warnings: string[];
  packing_essentials: string[];
}

export interface CostBreakdown {
  accommodation: number;
  food: number;
  activities: number;
  transport: number;
  total: number;
}

export interface PlanTier {
  tier: 'budget' | 'balanced' | 'premium';
  itinerary: Itinerary;
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
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  itinerary?: Itinerary;
  comparison?: ComparisonData;
}

export interface ChatStreamCallbacks {
  onToken?: (text: string) => void;
  onItinerary?: (itinerary: Itinerary) => void;
  onComparison?: (data: ComparisonData) => void;
  onStatus?: (status: { tool: string; status: string }) => void;
  onThreadId?: (threadId: string) => void;
  onDone?: () => void;
  onError?: (error: string) => void;
  onAbort?: () => void;
  signal?: AbortSignal;
}
