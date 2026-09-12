import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import DayDetailModal from '@/components/DayDetailModal';
import type { DayPlan } from '@/lib/types';

vi.mock('@/components/ItineraryMap', () => ({
  default: () => <div data-testid="itinerary-map">Map</div>,
}));

const makeDay = (overrides?: Partial<DayPlan>): DayPlan => ({
  day: 1,
  theme: 'Arrival',
  morning: { activity: 'Hotel check-in', location: 'Tokyo Station', cost_usd: 20, duration: '1h' },
  afternoon: { activity: 'Shibuya Crossing', location: 'Shibuya', cost_usd: 0, duration: '2h' },
  evening: { activity: 'Ramen dinner', location: 'Ichiran', cost_usd: 15, duration: '1h' },
  transport: 'Train',
  accommodation: 'Shibuya Hotel',
  daily_cost_usd: 35,
  tips: ['Get a Suica card', 'Avoid rush hour', 'Try the local ramen'],
  ...overrides,
});

describe('DayDetailModal', () => {
  it('renders day number and theme in header', () => {
    const day = makeDay({ day: 3, theme: 'Temples' });
    render(<DayDetailModal day={day} dayNumber={3} destination="Tokyo" onClose={vi.fn()} />);
    expect(screen.getByText('Day 3 — Temples')).toBeInTheDocument();
  });

  it('renders all three activity blocks', () => {
    const day = makeDay();
    render(<DayDetailModal day={day} dayNumber={1} destination="Tokyo" onClose={vi.fn()} />);
    expect(screen.getByText('Hotel check-in')).toBeInTheDocument();
    expect(screen.getByText('Shibuya Crossing')).toBeInTheDocument();
    expect(screen.getByText('Ramen dinner')).toBeInTheDocument();
  });

  it('shows all tips not just the first', () => {
    const day = makeDay();
    render(<DayDetailModal day={day} dayNumber={1} destination="Tokyo" onClose={vi.fn()} />);
    expect(screen.getByText('Get a Suica card')).toBeInTheDocument();
    expect(screen.getByText('Avoid rush hour')).toBeInTheDocument();
    expect(screen.getByText('Try the local ramen')).toBeInTheDocument();
  });

  it('shows transport and accommodation', () => {
    const day = makeDay();
    render(<DayDetailModal day={day} dayNumber={1} destination="Tokyo" onClose={vi.fn()} />);
    expect(screen.getByText('Train')).toBeInTheDocument();
    expect(screen.getByText('Shibuya Hotel')).toBeInTheDocument();
  });

  it('shows daily cost summary', () => {
    const day = makeDay({ daily_cost_usd: 120 });
    render(<DayDetailModal day={day} dayNumber={1} destination="Tokyo" onClose={vi.fn()} />);
    expect(screen.getByText(/120/)).toBeInTheDocument();
  });

  it('calls onClose when close button is clicked', () => {
    const onClose = vi.fn();
    const day = makeDay();
    render(<DayDetailModal day={day} dayNumber={1} destination="Tokyo" onClose={onClose} />);
    fireEvent.click(screen.getByLabelText('Close day details'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('calls onClose when Escape key is pressed', () => {
    const onClose = vi.fn();
    const day = makeDay();
    render(<DayDetailModal day={day} dayNumber={1} destination="Tokyo" onClose={onClose} />);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('renders mini-map', () => {
    const day = makeDay();
    render(<DayDetailModal day={day} dayNumber={1} destination="Tokyo" onClose={vi.fn()} />);
    expect(screen.getByTestId('itinerary-map')).toBeInTheDocument();
  });

  it('shows location for each activity', () => {
    const day = makeDay();
    render(<DayDetailModal day={day} dayNumber={1} destination="Tokyo" onClose={vi.fn()} />);
    expect(screen.getByText('Tokyo Station')).toBeInTheDocument();
    expect(screen.getByText('Shibuya')).toBeInTheDocument();
    expect(screen.getByText('Ichiran')).toBeInTheDocument();
  });

  it('shows duration for each activity', () => {
    const day = makeDay();
    render(<DayDetailModal day={day} dayNumber={1} destination="Tokyo" onClose={vi.fn()} />);
    expect(screen.getAllByText('1h').length).toBe(2);
    expect(screen.getByText('2h')).toBeInTheDocument();
  });
});
