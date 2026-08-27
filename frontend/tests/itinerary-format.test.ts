import { describe, it, expect } from 'vitest';
import { formatItineraryText, formatComparisonText, buildCopyContent } from '@/components/CopyButton';
import type { Itinerary, ComparisonData } from '@/lib/types';

function makeItinerary(overrides: Partial<Itinerary> = {}): Itinerary {
  return {
    destination: 'Tokyo, Japan',
    total_days: 2,
    estimated_total_cost_usd: 1200,
    budget_status: 'within',
    visa_note: 'No visa required for stays under 90 days',
    best_season_note: 'Spring (March-May) for cherry blossoms',
    days: [
      {
        day: 1,
        theme: 'Arrival & Shibuya',
        morning: { activity: 'Arrive at Narita Airport', location: 'Narita', cost_usd: 30, duration: '2h' },
        afternoon: { activity: 'Shibuya Crossing', location: 'Shibuya', cost_usd: 0, duration: '3h' },
        evening: { activity: 'Dinner in Shinjuku', location: 'Shinjuku', cost_usd: 45, duration: '2h' },
        transport: 'Narita Express',
        accommodation: 'Shinjuku Prince Hotel ($120)',
        daily_cost_usd: 195,
        tips: ['Get a Suica card for easy transit'],
      },
      {
        day: 2,
        theme: 'Temples & Culture',
        morning: { activity: 'Senso-ji Temple', location: 'Asakusa', cost_usd: 0, duration: '2h' },
        afternoon: { activity: 'Tokyo National Museum', location: 'Ueno', cost_usd: 10, duration: '3h' },
        evening: { activity: 'Ramen in Akihabara', location: 'Akihabara', cost_usd: 15, duration: '1h' },
        transport: 'Metro',
        accommodation: 'Shinjuku Prince Hotel ($120)',
        daily_cost_usd: 145,
        tips: ['Visit Senso-ji early to avoid crowds'],
      },
    ],
    warnings: ['Typhoon season runs June-October'],
    packing_essentials: ['comfortable walking shoes', 'rain jacket', 'power adapter'],
    ...overrides,
  };
}

function makeComparison(): ComparisonData {
  return {
    plans: [
      {
        tier: 'budget',
        itinerary: makeItinerary({ destination: 'Tokyo, Japan', estimated_total_cost_usd: 720 }),
        cost_breakdown: { accommodation: 150, food: 120, activities: 200, transport: 80, total: 720 },
        tradeoffs: ['Street food only', 'Shared hostel dorms'],
      },
      {
        tier: 'balanced',
        itinerary: makeItinerary({ estimated_total_cost_usd: 1200 }),
        cost_breakdown: { accommodation: 300, food: 200, activities: 400, transport: 150, total: 1200 },
        tradeoffs: ['Mid-range hotels', 'Mix of local restaurants'],
      },
      {
        tier: 'premium',
        itinerary: makeItinerary({ estimated_total_cost_usd: 1800 }),
        cost_breakdown: { accommodation: 500, food: 300, activities: 600, transport: 200, total: 1800 },
        tradeoffs: ['4-star hotels', 'Fine dining'],
      },
    ],
    comparison_matrix: {
      total_cost: { budget: 720, balanced: 1200, premium: 1800 },
      accommodation_type: { budget: 'Hostel', balanced: '3-star hotel', premium: '4-star hotel' },
      food_style: { budget: 'Street food', balanced: 'Local restaurants', premium: 'Fine dining' },
      activity_count: { budget: 9, balanced: 9, premium: 9 },
      transport_mode: { budget: 'Public transit', balanced: 'Transit + rideshare', premium: 'Taxi/rental' },
    },
  };
}

describe('formatItineraryText', () => {
  it('produces expected structure for a simple itinerary', () => {
    const text = formatItineraryText(makeItinerary());
    expect(text).toContain('📍 Tokyo, Japan — 2 days — $1,200');
    expect(text).toContain('Day 1: Arrival & Shibuya');
    expect(text).toContain('Morning: Arrive at Narita Airport (2h, $30)');
    expect(text).toContain('Transport: Narita Express');
    expect(text).toContain('Stay: Shinjuku Prince Hotel ($120)');
    expect(text).toContain('💡 Get a Suica card for easy transit');
    expect(text).toContain('⚠ Typhoon season runs June-October');
    expect(text).toContain('🎒 Pack: comfortable walking shoes, rain jacket, power adapter');
  });

  it('handles missing optional fields (no tips, no warnings, no packing essentials)', () => {
    const itin = makeItinerary({
      days: [{
        day: 1,
        theme: 'Test',
        morning: { activity: 'A', location: 'L', cost_usd: 10, duration: '1h' },
        afternoon: { activity: 'B', location: 'L', cost_usd: 20, duration: '2h' },
        evening: { activity: 'C', location: 'L', cost_usd: 30, duration: '1h' },
        transport: 'Bus',
        accommodation: 'Hotel',
        daily_cost_usd: 60,
        tips: [],
      }],
      warnings: [],
      packing_essentials: [],
    });
    const text = formatItineraryText(itin);
    expect(text).not.toContain('💡');
    expect(text).not.toContain('⚠');
    expect(text).not.toContain('🎒');
  });

  it('handles multiple days', () => {
    const text = formatItineraryText(makeItinerary());
    expect(text).toContain('Day 1: Arrival & Shibuya');
    expect(text).toContain('Day 2: Temples & Culture');
    expect(text).toContain('Visit Senso-ji early to avoid crowds');
  });
});

describe('formatComparisonText', () => {
  it('produces all 3 tiers', () => {
    const text = formatComparisonText(makeComparison());
    expect(text).toContain('=== BUDGET');
    expect(text).toContain('=== BALANCED');
    expect(text).toContain('=== PREMIUM');
    expect(text).toContain('Tradeoffs:');
    expect(text).toContain('Street food only');
    expect(text).toContain('4-star hotels');
  });

  it('handles missing cost breakdowns', () => {
    const data: ComparisonData = {
      plans: [
        {
          tier: 'budget',
          itinerary: makeItinerary({ estimated_total_cost_usd: null }),
          cost_breakdown: { accommodation: 0, food: 0, activities: 0, transport: 0, total: 0 },
          tradeoffs: [],
        },
      ],
      comparison_matrix: {
        total_cost: { budget: 0 },
        accommodation_type: { budget: 'N/A' },
        food_style: { budget: 'N/A' },
        activity_count: { budget: 0 },
        transport_mode: { budget: 'N/A' },
      },
    };
    const text = formatComparisonText(data);
    expect(text).toContain('=== BUDGET');
    expect(text).toContain('N/A');
  });
});

describe('buildCopyContent', () => {
  it('combines itinerary + message content', () => {
    const itin = makeItinerary();
    const result = buildCopyContent('Here is your plan!', itin, null);
    expect(result).toContain('📍 Tokyo, Japan');
    expect(result).toContain('Here is your plan!');
  });

  it('combines comparison + message content', () => {
    const comp = makeComparison();
    const result = buildCopyContent('Choose a plan:', null, comp);
    expect(result).toContain('=== BUDGET');
    expect(result).toContain('Choose a plan:');
  });

  it('returns just message content when no itinerary or comparison', () => {
    const result = buildCopyContent('Just text', null, null);
    expect(result).toBe('Just text');
  });
});
