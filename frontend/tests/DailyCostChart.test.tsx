import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { NextIntlClientProvider } from 'next-intl';
import DailyCostChart from '@/components/DailyCostChart';
import en from '../messages/en.json';

function renderWithProvider(ui: React.ReactElement) {
  return render(
    <NextIntlClientProvider locale="en" messages={en as Record<string, unknown>}>
      {ui}
    </NextIntlClientProvider>
  );
}

const mockDays = [
  { day: 1, theme: 'Explore', morning: { activity: 'a', location: 'l', cost_usd: 10, duration: '2h' }, afternoon: { activity: 'b', location: 'l', cost_usd: 20, duration: '3h' }, evening: { activity: 'c', location: 'l', cost_usd: 30, duration: '2h' }, transport: 'bus', accommodation: 'hotel', daily_cost_usd: 100, tips: [] },
  { day: 2, theme: 'Adventure', morning: { activity: 'a', location: 'l', cost_usd: 15, duration: '2h' }, afternoon: { activity: 'b', location: 'l', cost_usd: 25, duration: '3h' }, evening: { activity: 'c', location: 'l', cost_usd: 35, duration: '2h' }, transport: 'train', accommodation: 'hotel', daily_cost_usd: 150, tips: [] },
  { day: 3, theme: 'Relax', morning: { activity: 'a', location: 'l', cost_usd: 5, duration: '2h' }, afternoon: { activity: 'b', location: 'l', cost_usd: 10, duration: '3h' }, evening: { activity: 'c', location: 'l', cost_usd: 15, duration: '2h' }, transport: 'walk', accommodation: 'hotel', daily_cost_usd: 50, tips: [] },
];

describe('DailyCostChart', () => {
  it('renders nothing when days is empty', () => {
    const { container } = renderWithProvider(<DailyCostChart days={[]} currency="USD" />);
    expect(container.firstChild).toBeNull();
  });

  it('renders bar chart with SVG when days are provided', () => {
    const { container } = renderWithProvider(
      <DailyCostChart days={mockDays} currency="USD" />
    );
    expect(container.querySelector('svg')).toBeInTheDocument();
  });

  it('shows average cost label', () => {
    renderWithProvider(
      <DailyCostChart days={mockDays} currency="USD" />
    );
    expect(screen.getAllByText(/Avg/).length).toBeGreaterThan(0);
  });

  it('shows day labels', () => {
    renderWithProvider(
      <DailyCostChart days={mockDays} currency="USD" />
    );
    expect(screen.getByText('Day 1')).toBeInTheDocument();
    expect(screen.getByText('Day 2')).toBeInTheDocument();
    expect(screen.getByText('Day 3')).toBeInTheDocument();
  });

  it('calls onBarClick when a bar is clicked', () => {
    const onBarClick = vi.fn();
    const { container } = renderWithProvider(
      <DailyCostChart days={mockDays} currency="USD" onBarClick={onBarClick} />
    );
    const groups = container.querySelectorAll('g');
    expect(groups.length).toBeGreaterThan(0);
    fireEvent.click(groups[0]);
    expect(onBarClick).toHaveBeenCalledTimes(1);
    expect(onBarClick).toHaveBeenCalledWith(mockDays[0]);
  });
});
