import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ItineraryCard from '@/components/ItineraryCard';
import type { Itinerary } from '@/lib/types';

vi.mock('@/components/ItineraryMap', () => ({
  default: () => <div data-testid="itinerary-map">Map</div>,
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
});
