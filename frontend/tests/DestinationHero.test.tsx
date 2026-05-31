import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import DestinationHero from '@/components/DestinationHero';

describe('DestinationHero', () => {
  it('renders destination name', () => {
    render(<DestinationHero destination="Tokyo" totalDays={7} />);
    expect(screen.getByText('Tokyo')).toBeInTheDocument();
  });

  it('shows day count with plural', () => {
    render(<DestinationHero destination="Paris" totalDays={5} />);
    expect(screen.getByText('5 days')).toBeInTheDocument();
  });

  it('shows "day" (singular) for 1 day', () => {
    render(<DestinationHero destination="Osaka" totalDays={1} />);
    expect(screen.getByText('1 day')).toBeInTheDocument();
  });

  it('shows AI-Generated Itinerary label', () => {
    render(<DestinationHero destination="Bali" totalDays={3} />);
    expect(screen.getByText('AI-Generated Itinerary')).toBeInTheDocument();
  });

  it('renders plane icon (svg with lucide-plane class)', () => {
    const { container } = render(<DestinationHero destination="Rome" totalDays={4} />);
    const planeIcon = container.querySelector('.lucide-plane');
    expect(planeIcon).toBeInTheDocument();
  });

  it('renders calendar icon', () => {
    const { container } = render(<DestinationHero destination="Rome" totalDays={4} />);
    const calendarIcon = container.querySelector('.lucide-calendar');
    expect(calendarIcon).toBeInTheDocument();
  });

  it('renders map pin icon', () => {
    const { container } = render(<DestinationHero destination="Rome" totalDays={4} />);
    const mapPinIcon = container.querySelector('.lucide-map-pin');
    expect(mapPinIcon).toBeInTheDocument();
  });

  it('has decorative dots', () => {
    const { container } = render(<DestinationHero destination="Tokyo" totalDays={5} />);
    const dots = container.querySelectorAll('.rounded-full.bg-sky-400');
    expect(dots.length).toBeGreaterThanOrEqual(3);
  });

  it('renders with glassmorphism card border', () => {
    const { container } = render(<DestinationHero destination="Sydney" totalDays={10} />);
    const card = container.firstChild as HTMLElement;
    expect(card.className).toContain('border-white/10');
  });

  it('has gradient background divs', () => {
    const { container } = render(<DestinationHero destination="London" totalDays={6} />);
    const gradientDivs = container.querySelectorAll('[class*="bg-gradient"]');
    expect(gradientDivs.length).toBeGreaterThanOrEqual(1);
  });

  it('renders without crashing for empty destination', () => {
    const { container } = render(<DestinationHero destination="" totalDays={0} />);
    expect(container.firstChild).toBeInTheDocument();
  });
});
