import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

vi.mock('swr', () => ({
  default: (key: string | null) => {
    if (key === null) return { data: undefined, isLoading: false };
    return { data: undefined, isLoading: false };
  },
}));

// Mock the Google Maps JS API — jsdom can't load the real loader/API.
const mockMarker = { setMap: vi.fn(), addListener: vi.fn() };
const mockPolyline = { setMap: vi.fn() };
const mockInfoWindow = { setContent: vi.fn(), open: vi.fn(), close: vi.fn() };
const mockMap = {
  fitBounds: vi.fn(),
  getZoom: vi.fn(() => 12),
  setZoom: vi.fn(),
};
const boundsInstances: Array<{ extend: (p: unknown) => void }> = [];
const markerInstances: Array<{ options: unknown }> = [];

const googleStub = {
  maps: {
    Map: class MockMap {
      fitBounds = mockMap.fitBounds;
      getZoom = mockMap.getZoom;
      setZoom = mockMap.setZoom;
    },
    marker: {
      PinElement: class MockPinElement {
        element: { style: Record<string, string> };
        constructor(public spec: unknown) {
          this.element = { style: {} };
        }
      },
      AdvancedMarkerElement: class MockAdvancedMarker {
        options: unknown;
        map: unknown;
        addListener = mockMarker.addListener;
        constructor(opts: unknown) {
          this.options = opts;
          this.map = (opts as { map?: unknown }).map;
          markerInstances.push(this);
        }
      },
    },
    Polyline: class MockPolyline {
      setMap = mockPolyline.setMap;
      constructor(public opts: unknown) {}
    },
    InfoWindow: class MockInfoWindow {
      setContent = mockInfoWindow.setContent;
      open = mockInfoWindow.open;
      close = mockInfoWindow.close;
    },
    LatLngBounds: class MockLatLngBounds {
      extend = vi.fn();
      constructor() {
        boundsInstances.push(this);
      }
    },
    Point: class MockPoint {
      constructor(public x: number, public y: number) {}
    },
    event: {
      trigger: vi.fn(),
      addListenerOnce: vi.fn((_map: unknown, _event: string, cb: () => void) => cb()),
    },
  },
};

const loaderState = { shouldFail: false };

vi.mock('@googlemaps/js-api-loader', () => ({
  setOptions: vi.fn(),
  importLibrary: vi.fn(() => {
    if (loaderState.shouldFail) return Promise.reject(new Error('load failed'));
    (window as unknown as { google: unknown }).google = googleStub;
    return Promise.resolve(googleStub.maps);
  }),
}));

import ItineraryMap, { extractMarkers, pinSpec } from '@/components/ItineraryMap';
import type { DayPlan } from '@/lib/types';

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

beforeEach(() => {
  vi.stubEnv('NEXT_PUBLIC_GOOGLE_MAPS_API_KEY', 'test-key');
  loaderState.shouldFail = false;
  vi.clearAllMocks();
  markerInstances.length = 0;
  boundsInstances.length = 0;
});

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
    const day1Btn = screen.getByText('Day 1');
    const day2Btn = screen.getByText('Day 2');
    fireEvent.click(day2Btn);
    expect(day2Btn.className).toContain('bg-primary');
    expect(day1Btn.className).not.toContain('bg-primary');
  });

  it('renders legend with activity names for the selected day', () => {
    render(<ItineraryMap days={daysWithCoords} destination="Paris, France" />);
    expect(screen.getByText(/Check-in/)).toBeInTheDocument();
    expect(screen.getByText(/Eiffel Tower/)).toBeInTheDocument();
    expect(screen.getByText(/Dinner/)).toBeInTheDocument();
  });

  it('only shows day tabs for days with coordinates', () => {
    const mixedDays: DayPlan[] = [daysWithCoords[0], daysNoCoords[0]];
    render(<ItineraryMap days={mixedDays} destination="Paris, France" />);
    expect(screen.queryByText('Day 2')).not.toBeInTheDocument();
  });

  it('uses activeDay prop in controlled mode', () => {
    render(<ItineraryMap days={daysWithCoords} destination="Paris, France" activeDay={2} />);
    const day2Btn = screen.getByText('Day 2');
    expect(day2Btn.className).toContain('bg-primary');
  });

  it('calls onDaySelect when tab is clicked', () => {
    const onDaySelect = vi.fn();
    render(<ItineraryMap days={daysWithCoords} destination="Paris, France" activeDay={1} onDaySelect={onDaySelect} />);
    fireEvent.click(screen.getByText('Day 2'));
    expect(onDaySelect).toHaveBeenCalledWith(2);
  });

  it('creates markers and fits bounds once the API loads', async () => {
    render(<ItineraryMap days={daysWithCoords} destination="Paris, France" />);
    await vi.waitFor(() => expect(markerInstances.length).toBe(3));
    expect(mockMap.fitBounds).toHaveBeenCalled();
  });

  it('shows the link-list fallback when no API key is configured', () => {
    vi.stubEnv('NEXT_PUBLIC_GOOGLE_MAPS_API_KEY', '');
    render(<ItineraryMap days={daysWithCoords} destination="Paris, France" />);
    expect(screen.getByText(/Map unavailable/)).toBeInTheDocument();
    expect(screen.getAllByText(/Check-in/).length).toBeGreaterThan(0);
  });

  it('falls back to a link list if the loader rejects', async () => {
    loaderState.shouldFail = true;
    render(<ItineraryMap days={daysWithCoords} destination="Paris, France" />);
    await vi.waitFor(() => expect(screen.getByText(/Map unavailable/)).toBeInTheDocument());
    expect(screen.getAllByText(/Check-in/).length).toBeGreaterThan(0);
  });

  it('re-fits bounds when itinerary markers change (edit/regenerate)', async () => {
    const { rerender } = render(
      <ItineraryMap days={daysWithCoords} destination="Paris, France" activeDay={1} />
    );
    await vi.waitFor(() => expect(markerInstances.length).toBe(3));
    const callsAfterMount = mockMap.fitBounds.mock.calls.length;

    const editedDays: DayPlan[] = daysWithCoords.map((d) => ({
      ...d,
      morning: d.morning
        ? { ...d.morning, activity: 'Changed activity', location: 'Elsewhere', lat: 40.71, lng: -74.0 }
        : d.morning,
    }));
    rerender(<ItineraryMap days={editedDays} destination="Paris, France" activeDay={1} />);
    await vi.waitFor(() =>
      expect(mockMap.fitBounds.mock.calls.length).toBeGreaterThan(callsAfterMount)
    );
  });
});

describe('approximate pins (geo_approx)', () => {
  it('extractMarkers flags geo_approx slots as approximate', () => {
    const day: DayPlan = {
      ...daysWithCoords[0],
      morning: { ...daysWithCoords[0].morning, geo_approx: true },
    };
    const markers = extractMarkers(day);
    expect(markers[0].approximate).toBe(true);
    expect(markers[1].approximate).toBe(false);
  });

  it('pinSpec colors pins by slot with a slot-number glyph', () => {
    const p1 = pinSpec(1);
    expect(p1.background).toBe('#b8402e');
    expect(p1.glyph).toBe('1');
    expect(pinSpec(2).glyph).toBe('2');
  });

  it('approximate slots get a dimmed pin element', async () => {
    const approxDays: DayPlan[] = [{
      ...daysWithCoords[0],
      morning: { ...daysWithCoords[0].morning, geo_approx: true },
    }];
    render(<ItineraryMap days={approxDays} destination="Paris, France" />);
    await vi.waitFor(() => expect(markerInstances.length).toBe(3));
    const pins = markerInstances.map(
      (m) => (m.options as { content: { style: Record<string, string> } }).content
    );
    expect(pins[0].style.opacity).toBe('0.4');
    expect(pins[1].style.opacity).toBeUndefined();
  });
});
