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

describe('TimelineView', () => {
  it('renders all day bars with day number and theme', () => {
    render(<TimelineView days={makeDays()} destination="Tokyo" onDayClick={vi.fn()} />);
    expect(screen.getByText(/Day 1 — Arrival/)).toBeInTheDocument();
    expect(screen.getByText(/Day 2 — Temples/)).toBeInTheDocument();
  });

  it('shows color dots for morning, afternoon, evening', () => {
    const { container } = render(<TimelineView days={makeDays()} destination="Tokyo" onDayClick={vi.fn()} />);
    const dots = container.querySelectorAll('.rounded-full');
    // 2 days × 3 dots each = 6 color dots (plus 2 day markers = 8 total rounded-full)
    expect(dots.length).toBeGreaterThanOrEqual(6);
  });

  it('shows daily cost badge', () => {
    render(<TimelineView days={makeDays()} destination="Tokyo" onDayClick={vi.fn()} />);
    expect(screen.getByText(/35/)).toBeInTheDocument();
    expect(screen.getByText(/40/)).toBeInTheDocument();
  });

  it('clicking a day bar expands it showing activity blocks', () => {
    render(<TimelineView days={makeDays()} destination="Tokyo" onDayClick={vi.fn()} />);
    expect(screen.queryByText('Hotel check-in')).not.toBeInTheDocument();
    fireEvent.click(screen.getByText(/Day 1 — Arrival/));
    expect(screen.getByText('Hotel check-in')).toBeInTheDocument();
    expect(screen.getByText('Shibuya Crossing')).toBeInTheDocument();
    expect(screen.getByText('Ramen dinner')).toBeInTheDocument();
  });

  it('clicking an expanded day collapses it', () => {
    render(<TimelineView days={makeDays()} destination="Tokyo" onDayClick={vi.fn()} />);
    fireEvent.click(screen.getByText(/Day 1 — Arrival/));
    expect(screen.getByText('Hotel check-in')).toBeInTheDocument();
    fireEvent.click(screen.getByText(/Day 1 — Arrival/));
    expect(screen.queryByText('Hotel check-in')).not.toBeInTheDocument();
  });

  it('only one day expanded at a time', () => {
    render(<TimelineView days={makeDays()} destination="Tokyo" onDayClick={vi.fn()} />);
    fireEvent.click(screen.getByText(/Day 1 — Arrival/));
    expect(screen.getByText('Hotel check-in')).toBeInTheDocument();
    fireEvent.click(screen.getByText(/Day 2 — Temples/));
    expect(screen.queryByText('Hotel check-in')).not.toBeInTheDocument();
    expect(screen.getByText('Senso-ji Temple')).toBeInTheDocument();
  });

  it('expanded view shows location for each activity', () => {
    render(<TimelineView days={makeDays()} destination="Tokyo" onDayClick={vi.fn()} />);
    fireEvent.click(screen.getByText(/Day 1 — Arrival/));
    expect(screen.getByText('Tokyo Station')).toBeInTheDocument();
    expect(screen.getByText('Shibuya')).toBeInTheDocument();
    expect(screen.getByText('Ichiran')).toBeInTheDocument();
  });

  it('expanded view shows duration for each activity', () => {
    render(<TimelineView days={makeDays()} destination="Tokyo" onDayClick={vi.fn()} />);
    fireEvent.click(screen.getByText(/Day 1 — Arrival/));
    expect(screen.getAllByText('1h').length).toBe(2);
    expect(screen.getByText('2h')).toBeInTheDocument();
  });

  it('View Details button calls onDayClick', () => {
    const onDayClick = vi.fn();
    render(<TimelineView days={makeDays()} destination="Tokyo" onDayClick={onDayClick} />);
    fireEvent.click(screen.getByText(/Day 1 — Arrival/));
    fireEvent.click(screen.getByText('View Details'));
    expect(onDayClick).toHaveBeenCalledTimes(1);
    expect(onDayClick).toHaveBeenCalledWith(expect.objectContaining({ day: 1 }));
  });

  it('transport indicator shows correct text', () => {
    render(<TimelineView days={makeDays()} destination="Tokyo" onDayClick={vi.fn()} />);
    fireEvent.click(screen.getByText(/Day 1 — Arrival/));
    expect(screen.getAllByText('Train').length).toBe(2);
  });

  it('activeDay prop controls expanded day (controlled mode)', () => {
    render(<TimelineView days={makeDays()} destination="Tokyo" onDayClick={vi.fn()} activeDay={2} />);
    expect(screen.queryByText('Hotel check-in')).not.toBeInTheDocument();
    expect(screen.getByText('Senso-ji Temple')).toBeInTheDocument();
  });

  it('activeDay null collapses all days', () => {
    render(<TimelineView days={makeDays()} destination="Tokyo" onDayClick={vi.fn()} activeDay={null} />);
    expect(screen.queryByText('Hotel check-in')).not.toBeInTheDocument();
    expect(screen.queryByText('Senso-ji Temple')).not.toBeInTheDocument();
  });

  it('onDayExpand callback fires when day is toggled', () => {
    const onDayExpand = vi.fn();
    render(<TimelineView days={makeDays()} destination="Tokyo" onDayClick={vi.fn()} onDayExpand={onDayExpand} />);
    fireEvent.click(screen.getByText(/Day 1 — Arrival/));
    expect(onDayExpand).toHaveBeenCalledWith(1);
    fireEvent.click(screen.getByText(/Day 1 — Arrival/));
    expect(onDayExpand).toHaveBeenCalledWith(null);
  });

  it('works without activeDay/onDayExpand (uncontrolled mode)', () => {
    render(<TimelineView days={makeDays()} destination="Tokyo" onDayClick={vi.fn()} />);
    fireEvent.click(screen.getByText(/Day 1 — Arrival/));
    expect(screen.getByText('Hotel check-in')).toBeInTheDocument();
    fireEvent.click(screen.getByText(/Day 1 — Arrival/));
    expect(screen.queryByText('Hotel check-in')).not.toBeInTheDocument();
  });
});
