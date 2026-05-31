import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ItineraryView from '@/components/ItineraryView';
import type { Itinerary } from '@/lib/types';

const mockItinerary: Itinerary = {
  destination: 'Kyoto',
  total_days: 5,
  estimated_total_cost_usd: 2500,
  budget_status: 'within',
  visa_note: 'Visa-free for many countries',
  best_season_note: 'Autumn (Oct-Nov) is stunning',
  days: [
    {
      day: 1,
      theme: 'Temples & Culture',
      morning: { activity: 'Kinkaku-ji', location: 'Kyoto', cost_usd: 8, duration: '2h' },
      afternoon: { activity: 'Arashiyama Bamboo Grove', location: 'Arashiyama', cost_usd: 5, duration: '2.5h' },
      evening: { activity: 'Gion District Walk', location: 'Gion', cost_usd: 10, duration: '2h' },
      transport: 'Bus pass - $10',
      accommodation: 'Ryokan - $150/night',
      daily_cost_usd: 173,
      tips: ['Start early to avoid crowds', 'Wear comfortable shoes'],
    },
  ],
  warnings: ['Typhoon season June-October', 'Peak crowds in November'],
  packing_essentials: ['Umbrella', 'Comfortable walking shoes', 'Portable charger'],
};

describe('ItineraryView', () => {
  it('renders destination in hero', () => {
    render(<ItineraryView itinerary={mockItinerary} onReplanDay={vi.fn()} replanLoading={false} onReset={vi.fn()} />);
    const kyotoElements = screen.getAllByText('Kyoto');
    expect(kyotoElements.length).toBeGreaterThanOrEqual(1);
  });

  it('renders AI-Generated Itinerary badge', () => {
    render(<ItineraryView itinerary={mockItinerary} onReplanDay={vi.fn()} replanLoading={false} onReset={vi.fn()} />);
    const badges = screen.getAllByText('AI-Generated Itinerary');
    expect(badges.length).toBeGreaterThanOrEqual(1);
  });

  it('renders New Trip button in top bar', () => {
    render(<ItineraryView itinerary={mockItinerary} onReplanDay={vi.fn()} replanLoading={false} onReset={vi.fn()} />);
    expect(screen.getByText('New Trip')).toBeInTheDocument();
  });

  it('calls onReset when New Trip is clicked', () => {
    const onReset = vi.fn();
    render(<ItineraryView itinerary={mockItinerary} onReplanDay={vi.fn()} replanLoading={false} onReset={onReset} />);
    fireEvent.click(screen.getByText('New Trip'));
    expect(onReset).toHaveBeenCalledOnce();
  });

  it('renders Plan Another Trip button at bottom', () => {
    render(<ItineraryView itinerary={mockItinerary} onReplanDay={vi.fn()} replanLoading={false} onReset={vi.fn()} />);
    expect(screen.getByText('Plan Another Trip')).toBeInTheDocument();
  });

  it('calls onReset when Plan Another Trip is clicked', () => {
    const onReset = vi.fn();
    render(<ItineraryView itinerary={mockItinerary} onReplanDay={vi.fn()} replanLoading={false} onReset={onReset} />);
    fireEvent.click(screen.getByText('Plan Another Trip'));
    expect(onReset).toHaveBeenCalledOnce();
  });

  it('renders budget summary section', () => {
    render(<ItineraryView itinerary={mockItinerary} onReplanDay={vi.fn()} replanLoading={false} onReset={vi.fn()} />);
    expect(screen.getByText('Estimated Total Cost')).toBeInTheDocument();
  });

  it('renders warnings section', () => {
    render(<ItineraryView itinerary={mockItinerary} onReplanDay={vi.fn()} replanLoading={false} onReset={vi.fn()} />);
    expect(screen.getByText((content) => content.includes('Travel Warnings'))).toBeInTheDocument();
    expect(screen.getByText('(2)')).toBeInTheDocument();
  });

  it('renders packing essentials section', () => {
    render(<ItineraryView itinerary={mockItinerary} onReplanDay={vi.fn()} replanLoading={false} onReset={vi.fn()} />);
    expect(screen.getByText('Packing Essentials')).toBeInTheDocument();
    expect(screen.getByText('(3)')).toBeInTheDocument();
  });

  it('renders timeline day with activity', () => {
    render(<ItineraryView itinerary={mockItinerary} onReplanDay={vi.fn()} replanLoading={false} onReset={vi.fn()} />);
    expect(screen.getByText('Day 1')).toBeInTheDocument();
    expect(screen.getByText('Temples & Culture')).toBeInTheDocument();
    expect(screen.getByText('Kinkaku-ji')).toBeInTheDocument();
  });

  it('renders day count in hero section', () => {
    render(<ItineraryView itinerary={mockItinerary} onReplanDay={vi.fn()} replanLoading={false} onReset={vi.fn()} />);
    expect(screen.getByText('5 days')).toBeInTheDocument();
  });

  it('passes replanLoading to TimelineDay', () => {
    render(<ItineraryView itinerary={mockItinerary} onReplanDay={vi.fn()} replanLoading={true} onReset={vi.fn()} />);
    fireEvent.click(screen.getByText('Replan This Day'));
    const replanBtn = screen.getByText('Replanning…');
    expect(replanBtn).toBeInTheDocument();
  });

  it('calls onReplanDay when a day is replanned', () => {
    const onReplanDay = vi.fn();
    render(<ItineraryView itinerary={mockItinerary} onReplanDay={onReplanDay} replanLoading={false} onReset={vi.fn()} />);
    fireEvent.click(screen.getByText('Replan This Day'));
    fireEvent.change(screen.getByLabelText('Reason to replan day 1'), { target: { value: 'Too many temples' } });
    fireEvent.click(screen.getByText('Replan'));
    expect(onReplanDay).toHaveBeenCalledWith(1, 'Too many temples');
  });

  it('renders with correct container width class', () => {
    const { container } = render(
      <ItineraryView itinerary={mockItinerary} onReplanDay={vi.fn()} replanLoading={false} onReset={vi.fn()} />
    );
    const outerDiv = container.firstChild as HTMLElement;
    expect(outerDiv.className).toContain('max-w-4xl');
  });

  it('renders visa note when present', () => {
    render(<ItineraryView itinerary={mockItinerary} onReplanDay={vi.fn()} replanLoading={false} onReset={vi.fn()} />);
    expect(screen.getByText('Visa-free for many countries')).toBeInTheDocument();
  });
});
