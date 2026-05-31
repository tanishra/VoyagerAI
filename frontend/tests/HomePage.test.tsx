import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import Home from '@/app/page';

vi.mock('lucide-react', () => {
  const MockIcon = ({ name }: { name?: string }) => <span data-testid={`icon-${name || 'default'}`} />;
  return {
    Globe: () => <span data-testid="icon-globe" />,
    Sparkles: () => <span data-testid="icon-sparkles" />,
    MapPin: () => <span data-testid="icon-map-pin" />,
    Calendar: () => <span data-testid="icon-calendar" />,
    DollarSign: () => <span data-testid="icon-dollar" />,
    Compass: () => <span data-testid="icon-compass" />,
    Map: () => <span data-testid="icon-map" />,
    Lightbulb: () => <span data-testid="icon-lightbulb" />,
    Luggage: () => <span data-testid="icon-luggage" />,
    RefreshCw: () => <span data-testid="icon-refresh" />,
    Award: () => <span data-testid="icon-award" />,
    ArrowRight: () => <span data-testid="icon-arrow-right" />,
  };
});

describe('Home landing page', () => {
  it('renders HeroSection content', () => {
    render(<Home />);
    expect(screen.getByText('Gemini AI Travel Planning')).toBeInTheDocument();
    expect(screen.getByText('Your Perfect Trip,')).toBeInTheDocument();
    expect(screen.getByText('Planned by Gemini AI')).toBeInTheDocument();
  });

  it('renders HowItWorks section', () => {
    render(<Home />);
    const howItWorksHeadings = screen.getAllByText('How It Works');
    expect(howItWorksHeadings.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Tell Us Your Preferences')).toBeInTheDocument();
  });

  it('renders FeatureGrid section', () => {
    render(<Home />);
    expect(screen.getByText('Everything You Need')).toBeInTheDocument();
    expect(screen.getByText('Gemini-Powered Planning')).toBeInTheDocument();
  });

  it('renders StatsSection section', () => {
    render(<Home />);
    expect(screen.getByText('Trips Planned')).toBeInTheDocument();
    expect(screen.getByText('Destinations')).toBeInTheDocument();
  });

  it('renders CTASection', () => {
    render(<Home />);
    expect(screen.getByText('Ready to Plan Your Next Adventure?')).toBeInTheDocument();
    expect(screen.getByText('Plan Your Trip Now')).toBeInTheDocument();
  });
});
