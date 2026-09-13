import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

const mockSwrData: Record<string, { data: unknown; isLoading: boolean }> = {};

vi.mock('swr', () => ({
  default: (key: string | null) => {
    if (key === null) return { data: undefined, isLoading: false };
    return mockSwrData[key] ?? { data: undefined, isLoading: true };
  },
}));

vi.mock('@/components/ItineraryMap', () => ({
  default: () => <div data-testid="activity-map">Map</div>,
}));

vi.mock('next/dynamic', () => ({
  default: (fn: () => Promise<{ default: React.ComponentType }>) => {
    let Comp: React.ComponentType | null = null;
    fn().then((m) => { Comp = m.default; });
    return function DynamicComponent(props: Record<string, unknown>) {
      if (!Comp) return null;
      return React.createElement(Comp, props);
    };
  },
}));

import ActivityCard from '@/components/ActivityCard';
import type { TimeSlot } from '@/lib/types';

const makeSlot = (overrides?: Partial<TimeSlot>): TimeSlot => ({
  activity: 'Senso-ji Temple',
  location: 'Asakusa',
  cost_usd: 0,
  duration: '2h',
  ...overrides,
});

const setMock = (key: string, value: { data: unknown; isLoading: boolean }) => {
  mockSwrData[key] = value;
};

describe('ActivityCard', () => {
  beforeEach(() => {
    for (const key of Object.keys(mockSwrData)) delete mockSwrData[key];
  });

  it('renders activity name in collapsed state', () => {
    setMock('wikimedia:Senso-ji Temple Tokyo', { data: null, isLoading: false });
    render(<ActivityCard slot={makeSlot()} slotKey="morning" destination="Tokyo" />);
    expect(screen.getByText('Senso-ji Temple')).toBeInTheDocument();
  });

  it('renders location, cost, duration in collapsed state', () => {
    setMock('wikimedia:Senso-ji Temple Tokyo', { data: null, isLoading: false });
    render(<ActivityCard slot={makeSlot({ cost_usd: 10, duration: '3h' })} slotKey="afternoon" destination="Tokyo" />);
    expect(screen.getByText('Asakusa')).toBeInTheDocument();
    expect(screen.getByText('3h')).toBeInTheDocument();
    expect(screen.getByText('$10')).toBeInTheDocument();
  });

  it('shows skeleton placeholder while image is loading', () => {
    setMock('wikimedia:Senso-ji Temple Tokyo', { data: undefined, isLoading: true });
    const { container } = render(<ActivityCard slot={makeSlot()} slotKey="morning" destination="Tokyo" />);
    expect(container.querySelector('.animate-pulse')).toBeInTheDocument();
  });

  it('shows thumbnail image when loaded', () => {
    setMock('wikimedia:Senso-ji Temple Tokyo', { data: 'https://example.com/image.jpg', isLoading: false });
    render(<ActivityCard slot={makeSlot()} slotKey="morning" destination="Tokyo" />);
    expect(screen.getByAltText('Senso-ji Temple')).toBeInTheDocument();
  });

  it('shows MapPin fallback when no image found', () => {
    setMock('wikimedia:Senso-ji Temple Tokyo', { data: null, isLoading: false });
    const { container } = render(<ActivityCard slot={makeSlot()} slotKey="morning" destination="Tokyo" />);
    expect(container.querySelector('.lucide-map-pin')).toBeInTheDocument();
  });

  it('clicking card toggles expanded state', () => {
    setMock('wikimedia:Senso-ji Temple Tokyo', { data: null, isLoading: false });
    render(<ActivityCard slot={makeSlot()} slotKey="morning" destination="Tokyo" />);
    const button = screen.getByRole('button');
    expect(button).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(button);
    expect(button).toHaveAttribute('aria-expanded', 'true');
  });

  it('shows Wikipedia description when expanded and loaded', async () => {
    setMock('wikimedia:Senso-ji Temple Tokyo', { data: null, isLoading: false });
    setMock('wikipedia:Senso-ji Temple', { data: 'An ancient Buddhist temple in Tokyo.', isLoading: false });
    render(<ActivityCard slot={makeSlot()} slotKey="morning" destination="Tokyo" />);
    fireEvent.click(screen.getByRole('button'));
    await waitFor(() => {
      expect(screen.getByText('An ancient Buddhist temple in Tokyo.')).toBeInTheDocument();
    });
  });

  it('hides description section when Wikipedia returns null', () => {
    setMock('wikimedia:Senso-ji Temple Tokyo', { data: null, isLoading: false });
    setMock('wikipedia:Senso-ji Temple', { data: null, isLoading: false });
    render(<ActivityCard slot={makeSlot()} slotKey="morning" destination="Tokyo" />);
    fireEvent.click(screen.getByRole('button'));
    expect(screen.queryByText('Loading description...')).not.toBeInTheDocument();
  });

  it('shows mini-map when lat/lng exist and card is expanded', () => {
    setMock('wikimedia:Senso-ji Temple Tokyo', { data: null, isLoading: false });
    setMock('wikipedia:Senso-ji Temple', { data: null, isLoading: false });
    render(<ActivityCard slot={makeSlot({ lat: 35.7148, lng: 139.7967 })} slotKey="morning" destination="Tokyo" />);
    fireEvent.click(screen.getByRole('button'));
    expect(screen.getByTestId('activity-map')).toBeInTheDocument();
  });

  it('hides mini-map when no lat/lng', () => {
    setMock('wikimedia:Senso-ji Temple Tokyo', { data: null, isLoading: false });
    setMock('wikipedia:Senso-ji Temple', { data: null, isLoading: false });
    render(<ActivityCard slot={makeSlot()} slotKey="morning" destination="Tokyo" />);
    fireEvent.click(screen.getByRole('button'));
    expect(screen.queryByTestId('activity-map')).not.toBeInTheDocument();
  });
});
