import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ItineraryCard from '@/components/ItineraryCard';
import type { Itinerary } from '@/lib/types';

const mockSwrData: Record<string, { data: unknown; isLoading: boolean }> = {};

vi.mock('swr', () => ({
  default: (key: string | null) => {
    if (key === null) return { data: undefined, isLoading: false };
    return mockSwrData[key] ?? { data: undefined, isLoading: true };
  },
}));

const { MockMap } = vi.hoisted(() => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const React = require('react');
  return {
    MockMap: ({ activeDay, onMarkerClick, onDaySelect }: { activeDay?: number | null; onMarkerClick?: (d: number) => void; onDaySelect?: (d: number) => void }) =>
      React.createElement('div', { 'data-testid': 'itinerary-map', 'data-active-day': activeDay ?? null },
        React.createElement('button', { 'data-testid': 'map-marker-click', onClick: () => onMarkerClick?.(2) }, 'Marker Day 2'),
        React.createElement('button', { 'data-testid': 'map-day-select', onClick: () => onDaySelect?.(1) }, 'Select Day 1'),
      ),
  };
});

vi.mock('next/dynamic', () => ({
  default: () => MockMap,
}));

vi.mock('@/components/ItineraryMap', () => ({
  default: MockMap,
}));

vi.mock('@/lib/share-api', () => ({
  createShare: vi.fn(),
  exportItinerary: vi.fn(),
}));

const makeItinerary = (overrides?: Partial<Itinerary>): Itinerary => ({
  destination: 'Tokyo',
  total_days: 3,
  estimated_total_cost_usd: 500,
  budget_status: 'within',
  visa_note: 'No visa required for stays under 90 days',
  best_season_note: 'Spring (March-May) for cherry blossoms',
  days: [
    {
      day: 1,
      theme: 'Arrival',
      morning: { activity: 'Hotel check-in', location: 'Tokyo Station', cost_usd: 20, duration: '1h' },
      afternoon: { activity: 'Shibuya Crossing', location: 'Shibuya', cost_usd: 0, duration: '2h' },
      evening: { activity: 'Ramen dinner', location: 'Ichiran', cost_usd: 15, duration: '1h' },
      transport: 'Train',
      accommodation: 'Shibuya Hotel',
      daily_cost_usd: 35,
      tips: ['Get a Suica card', 'Avoid rush hour'],
    },
    {
      day: 2,
      theme: 'Temples',
      morning: { activity: 'Senso-ji Temple', location: 'Asakusa', cost_usd: 0, duration: '2h' },
      afternoon: { activity: 'Ueno Park', location: 'Ueno', cost_usd: 5, duration: '3h' },
      evening: { activity: 'Izakaya night', location: 'Shinjuku', cost_usd: 30, duration: '2h' },
      transport: 'Subway',
      accommodation: 'Shibuya Hotel',
      daily_cost_usd: 35,
      tips: ['Wear comfortable shoes', 'Bring a camera'],
    },
  ],
  warnings: ['Monsoon season in June-July', 'Trains stop at midnight'],
  packing_essentials: ['Passport', 'Suica card', 'Comfortable shoes'],
  ...overrides,
});

describe('ItineraryCard', () => {
  beforeEach(() => {
    for (const key of Object.keys(mockSwrData)) delete mockSwrData[key];
    mockSwrData['wikimedia:Tokyo'] = { data: 'https://example.com/tokyo.jpg', isLoading: false };
  });

  it('renders destination and budget', () => {
    render(<ItineraryCard itinerary={makeItinerary()} threadId="t1" />);
    expect(screen.getByText('Tokyo')).toBeInTheDocument();
  });

  it('renders timeline day bars with theme', () => {
    render(<ItineraryCard itinerary={makeItinerary()} threadId="t1" />);
    expect(screen.getByText(/Day 1 — Arrival/)).toBeInTheDocument();
    expect(screen.getByText(/Day 2 — Temples/)).toBeInTheDocument();
  });

  it('does not show transport/stay labels in collapsed view (non-print mode)', () => {
    render(<ItineraryCard itinerary={makeItinerary()} threadId="t1" />);
    expect(screen.queryByText(/Transport:/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Stay:/)).not.toBeInTheDocument();
  });

  it('shows all warnings not just the first', () => {
    render(<ItineraryCard itinerary={makeItinerary()} threadId="t1" />);
    expect(screen.getByText(/Monsoon season in June-July/)).toBeInTheDocument();
    expect(screen.getByText(/Trains stop at midnight/)).toBeInTheDocument();
  });

  it('shows packing essentials in non-print mode', () => {
    render(<ItineraryCard itinerary={makeItinerary()} threadId="t1" />);
    expect(screen.getByText('Passport')).toBeInTheDocument();
    expect(screen.getByText('Suica card')).toBeInTheDocument();
    expect(screen.getByText('Comfortable shoes')).toBeInTheDocument();
  });

  it('expands day bar inline when clicked (accordion)', () => {
    render(<ItineraryCard itinerary={makeItinerary()} threadId="t1" />);
    fireEvent.click(screen.getByText(/Day 1 — Arrival/));
    expect(screen.getByText('Hotel check-in')).toBeInTheDocument();
    expect(screen.getByText('Shibuya Crossing')).toBeInTheDocument();
    expect(screen.getByText('Ramen dinner')).toBeInTheDocument();
  });

  it('opens day detail modal via View Details button', () => {
    render(<ItineraryCard itinerary={makeItinerary()} threadId="t1" />);
    fireEvent.click(screen.getByText(/Day 1 — Arrival/));
    fireEvent.click(screen.getByText('View Details'));
    expect(screen.getByText('Get a Suica card')).toBeInTheDocument();
    expect(screen.getByText('Avoid rush hour')).toBeInTheDocument();
  });

  it('closes modal when close button is clicked', () => {
    render(<ItineraryCard itinerary={makeItinerary()} threadId="t1" />);
    fireEvent.click(screen.getByText(/Day 1 — Arrival/));
    fireEvent.click(screen.getByText('View Details'));
    expect(screen.getByText('Get a Suica card')).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText('Close day details'));
    expect(screen.queryByText('Get a Suica card')).not.toBeInTheDocument();
  });

  it('shows full details inline in print mode', () => {
    render(<ItineraryCard itinerary={makeItinerary()} threadId="t1" printMode />);
    expect(screen.getAllByText(/Transport:/).length).toBe(2);
    expect(screen.getAllByText(/Stay:/).length).toBe(2);
    expect(screen.getAllByText(/Daily cost:/).length).toBe(2);
  });

  it('does not show View Details button in print mode', () => {
    render(<ItineraryCard itinerary={makeItinerary()} threadId="t1" printMode />);
    expect(screen.queryByText('View Details')).not.toBeInTheDocument();
  });

  it('expanding a day in timeline sets activeDay on map', () => {
    render(<ItineraryCard itinerary={makeItinerary()} threadId="t1" />);
    fireEvent.click(screen.getByText(/Day 1 — Arrival/));
    const map = screen.getByTestId('itinerary-map');
    expect(map.getAttribute('data-active-day')).toBe('1');
  });

  it('map marker click sets activeDay and expands corresponding day', () => {
    render(<ItineraryCard itinerary={makeItinerary()} threadId="t1" />);
    fireEvent.click(screen.getByText('Map'));
    fireEvent.click(screen.getByTestId('map-marker-click'));
    expect(screen.getByText('Senso-ji Temple')).toBeInTheDocument();
    const map = screen.getByTestId('itinerary-map');
    expect(map.getAttribute('data-active-day')).toBe('2');
  });

  it('map day select click sets activeDay', () => {
    render(<ItineraryCard itinerary={makeItinerary()} threadId="t1" />);
    fireEvent.click(screen.getByText('Map'));
    fireEvent.click(screen.getByTestId('map-day-select'));
    const map = screen.getByTestId('itinerary-map');
    expect(map.getAttribute('data-active-day')).toBe('1');
  });

  it('does not show a budget breakdown section (removed — was showing wrong data)', () => {
    render(<ItineraryCard itinerary={makeItinerary()} threadId="t1" />);
    expect(screen.queryByText('Budget Breakdown')).not.toBeInTheDocument();
  });

  it('shows budget status badge next to cost', () => {
    render(<ItineraryCard itinerary={makeItinerary()} threadId="t1" />);
    expect(screen.getByText('Within budget')).toBeInTheDocument();
  });

  it('uses the itinerary currency over the app preference when formatting cost', () => {
    render(<ItineraryCard itinerary={makeItinerary({ currency: 'INR' })} threadId="t1" />);
    expect(screen.getByText('₹500')).toBeInTheDocument();
  });

  it('shows destination banner image when loaded', () => {
    render(<ItineraryCard itinerary={makeItinerary()} threadId="t1" />);
    expect(screen.getByAltText('Tokyo')).toBeInTheDocument();
  });

  it('shows skeleton while destination image is loading', () => {
    mockSwrData['wikimedia:Tokyo'] = { data: undefined, isLoading: true };
    const { container } = render(<ItineraryCard itinerary={makeItinerary()} threadId="t1" />);
    expect(container.querySelector('.animate-pulse')).toBeInTheDocument();
  });

  it('shows gradient fallback when no destination image', () => {
    mockSwrData['wikimedia:Tokyo'] = { data: null, isLoading: false };
    render(<ItineraryCard itinerary={makeItinerary()} threadId="t1" />);
    expect(screen.getByText('Tokyo')).toBeInTheDocument();
    expect(screen.queryByAltText('Tokyo')).not.toBeInTheDocument();
  });

  it('shows destination name overlaid on banner image', () => {
    render(<ItineraryCard itinerary={makeItinerary()} threadId="t1" />);
    expect(screen.getByText('Tokyo')).toBeInTheDocument();
    expect(screen.getByAltText('Tokyo')).toBeInTheDocument();
  });
});

describe('limited research badge (R5)', () => {
  it('shows the badge when research_limited is set', () => {
    render(<ItineraryCard itinerary={makeItinerary({ research_limited: true })} threadId="t1" />);
    expect(screen.getByText(/Limited live data/i)).toBeInTheDocument();
  });

  it('hides the badge when research_limited is absent', () => {
    render(<ItineraryCard itinerary={makeItinerary()} threadId="t1" />);
    expect(screen.queryByText(/Limited live data/i)).not.toBeInTheDocument();
  });
});

describe('edit changes strip (U5)', () => {
  const changes = [
    { type: 'changed' as const, day: 2, slot: 'morning', activity: 'Museum', detail: 'Temple' },
    { type: 'added' as const, day: 4, slot: 'evening', activity: 'Cooking class' },
    { type: 'cost' as const, before: 45000, after: 47500 },
  ];

  it('shows the strip when edit_changes present', () => {
    render(<ItineraryCard itinerary={makeItinerary({ edit_changes: changes })} threadId="t1" />);
    expect(screen.getByText(/adjusted your edits/i)).toBeInTheDocument();
  });

  it('expands to list each change', () => {
    render(<ItineraryCard itinerary={makeItinerary({ edit_changes: changes })} threadId="t1" />);
    fireEvent.click(screen.getByText(/adjusted your edits/i));
    expect(screen.getByText(/Museum.*→.*Temple/)).toBeInTheDocument();
    expect(screen.getByText(/added.*Cooking class/i)).toBeInTheDocument();
    expect(screen.getByText(/45,000.*→.*47,500/)).toBeInTheDocument();
  });

  it('hidden when edit_changes absent', () => {
    render(<ItineraryCard itinerary={makeItinerary()} threadId="t1" />);
    expect(screen.queryByText(/adjusted your edits/i)).not.toBeInTheDocument();
  });
});
