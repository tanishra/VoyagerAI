import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { NextIntlClientProvider } from 'next-intl';
import ShareCard from '@/components/ShareCard';
import en from '../messages/en.json';
import type { Itinerary } from '@/lib/types';

vi.mock('@/lib/useLocale', () => ({
  useLocale: () => 'en',
}));

vi.mock('@/lib/useCurrency', () => ({
  useCurrency: () => ['USD'],
}));

const mockItinerary: Itinerary = {
  destination: 'Paris, France',
  total_days: 3,
  estimated_total_cost_usd: 1200,
  budget_status: 'within',
  visa_note: 'Schengen',
  best_season_note: 'April-June',
  days: [
    {
      day: 1,
      theme: 'Arrival',
      morning: { activity: 'Check-in at Hotel', location: 'Le Marais', cost_usd: 0, duration: '1h' },
      afternoon: { activity: 'Eiffel Tower', location: 'Champ de Mars', cost_usd: 30, duration: '3h' },
      evening: { activity: 'Seine Dinner Cruise', location: 'Seine River', cost_usd: 80, duration: '2h' },
      transport: 'Metro',
      accommodation: 'Hotel Marais',
      daily_cost_usd: 400,
      tips: [],
    },
  ],
  warnings: [],
  packing_essentials: [],
};

function renderWithProvider(ui: React.ReactElement) {
  return render(
    <NextIntlClientProvider locale="en" messages={en as Record<string, unknown>}>
      {ui}
    </NextIntlClientProvider>
  );
}

describe('ShareCard', () => {
  it('renders destination name', () => {
    renderWithProvider(<ShareCard itinerary={mockItinerary} />);
    expect(screen.getByRole('heading', { name: 'Paris, France' })).toBeInTheDocument();
  });

  it('renders trip duration', () => {
    renderWithProvider(<ShareCard itinerary={mockItinerary} />);
    expect(screen.getByText('3 days')).toBeInTheDocument();
  });

  it('renders total cost label', () => {
    renderWithProvider(<ShareCard itinerary={mockItinerary} />);
    expect(screen.getByText('Total Cost')).toBeInTheDocument();
  });

  it('renders highlights section', () => {
    renderWithProvider(<ShareCard itinerary={mockItinerary} />);
    expect(screen.getByText('Highlights')).toBeInTheDocument();
    expect(screen.getByText('Check-in at Hotel')).toBeInTheDocument();
    expect(screen.getByText('Eiffel Tower')).toBeInTheDocument();
  });

  it('renders powered by watermark', () => {
    renderWithProvider(<ShareCard itinerary={mockItinerary} />);
    expect(screen.getAllByText('Powered by VoyagerAI').length).toBeGreaterThan(0);
  });

  it('renders destination image when provided', () => {
    renderWithProvider(<ShareCard itinerary={mockItinerary} destinationImage="data:image/png;base64,abc123" />);
    const img = screen.getByAltText('Paris, France');
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute('src', 'data:image/png;base64,abc123');
  });

  it('renders gradient fallback when no image', () => {
    renderWithProvider(<ShareCard itinerary={mockItinerary} />);
    expect(screen.queryByAltText('Paris, France')).not.toBeInTheDocument();
    expect(screen.getAllByText('Paris, France').length).toBeGreaterThan(0);
  });

  it('renders without highlights when days are empty', () => {
    const emptyItinerary: Itinerary = {
      ...mockItinerary,
      days: [],
    };
    renderWithProvider(<ShareCard itinerary={emptyItinerary} />);
    expect(screen.queryByText('Highlights')).not.toBeInTheDocument();
  });
});
