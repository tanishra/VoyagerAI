import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ComparisonView from '@/app/[locale]/chat/ComparisonView';
import type { ComparisonData } from '@/lib/types';

const mockSwrData: Record<string, { data: unknown; isLoading: boolean }> = {};

vi.mock('swr', () => ({
  default: (key: string | null) => {
    if (key === null) return { data: undefined, isLoading: false };
    return mockSwrData[key] ?? { data: undefined, isLoading: false };
  },
}));

vi.mock('@/lib/wikimedia', () => ({
  fetchWikimediaImage: vi.fn().mockResolvedValue('https://example.com/tokyo.jpg'),
}));

const mockData: ComparisonData = {
  plans: [
    {
      tier: 'budget',
      itinerary: {
        destination: 'Tokyo',
        total_days: 3,
        estimated_total_cost_usd: 720,
        budget_status: 'within',
        visa_note: 'No visa required',
        best_season_note: 'Spring',
        days: [
          {
            day: 1,
            theme: 'Arrival',
            morning: { activity: 'Explore', location: 'Shibuya', cost_usd: 10, duration: '2h' },
            afternoon: { activity: 'Temple', location: 'Asakusa', cost_usd: 5, duration: '3h' },
            evening: { activity: 'Street food', location: 'Shinjuku', cost_usd: 15, duration: '2h' },
            transport: 'Public bus',
            accommodation: 'Hostel ($25)',
            daily_cost_usd: 80,
            tips: ['Bring cash'],
          },
        ],
        warnings: [],
        packing_essentials: [],
      },
      cost_breakdown: { accommodation: 150, food: 120, activities: 200, transport: 80, total: 720 },
      tradeoffs: ['Budget: street food only', 'Budget: shared hostel dorms'],
    },
    {
      tier: 'balanced',
      itinerary: {
        destination: 'Tokyo',
        total_days: 3,
        estimated_total_cost_usd: 1200,
        budget_status: 'within',
        visa_note: 'No visa required',
        best_season_note: 'Spring',
        days: [
          {
            day: 1,
            theme: 'Arrival',
            morning: { activity: 'Guided tour', location: 'Shibuya', cost_usd: 30, duration: '2h' },
            afternoon: { activity: 'Temple visit', location: 'Asakusa', cost_usd: 15, duration: '3h' },
            evening: { activity: 'Local restaurant', location: 'Shinjuku', cost_usd: 40, duration: '2h' },
            transport: 'Metro',
            accommodation: '3-star hotel ($100)',
            daily_cost_usd: 150,
            tips: ['Book in advance'],
          },
        ],
        warnings: [],
        packing_essentials: [],
      },
      cost_breakdown: { accommodation: 300, food: 200, activities: 300, transport: 150, total: 1200 },
      tradeoffs: ['Balanced: mid-range hotels'],
    },
    {
      tier: 'premium',
      itinerary: {
        destination: 'Tokyo',
        total_days: 3,
        estimated_total_cost_usd: 1800,
        budget_status: 'within',
        visa_note: 'No visa required',
        best_season_note: 'Spring',
        days: [
          {
            day: 1,
            theme: 'Arrival',
            morning: { activity: 'Private tour', location: 'Shibuya', cost_usd: 80, duration: '2h' },
            afternoon: { activity: 'Exclusive access', location: 'Asakusa', cost_usd: 50, duration: '3h' },
            evening: { activity: 'Fine dining', location: 'Ginza', cost_usd: 120, duration: '2h' },
            transport: 'Taxi',
            accommodation: '4-star hotel ($200)',
            daily_cost_usd: 250,
            tips: ['Reserve well ahead'],
          },
        ],
        warnings: [],
        packing_essentials: [],
      },
      cost_breakdown: { accommodation: 500, food: 400, activities: 500, transport: 300, total: 1800 },
      tradeoffs: ['Premium: 4-star hotels', 'Premium: fine dining'],
    },
  ],
  comparison_matrix: {
    total_cost: { budget: 720, balanced: 1200, premium: 1800 },
    accommodation_type: { budget: 'Hostel', balanced: '3-star hotel', premium: '4-star hotel' },
    food_style: { budget: 'Street food', balanced: 'Local restaurants', premium: 'Fine dining' },
    activity_count: { budget: 3, balanced: 3, premium: 3 },
    transport_mode: { budget: 'Public transit', balanced: 'Metro', premium: 'Taxi' },
  },
};

describe('ComparisonView', () => {
  it('renders all three tier labels', () => {
    render(<ComparisonView data={mockData} onSelect={() => {}} />);
    expect(screen.getByText('Budget')).toBeInTheDocument();
    expect(screen.getByText('Balanced')).toBeInTheDocument();
    expect(screen.getByText('Premium')).toBeInTheDocument();
  });

  it('displays total cost for each plan', () => {
    render(<ComparisonView data={mockData} onSelect={() => {}} />);
    // Costs appear in both the matrix table and plan card headers
    expect(screen.getAllByText('$720').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('$1,200').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('$1,800').length).toBeGreaterThanOrEqual(1);
  });

  it('renders comparison matrix values', () => {
    render(<ComparisonView data={mockData} onSelect={() => {}} />);
    expect(screen.getByText('Hostel')).toBeInTheDocument();
    expect(screen.getByText('3-star hotel')).toBeInTheDocument();
    expect(screen.getByText('4-star hotel')).toBeInTheDocument();
  });

  it('never shows NaN when cost_breakdown only has a total (prose-fallback shape)', () => {
    // Reproduces the deterministic prose parser's output shape: only
    // cost_breakdown.total is set, no accommodation/food/activities/transport,
    // and itinerary.days is empty (no per-day content in prose).
    const proseFallbackData: ComparisonData = {
      plans: [
        {
          tier: 'budget',
          itinerary: { destination: 'Tokyo', total_days: 5, days: [], estimated_total_cost_usd: 45000 },
          cost_breakdown: { total: 45000 },
          tradeoffs: ['Street food and hostels'],
        },
        {
          tier: 'balanced',
          itinerary: { destination: 'Tokyo', total_days: 5, days: [], estimated_total_cost_usd: 75000 },
          cost_breakdown: { total: 75000 },
          tradeoffs: ['Mid-range hotels'],
        },
        {
          tier: 'premium',
          itinerary: { destination: 'Tokyo', total_days: 5, days: [], estimated_total_cost_usd: 112500 },
          cost_breakdown: { total: 112500 },
          tradeoffs: ['Fine dining'],
        },
      ],
      comparison_matrix: {
        total_cost: { budget: 45000, balanced: 75000, premium: 112500 },
        accommodation_type: { budget: 'Hostel', balanced: '3-star hotel', premium: '4-star hotel' },
        food_style: { budget: 'Street food', balanced: 'Local restaurants', premium: 'Fine dining' },
        activity_count: {},
        transport_mode: { budget: 'Public transit', balanced: 'Transit + rideshare', premium: 'Private car' },
      },
    };
    render(<ComparisonView data={proseFallbackData} onSelect={() => {}} />);
    expect(screen.queryByText(/NaN/i)).not.toBeInTheDocument();
    // Falls back to total_days (5) since days[] is empty — not "0 days"
    expect(screen.getAllByText('5 days · Tokyo').length).toBe(3);
    expect(screen.queryByText('0 days · Tokyo')).not.toBeInTheDocument();
  });

  it('renders tradeoffs for each plan', () => {
    render(<ComparisonView data={mockData} onSelect={() => {}} />);
    expect(screen.getByText('Budget: street food only')).toBeInTheDocument();
    expect(screen.getByText('Premium: 4-star hotels')).toBeInTheDocument();
  });

  it('renders select buttons for each tier', () => {
    render(<ComparisonView data={mockData} onSelect={() => {}} />);
    expect(screen.getByText('Select Budget')).toBeInTheDocument();
    expect(screen.getByText('Select Balanced')).toBeInTheDocument();
    expect(screen.getByText('Select Premium')).toBeInTheDocument();
  });

  it('calls onSelect with correct tier when select button is clicked', () => {
    const onSelect = vi.fn();
    render(<ComparisonView data={mockData} onSelect={onSelect} />);
    fireEvent.click(screen.getByText('Select Balanced'));
    expect(onSelect).toHaveBeenCalledWith('balanced');
  });

  it('shows destination and day count in expandable header', () => {
    render(<ComparisonView data={mockData} onSelect={() => {}} />);
    expect(screen.getAllByText(/1 days · Tokyo/).length).toBe(3);
  });

  it('expands day details when clicked', () => {
    render(<ComparisonView data={mockData} onSelect={() => {}} />);
    const expandBtn = screen.getAllByText(/1 days · Tokyo/)[0];
    fireEvent.click(expandBtn);
    // After expanding, the day theme should be visible
    expect(screen.getAllByText(/Arrival/).length).toBeGreaterThan(0);
  });

  it('shows a single Recommended badge on the balanced plan', () => {
    render(<ComparisonView data={mockData} onSelect={() => {}} />);
    expect(screen.getAllByText('Recommended')).toHaveLength(1);
  });

  it('shows per-day cost under the total', () => {
    render(<ComparisonView data={mockData} onSelect={() => {}} />);
    // 1200 total / 1 day fixture = $1,200 per day
    expect(screen.getAllByText(/\$1,200 per day/).length).toBeGreaterThanOrEqual(1);
  });

  it('clicking a card body calls onSelect with that tier', () => {
    const onSelect = vi.fn();
    const { container } = render(<ComparisonView data={mockData} onSelect={onSelect} />);
    // Click the tradeoff text inside the premium card (not the button)
    fireEvent.click(screen.getByText('Premium: 4-star hotels'));
    expect(onSelect).toHaveBeenCalledWith('premium');
  });

  it('expand toggle does not trigger plan selection', () => {
    const onSelect = vi.fn();
    render(<ComparisonView data={mockData} onSelect={onSelect} />);
    fireEvent.click(screen.getAllByText(/1 days · Tokyo/)[0]);
    expect(onSelect).not.toHaveBeenCalled();
  });

  it('renders the destination banner image when loaded', () => {
    mockSwrData['wikimedia:Tokyo'] = { data: 'https://example.com/tokyo.jpg', isLoading: false };
    render(<ComparisonView data={mockData} onSelect={() => {}} />);
    const img = document.querySelector('img[alt="Tokyo"]');
    expect(img).toBeInTheDocument();
    delete mockSwrData['wikimedia:Tokyo'];
  });
});

describe('ComparisonView — single-tier regenerate (U6)', () => {
  it('shows no refresh buttons without a handler (legacy callers)', () => {
    render(<ComparisonView data={mockData} onSelect={() => {}} />);
    expect(screen.queryAllByRole('button', { name: /try a different plan/i })).toHaveLength(0);
  });

  it('renders one refresh button per card when handler provided', () => {
    render(<ComparisonView data={mockData} onSelect={() => {}} onRegenerateTier={() => {}} />);
    expect(screen.getAllByRole('button', { name: /try a different plan/i })).toHaveLength(3);
  });

  it('calls onRegenerateTier with the tier and does NOT trigger select', () => {
    const onRegen = vi.fn();
    const onSelect = vi.fn();
    render(<ComparisonView data={mockData} onSelect={onSelect} onRegenerateTier={onRegen} />);
    fireEvent.click(screen.getAllByRole('button', { name: /try a different plan/i })[2]);
    expect(onRegen).toHaveBeenCalledWith('premium');
    expect(onSelect).not.toHaveBeenCalled();
  });

  it('disables only the regenerating card button and spins its icon', () => {
    render(
      <ComparisonView
        data={mockData}
        onSelect={() => {}}
        onRegenerateTier={() => {}}
        regeneratingTier="balanced"
      />
    );
    const buttons = screen.getAllByRole('button', { name: /try a different plan/i });
    expect(buttons[0]).not.toBeDisabled();
    expect(buttons[1]).toBeDisabled();
    expect(buttons[2]).not.toBeDisabled();
    expect(buttons[1].querySelector('svg')?.className.baseVal).toContain('animate-spin');
  });
});

describe('limited research badge (R5)', () => {
  it('shows the badge when research_limited is set', () => {
    const data = { ...mockData, research_limited: true, research_gaps: ['researcher'] };
    render(<ComparisonView data={data} onSelect={() => {}} />);
    expect(screen.getByText(/Limited live data/i)).toBeInTheDocument();
  });

  it('hides the badge when research_limited is absent', () => {
    render(<ComparisonView data={mockData} onSelect={() => {}} />);
    expect(screen.queryByText(/Limited live data/i)).not.toBeInTheDocument();
  });
});

describe('currency source (U4)', () => {
  it('renders the plan currency, not the app preference', () => {
    const inrData = {
      ...mockData,
      plans: mockData.plans.map((p) => ({
        ...p,
        itinerary: { ...p.itinerary, currency: 'INR' },
      })),
    };
    render(<ComparisonView data={inrData} onSelect={() => {}} />);
    expect(screen.getAllByText(/₹/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/\$/)).not.toBeInTheDocument();
  });
});
