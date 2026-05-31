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
  estimated_total_cost_usd: number;
  budget_status: 'within' | 'over' | 'under';
  visa_note: string;
  best_season_note: string;
  days: DayPlan[];
  warnings: string[];
  packing_essentials: string[];
}

export interface PlanRequest {
  destination: string;
  days: number;
  budget_usd: number;
  travel_style: string;
  group_type: string;
  dietary: string;
  constraints: string;
}
