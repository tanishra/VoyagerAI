import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
// Imported before ItineraryCard so the next/dynamic mock below can hand the
// real components back synchronously (bindings must be initialized before
// ItineraryCard's module body calls dynamic()).
import RealDayDetailPanel from '@/components/DayDetailPanel';
import RealItineraryEditor from '@/components/ItineraryEditor';
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
  // Dispatch on the loader's source — ItineraryCard lazy-loads the map,
  // day panel and editor. The map stays mocked; panel/editor resolve to
  // the real modules synchronously so the tests stay sync.
  default: (loader: () => Promise<unknown>) => {
    const src = String(loader);
    if (src.includes('ItineraryMap')) return MockMap;
    if (src.includes('DayDetailPanel')) return RealDayDetailPanel;
    if (src.includes('ItineraryEditor')) return RealItineraryEditor;
    return () => null;
  },
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

  it('renders localized schedule clashes in the warning block', () => {
    const itinerary = makeItinerary({
      schedule_clashes: [{ day: 2, prev: 'Museum', next: 'Dinner', time: '17:00' }],
    });
    render(<ItineraryCard itinerary={itinerary} threadId="t1" />);
    expect(screen.getByText(/'Museum' may overlap 'Dinner' at 17:00/)).toBeInTheDocument();
    // Legacy string warnings still render alongside.
    expect(screen.getByText(/Monsoon season in June-July/)).toBeInTheDocument();
  });

  it('shows packing essentials in non-print mode', () => {
    render(<ItineraryCard itinerary={makeItinerary()} threadId="t1" />);
    expect(screen.getByText('Passport')).toBeInTheDocument();
    expect(screen.getByText('Suica card')).toBeInTheDocument();
    expect(screen.getByText('Comfortable shoes')).toBeInTheDocument();
  });

  it('clicking a day row opens the day panel', () => {
    render(<ItineraryCard itinerary={makeItinerary()} threadId="t1" />);
    fireEvent.click(screen.getByText(/Day 1 — Arrival/));
    // panel shows every day, not just the clicked one
    expect(screen.getByText('Hotel check-in')).toBeInTheDocument();
    expect(screen.getByText('Senso-ji Temple')).toBeInTheDocument();
    expect(screen.getByText('Get a Suica card')).toBeInTheDocument();
  });

  it('View full opens the day panel', () => {
    render(<ItineraryCard itinerary={makeItinerary()} threadId="t1" />);
    fireEvent.click(screen.getByText(/View full/));
    expect(screen.getByText('Hotel check-in')).toBeInTheDocument();
    expect(screen.getByText('Avoid rush hour')).toBeInTheDocument();
  });

  it('closes panel when close button is clicked', () => {
    render(<ItineraryCard itinerary={makeItinerary()} threadId="t1" />);
    fireEvent.click(screen.getByText(/Day 1 — Arrival/));
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

  it('does not show the day summary block in print mode', () => {
    render(<ItineraryCard itinerary={makeItinerary()} threadId="t1" printMode />);
    expect(screen.queryByText('Day by day')).not.toBeInTheDocument();
  });

  it('print mode prefixes slot time when present', () => {
    const it = makeItinerary();
    it.days[0].morning = { ...it.days[0].morning, time: '09:30' };
    render(<ItineraryCard itinerary={it} threadId="t1" printMode />);
    expect(screen.getByText(/09:30 Hotel check-in/)).toBeInTheDocument();
  });

  it('clicking a day row sets activeDay on the map', () => {
    render(<ItineraryCard itinerary={makeItinerary()} threadId="t1" />);
    fireEvent.click(screen.getByText('Map'));
    fireEvent.click(screen.getByText(/Day 1 — Arrival/));
    const map = screen.getAllByTestId('itinerary-map')[0];
    expect(map.getAttribute('data-active-day')).toBe('1');
  });

  it('map marker click opens the panel at that day', () => {
    render(<ItineraryCard itinerary={makeItinerary()} threadId="t1" />);
    fireEvent.click(screen.getByText('Map'));
    fireEvent.click(screen.getByTestId('map-marker-click'));
    expect(screen.getByText('Senso-ji Temple')).toBeInTheDocument();
    const map = screen.getAllByTestId('itinerary-map')[0];
    expect(map.getAttribute('data-active-day')).toBe('2');
  });

  it('map day select click opens the panel at that day', () => {
    render(<ItineraryCard itinerary={makeItinerary()} threadId="t1" />);
    fireEvent.click(screen.getByText('Map'));
    fireEvent.click(screen.getByTestId('map-day-select'));
    expect(screen.getByText('Hotel check-in')).toBeInTheDocument();
    const map = screen.getAllByTestId('itinerary-map')[0];
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

describe('print static day maps (P10)', () => {
  const KEY = 'NEXT_PUBLIC_GOOGLE_MAPS_API_KEY';
  const orig = process.env[KEY];

  beforeEach(() => {
    process.env[KEY] = 'test-key';
  });
  afterEach(() => {
    if (orig === undefined) delete process.env[KEY];
    else process.env[KEY] = orig;
  });

  const withCoords = () => {
    const it = makeItinerary();
    it.days[0].morning = { ...it.days[0].morning, lat: 35.68, lng: 139.69 };
    it.days[0].afternoon = { ...it.days[0].afternoon, lat: 35.66, lng: 139.7 };
    it.days[0].evening = { ...it.days[0].evening, lat: 35.67, lng: 139.71 };
    // day 2 keeps no coords
    return it;
  };

  it('renders a static map image per day that has coordinates', () => {
    render(<ItineraryCard itinerary={withCoords()} threadId="t1" printMode />);
    const img = screen.getByAltText('Map for day 1');
    expect(img).toHaveAttribute('src', expect.stringContaining('staticmap'));
    expect(img.getAttribute('src')).toContain('label%3A1');
    expect(img.getAttribute('src')).toContain('label%3A3');
    // day 2 has no coords → no map
    expect(screen.queryByAltText('Map for day 2')).not.toBeInTheDocument();
  });

  it('renders no static maps without an API key', () => {
    delete process.env[KEY];
    render(<ItineraryCard itinerary={withCoords()} threadId="t1" printMode />);
    expect(screen.queryByAltText('Map for day 1')).not.toBeInTheDocument();
  });

  it('renders no static maps in non-print mode', () => {
    render(<ItineraryCard itinerary={withCoords()} threadId="t1" />);
    expect(screen.queryByAltText('Map for day 1')).not.toBeInTheDocument();
  });
});
