import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ComparisonView from '@/app/[locale]/chat/ComparisonView';
import type { ComparisonData } from '@/lib/types';

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
});
