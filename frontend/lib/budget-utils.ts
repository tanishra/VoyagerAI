import type { Itinerary, DayPlan, CostBreakdown } from '@/lib/types';

export function computeCostBreakdown(itinerary: Itinerary): CostBreakdown | null {
  const days = itinerary.days;
  if (!days || days.length === 0) return null;

  let accommodation = 0;
  let food = 0;
  let activities = 0;
  let transport = 0;

  for (const day of days) {
    // Estimate accommodation as ~40% of daily cost (common heuristic)
    // Or extract from accommodation field if it contains a price
    const accMatch = day.accommodation?.match(/\$?(\d[\d,]*)/);
    if (accMatch) {
      accommodation += parseFloat(accMatch[1].replace(/,/g, ''));
    } else {
      accommodation += day.daily_cost_usd * 0.4;
    }

    // Food: evening activity cost is typically dinner
    food += day.evening?.cost_usd ?? 0;

    // Activities: morning + afternoon costs
    activities += (day.morning?.cost_usd ?? 0) + (day.afternoon?.cost_usd ?? 0);

    // Transport: estimate as ~15% of daily cost
    transport += day.daily_cost_usd * 0.15;
  }

  const total = accommodation + food + activities + transport;

  return {
    accommodation: Math.round(accommodation),
    food: Math.round(food),
    activities: Math.round(activities),
    transport: Math.round(transport),
    total: Math.round(total),
  };
}

export function computeAverageDailyCost(days: DayPlan[]): number {
  if (!days || days.length === 0) return 0;
  const total = days.reduce((sum, day) => sum + (day.daily_cost_usd ?? 0), 0);
  return total / days.length;
}

export function getDailyCosts(days: DayPlan[]): { day: number; cost: number; theme: string }[] {
  return days.map((day) => ({
    day: day.day,
    cost: day.daily_cost_usd ?? 0,
    theme: day.theme ?? `Day ${day.day}`,
  }));
}
