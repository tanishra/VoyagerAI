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

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  itinerary?: Itinerary;
}

export interface ChatStreamCallbacks {
  onToken?: (text: string) => void;
  onItinerary?: (itinerary: Itinerary) => void;
  onStatus?: (status: { tool: string; status: string }) => void;
  onThreadId?: (threadId: string) => void;
  onDone?: () => void;
  onError?: (error: string) => void;
  onAbort?: () => void;
  signal?: AbortSignal;
}
