import { describe, it, expect, vi, beforeAll, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
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

  it('mounts only the initial day map; others activate on scroll', async () => {
    const { MockIntersectionObserver } = await import('./setup');
    MockIntersectionObserver.instances.length = 0;
    render(<DayDetailPanel days={days} destination="Tokyo" initialDay={1} onClose={vi.fn()} />);
    // Only day 1's map mounts on open — the rest lazy-mount on intersection.
    let maps = screen.getAllByTestId('itinerary-map');
    expect(maps).toHaveLength(1);
    expect(maps[0].getAttribute('data-days')).toBe('1');

    const io = MockIntersectionObserver.instances.at(-1);
    act(() => io?.triggerAll());
    await screen.findAllByTestId('itinerary-map');
    maps = screen.getAllByTestId('itinerary-map');
    expect(maps).toHaveLength(3);
  });

  it('pill click activates that day map immediately', () => {
    render(<DayDetailPanel days={days} destination="Tokyo" initialDay={1} onClose={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Day 3' }));
    const maps = screen.getAllByTestId('itinerary-map');
    expect(maps.map((m) => m.getAttribute('data-days')).sort()).toEqual(['1', '3']);
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

  it('lazy map placeholder shows a shimmer while the map mounts', () => {
    const { container } = render(
      <DayDetailPanel days={days} destination="Tokyo" initialDay={1} onClose={vi.fn()} />
    );
    // Days 2 and 3 are unactivated → shimmer placeholders.
    expect(container.querySelectorAll('.shimmer').length).toBe(2);
  });
});

describe('DayDetailPanel — long trips (>8 days)', () => {
  const longDays = Array.from({ length: 12 }, (_, i) => makeDay(i + 1, `Theme ${i + 1}`));

  it('mounts only the initial day content; other sections stay as shells', () => {
    render(<DayDetailPanel days={longDays} destination="Tokyo" initialDay={1} onClose={vi.fn()} />);
    // Every section/header exists…
    expect(screen.getByText(/Day 12 — Theme 12/)).toBeInTheDocument();
    // …but only day 1's content (map + cards) mounted.
    expect(screen.getAllByTestId('itinerary-map')).toHaveLength(1);
    expect(screen.getAllByText('Daily Cost')).toHaveLength(1);
  });

  it('scrolling near a day mounts its content via the prefetch observer', async () => {
    const { MockIntersectionObserver } = await import('./setup');
    MockIntersectionObserver.instances.length = 0;
    render(<DayDetailPanel days={longDays} destination="Tokyo" initialDay={1} onClose={vi.fn()} />);
    // Second observer = prefetch (80% margin) — firing it mounts everything.
    act(() => MockIntersectionObserver.instances.at(-1)?.triggerAll());
    expect(screen.getAllByText('Daily Cost')).toHaveLength(12);
    expect(screen.getAllByTestId('itinerary-map')).toHaveLength(12);
  });
});

describe('DayDetailPanel — pill strip arrows', () => {
  let scrollW: PropertyDescriptor | undefined;
  let clientW: PropertyDescriptor | undefined;

  beforeAll(() => {
    scrollW = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'scrollWidth');
    clientW = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'clientWidth');
  });

  afterEach(() => {
    if (scrollW) Object.defineProperty(HTMLElement.prototype, 'scrollWidth', scrollW);
    else delete (HTMLElement.prototype as never)['scrollWidth'];
    if (clientW) Object.defineProperty(HTMLElement.prototype, 'clientWidth', clientW);
    else delete (HTMLElement.prototype as never)['clientWidth'];
  });

  it('shows arrows only when the strip overflows and scrolls on click', () => {
    render(<DayDetailPanel days={days} destination="Tokyo" initialDay={1} onClose={vi.fn()} />);
    // No overflow in jsdom → no arrows.
    expect(screen.queryByLabelText('Previous days')).not.toBeInTheDocument();

    Object.defineProperty(HTMLElement.prototype, 'scrollWidth', { configurable: true, get: () => 600 });
    Object.defineProperty(HTMLElement.prototype, 'clientWidth', { configurable: true, get: () => 200 });
    const scrollBy = vi.fn();
    Object.defineProperty(HTMLElement.prototype, 'scrollBy', { configurable: true, value: scrollBy });

    render(<DayDetailPanel days={days} destination="Tokyo" initialDay={1} onClose={vi.fn()} />);
    fireEvent.click(screen.getAllByLabelText('Next days')[0]);
    expect(scrollBy).toHaveBeenCalledWith(expect.objectContaining({ left: 160 }));
    fireEvent.click(screen.getAllByLabelText('Previous days')[0]);
    expect(scrollBy).toHaveBeenCalledWith(expect.objectContaining({ left: -160 }));
  });
});
