import { describe, it, expect, vi, beforeAll } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import DayDetailPanel from '@/components/DayDetailPanel';
import type { DayPlan } from '@/lib/types';

vi.mock('swr', () => ({
  default: () => ({ data: undefined, isLoading: false }),
}));

const { MockMap } = vi.hoisted(() => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const React = require('react');
  return {
    MockMap: ({ days }: { days?: DayPlan[] }) =>
      React.createElement('div', { 'data-testid': 'itinerary-map', 'data-days': days?.map(d => d.day).join(',') }),
  };
});
vi.mock('next/dynamic', () => ({ default: () => MockMap }));
vi.mock('@/components/ItineraryMap', () => ({ default: MockMap }));

const makeDay = (n: number, theme: string): DayPlan => ({
  day: n,
  theme,
  morning: { activity: `Morning ${n}`, location: 'Loc', cost_usd: 10, duration: '1h' },
  afternoon: { activity: `Afternoon ${n}`, location: 'Loc', cost_usd: 5, duration: '2h' },
  evening: { activity: `Evening ${n}`, location: 'Loc', cost_usd: 15, duration: '1h' },
  transport: 'Train',
  accommodation: 'Hotel',
  daily_cost_usd: 30,
  tips: [`Tip ${n}`],
});

const days = [makeDay(1, 'Arrival'), makeDay(2, 'Temples'), makeDay(3, 'Departure')];

beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

describe('DayDetailPanel', () => {
  it('renders every day section, not just one', () => {
    render(<DayDetailPanel days={days} destination="Tokyo" initialDay={2} onClose={vi.fn()} />);
    expect(screen.getByText(/Day 1 — Arrival/)).toBeInTheDocument();
    expect(screen.getByText(/Day 2 — Temples/)).toBeInTheDocument();
    expect(screen.getByText(/Day 3 — Departure/)).toBeInTheDocument();
  });

  it('shows all slots, transport, stay, tips and day total per day', () => {
    render(<DayDetailPanel days={days} destination="Tokyo" initialDay={1} onClose={vi.fn()} />);
    expect(screen.getAllByText('Hotel').length).toBe(3);
    expect(screen.getAllByText('Train').length).toBe(3);
    expect(screen.getByText('Tip 2')).toBeInTheDocument();
    expect(screen.getAllByText('Daily Cost').length).toBe(3);
  });

  it('renders one map per day scoped to that day', () => {
    render(<DayDetailPanel days={days} destination="Tokyo" initialDay={1} onClose={vi.fn()} />);
    const maps = screen.getAllByTestId('itinerary-map');
    expect(maps).toHaveLength(3);
    expect(maps[0].getAttribute('data-days')).toBe('1');
    expect(maps[1].getAttribute('data-days')).toBe('2');
    expect(maps[2].getAttribute('data-days')).toBe('3');
  });

  it('renders a pill per day and pill click scrolls to that day', () => {
    render(<DayDetailPanel days={days} destination="Tokyo" initialDay={1} onClose={vi.fn()} />);
    const pill = screen.getByRole('button', { name: 'Day 3' });
    fireEvent.click(pill);
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled();
  });

  it('scrolls to initialDay on mount', () => {
    render(<DayDetailPanel days={days} destination="Tokyo" initialDay={2} onClose={vi.fn()} />);
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled();
  });

  it('closes on Escape', () => {
    const onClose = vi.fn();
    render(<DayDetailPanel days={days} destination="Tokyo" initialDay={1} onClose={onClose} />);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalled();
  });

  it('closes on the X button', () => {
    const onClose = vi.fn();
    render(<DayDetailPanel days={days} destination="Tokyo" initialDay={1} onClose={onClose} />);
    fireEvent.click(screen.getByLabelText('Close day details'));
    expect(onClose).toHaveBeenCalled();
  });
});
