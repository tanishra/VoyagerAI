import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ItineraryMap from '@/components/ItineraryMap';
import type { DayPlan } from '@/lib/types';

// Mock maplibre-gl — jsdom has no WebGL/canvas support
const mockMarker = {
  setLngLat: vi.fn().mockReturnThis(),
  setPopup: vi.fn().mockReturnThis(),
  addTo: vi.fn().mockReturnThis(),
  remove: vi.fn(),
};
const mockPopup = {
  setHTML: vi.fn().mockReturnThis(),
};
const mockMap = {
  on: vi.fn((event: string, cb: () => void) => {
    if (event === 'load') cb();
  }),
  addSource: vi.fn(),
  addLayer: vi.fn(),
  fitBounds: vi.fn(),
  remove: vi.fn(),
};

vi.mock('maplibre-gl', () => {
  return {
    Map: class MockMap {
      on = mockMap.on;
      addSource = mockMap.addSource;
      addLayer = mockMap.addLayer;
      fitBounds = mockMap.fitBounds;
      remove = mockMap.remove;
    },
    Marker: class MockMarker {
      setLngLat = mockMarker.setLngLat;
      setPopup = mockMarker.setPopup;
      addTo = mockMarker.addTo;
      remove = mockMarker.remove;
    },
    Popup: class MockPopup {
      setHTML = mockPopup.setHTML;
    },
    LngLatBounds: class MockLngLatBounds {
      extend = vi.fn();
    },
  };
});

vi.mock('maplibre-gl/dist/maplibre-gl.css', () => ({}));

const daysWithCoords: DayPlan[] = [
  {
    day: 1,
    theme: 'Arrival',
    morning: { activity: 'Check-in', location: 'Hotel', cost_usd: 0, duration: '1h', lat: 48.86, lng: 2.34 },
    afternoon: { activity: 'Eiffel Tower', location: 'Champ de Mars', cost_usd: 30, duration: '3h', lat: 48.86, lng: 2.29 },
    evening: { activity: 'Dinner', location: 'Bistro', cost_usd: 50, duration: '2h', lat: 48.87, lng: 2.35 },
    transport: 'Metro',
    accommodation: 'Hotel',
    daily_cost_usd: 400,
    tips: [],
  },
  {
    day: 2,
    theme: 'Art',
    morning: { activity: 'Louvre', location: 'Rue de Rivoli', cost_usd: 17, duration: '3h', lat: 48.86, lng: 2.34 },
    afternoon: { activity: 'Montmartre', location: 'Butte Montmartre', cost_usd: 0, duration: '2h', lat: 48.89, lng: 2.34 },
    evening: { activity: 'Show', location: 'Moulin Rouge', cost_usd: 120, duration: '3h' },
    transport: 'Metro',
    accommodation: 'Hotel',
    daily_cost_usd: 400,
    tips: [],
  },
];

const daysNoCoords: DayPlan[] = [
  {
    day: 1,
    theme: 'Arrival',
    morning: { activity: 'Check-in', location: 'Hotel', cost_usd: 0, duration: '1h' },
    afternoon: { activity: 'Eiffel Tower', location: 'Champ de Mars', cost_usd: 30, duration: '3h' },
    evening: { activity: 'Dinner', location: 'Bistro', cost_usd: 50, duration: '2h' },
    transport: 'Metro',
    accommodation: 'Hotel',
    daily_cost_usd: 400,
    tips: [],
  },
];

describe('ItineraryMap', () => {
  it('renders map with day tabs when coordinates are present', () => {
    render(<ItineraryMap days={daysWithCoords} destination="Paris, France" />);
    expect(screen.getByText('Day 1')).toBeInTheDocument();
    expect(screen.getByText('Day 2')).toBeInTheDocument();
  });

  it('shows unavailable message when no coordinates', () => {
    render(<ItineraryMap days={daysNoCoords} destination="Paris, France" />);
    expect(screen.getByText(/Map unavailable/)).toBeInTheDocument();
  });

  it('switches day on tab click', () => {
    render(<ItineraryMap days={daysWithCoords} destination="Paris, France" />);
    // Day 1 should be active initially
    const day1Btn = screen.getByText('Day 1');
    const day2Btn = screen.getByText('Day 2');
    fireEvent.click(day2Btn);
    // After clicking Day 2, it should become active (primary style)
    expect(day2Btn.className).toContain('bg-primary');
    expect(day1Btn.className).not.toContain('bg-primary');
  });

  it('renders legend with activity names for the selected day', () => {
    render(<ItineraryMap days={daysWithCoords} destination="Paris, France" />);
    // Day 1 is selected by default — should show its activities in legend
    expect(screen.getByText(/Check-in/)).toBeInTheDocument();
    expect(screen.getByText(/Eiffel Tower/)).toBeInTheDocument();
    expect(screen.getByText(/Dinner/)).toBeInTheDocument();
  });

  it('only shows day tabs for days with coordinates', () => {
    const mixedDays: DayPlan[] = [daysWithCoords[0], daysNoCoords[0]];
    render(<ItineraryMap days={mixedDays} destination="Paris, France" />);
    // Only Day 1 should appear (Day 2 has no coords)
    expect(screen.getByText('Day 1')).toBeInTheDocument();
    expect(screen.queryByText('Day 2')).not.toBeInTheDocument();
  });
});
