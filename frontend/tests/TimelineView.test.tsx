import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import TimelineView from '@/components/TimelineView';
import type { DayPlan } from '@/lib/types';

const makeDay = (overrides?: Partial<DayPlan>): DayPlan => ({
  day: 1,
  theme: 'Arrival',
  morning: { activity: 'Hotel check-in', location: 'Tokyo Station', cost_usd: 20, duration: '1h' },
  afternoon: { activity: 'Shibuya Crossing', location: 'Shibuya', cost_usd: 0, duration: '2h' },
  evening: { activity: 'Ramen dinner', location: 'Ichiran', cost_usd: 15, duration: '1h' },
  transport: 'Train',
  accommodation: 'Shibuya Hotel',
  daily_cost_usd: 35,
  tips: ['Get a Suica card', 'Avoid rush hour'],
  ...overrides,
});

const makeDays = (): DayPlan[] => [
  makeDay({ day: 1, theme: 'Arrival' }),
  makeDay({
    day: 2,
    theme: 'Temples',
    transport: 'Walk',
    daily_cost_usd: 40,
    morning: { activity: 'Senso-ji Temple', location: 'Asakusa', cost_usd: 0, duration: '2h' },
    afternoon: { activity: 'Ueno Park', location: 'Ueno', cost_usd: 5, duration: '3h' },
    evening: { activity: 'Izakaya night', location: 'Shinjuku', cost_usd: 30, duration: '2h' },
  }),
];

describe('TimelineView (day summary rows)', () => {
  it('renders one row per day with number and theme', () => {
    render(<TimelineView days={makeDays()} destination="Tokyo" onDayClick={vi.fn()} />);
    expect(screen.getByText(/Day 1 — Arrival/)).toBeInTheDocument();
    expect(screen.getByText(/Day 2 — Temples/)).toBeInTheDocument();
  });

  it('compresses the day into a morning → afternoon → evening route line', () => {
    render(<TimelineView days={makeDays()} destination="Tokyo" onDayClick={vi.fn()} />);
    expect(
      screen.getByText('Hotel check-in → Shibuya Crossing → Ramen dinner')
    ).toBeInTheDocument();
    expect(
      screen.getByText('Senso-ji Temple → Ueno Park → Izakaya night')
    ).toBeInTheDocument();
  });

  it('shows the daily cost badge', () => {
    render(<TimelineView days={makeDays()} destination="Tokyo" onDayClick={vi.fn()} />);
    expect(screen.getByText(/35/)).toBeInTheDocument();
    expect(screen.getByText(/40/)).toBeInTheDocument();
  });

  it('clicking a day row fires onDayClick with that day', () => {
    const onDayClick = vi.fn();
    render(<TimelineView days={makeDays()} destination="Tokyo" onDayClick={onDayClick} />);
    fireEvent.click(screen.getByText(/Day 2 — Temples/));
    expect(onDayClick).toHaveBeenCalledTimes(1);
    expect(onDayClick).toHaveBeenCalledWith(expect.objectContaining({ day: 2 }));
  });

  it('View full opens at the first day', () => {
    const onDayClick = vi.fn();
    render(<TimelineView days={makeDays()} destination="Tokyo" onDayClick={onDayClick} />);
    fireEvent.click(screen.getByText(/View full/));
    expect(onDayClick).toHaveBeenCalledWith(expect.objectContaining({ day: 1 }));
  });

  it('skips missing slots in the route line', () => {
    const days = [makeDay({ afternoon: {} as DayPlan['afternoon'] })];
    render(<TimelineView days={days} destination="Tokyo" onDayClick={vi.fn()} />);
    expect(screen.getByText('Hotel check-in → Ramen dinner')).toBeInTheDocument();
  });
});
