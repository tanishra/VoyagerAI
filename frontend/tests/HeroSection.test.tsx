import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import HeroSection from '@/components/HeroSection';

describe('HeroSection', () => {
  it('renders the Gemini badge', () => {
    render(<HeroSection />);
    expect(screen.getByText('Gemini AI Travel Planning')).toBeInTheDocument();
  });

  it('renders main heading', () => {
    render(<HeroSection />);
    expect(screen.getByText('Your Perfect Trip,')).toBeInTheDocument();
    expect(screen.getByText('Planned by Gemini AI')).toBeInTheDocument();
  });

  it('renders the description text', () => {
    render(<HeroSection />);
    expect(screen.getByText(/tell us your destination/i)).toBeInTheDocument();
  });

  it('renders CTA buttons', () => {
    render(<HeroSection />);
    const planBtn = screen.getByText('Plan Your Trip');
    expect(planBtn.closest('a')).toHaveAttribute('href', '/plan');
    const howBtn = screen.getByText('How It Works');
    expect(howBtn.closest('a')).toHaveAttribute('href', '/about');
  });

  it('renders trust indicators', () => {
    render(<HeroSection />);
    expect(screen.getByText('Gemini Generated')).toBeInTheDocument();
    expect(screen.getByText('Budget Tracking')).toBeInTheDocument();
    expect(screen.getByText('Day-by-Day Plans')).toBeInTheDocument();
  });
});
