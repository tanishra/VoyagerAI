import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import BudgetSummary from '@/components/BudgetSummary';
import type { Itinerary } from '@/lib/types';

const baseItinerary: Itinerary = {
  destination: 'Tokyo',
  total_days: 7,
  estimated_total_cost_usd: 3500,
  budget_status: 'within',
  visa_note: 'Visa required for most nationalities',
  best_season_note: 'Spring (March-May) is ideal',
  days: [],
  warnings: [],
  packing_essentials: [],
};

describe('BudgetSummary', () => {
  it('renders the card with estimated total cost heading', () => {
    render(<BudgetSummary itinerary={baseItinerary} />);
    expect(screen.getByText('Estimated Total Cost')).toBeInTheDocument();
    expect(screen.getByText('USD')).toBeInTheDocument();
  });

  it('shows budget status badge', () => {
    render(<BudgetSummary itinerary={baseItinerary} />);
    expect(screen.getByText('Within Budget')).toBeInTheDocument();
  });

  it('shows over budget status', () => {
    const over: Itinerary = { ...baseItinerary, budget_status: 'over' };
    render(<BudgetSummary itinerary={over} />);
    expect(screen.getByText('Over Budget')).toBeInTheDocument();
  });

  it('shows under budget status', () => {
    const under: Itinerary = { ...baseItinerary, budget_status: 'under' };
    render(<BudgetSummary itinerary={under} />);
    expect(screen.getByText('Under Budget')).toBeInTheDocument();
  });

  it('shows per day average stat', () => {
    render(<BudgetSummary itinerary={baseItinerary} />);
    expect(screen.getByText('Per Day Avg')).toBeInTheDocument();
  });

  it('shows duration stat', () => {
    render(<BudgetSummary itinerary={baseItinerary} />);
    expect(screen.getByText('Duration')).toBeInTheDocument();
    expect(screen.getByText('days')).toBeInTheDocument();
  });

  it('shows total cost stat', () => {
    render(<BudgetSummary itinerary={baseItinerary} />);
    expect(screen.getByText('Total')).toBeInTheDocument();
  });

  it('shows "Your Budget" when budget prop is provided', () => {
    render(<BudgetSummary itinerary={baseItinerary} budget={5000} />);
    expect(screen.getByText('Your Budget')).toBeInTheDocument();
  });

  it('shows visa note with content', () => {
    render(<BudgetSummary itinerary={baseItinerary} />);
    expect(screen.getByText('Visa Note')).toBeInTheDocument();
    expect(screen.getByText('Visa required for most nationalities')).toBeInTheDocument();
  });

  it('shows best season note with content', () => {
    render(<BudgetSummary itinerary={baseItinerary} />);
    expect(screen.getByText('Best Season')).toBeInTheDocument();
    expect(screen.getByText('Spring (March-May) is ideal')).toBeInTheDocument();
  });

  it('hides visa note when not provided', () => {
    const noVisa: Itinerary = { ...baseItinerary, visa_note: '' };
    render(<BudgetSummary itinerary={noVisa} />);
    expect(screen.queryByText('Visa Note')).not.toBeInTheDocument();
  });

  it('hides best season note when not provided', () => {
    const noSeason: Itinerary = { ...baseItinerary, best_season_note: '' };
    render(<BudgetSummary itinerary={noSeason} />);
    expect(screen.queryByText('Best Season')).not.toBeInTheDocument();
  });

  it('renders BudgetGauge component', () => {
    const { container } = render(<BudgetSummary itinerary={baseItinerary} />);
    const gauge = container.querySelector('[role="img"]');
    expect(gauge).toBeInTheDocument();
  });

  it('caps budget percentage at 100', () => {
    const expensive: Itinerary = { ...baseItinerary, estimated_total_cost_usd: 10000 };
    render(<BudgetSummary itinerary={expensive} budget={5000} />);
    expect(screen.getByText('100%')).toBeInTheDocument();
  });

  it('shows correct percentage for within-budget trip', () => {
    render(<BudgetSummary itinerary={baseItinerary} budget={5000} />);
    expect(screen.getByText('70%')).toBeInTheDocument();
  });
});
