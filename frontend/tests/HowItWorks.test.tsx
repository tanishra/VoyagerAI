import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import HowItWorks from '@/components/HowItWorks';

describe('HowItWorks', () => {
  it('renders section heading', () => {
    render(<HowItWorks />);
    expect(screen.getByText('Three Steps to Your Perfect Trip')).toBeInTheDocument();
  });

  it('renders pill badge', () => {
    render(<HowItWorks />);
    expect(screen.getByText('How it works')).toBeInTheDocument();
  });

  it('renders all step titles', () => {
    render(<HowItWorks />);
    expect(screen.getByText('Tell Us Your Preferences')).toBeInTheDocument();
    expect(screen.getByText('Gemini Generates Your Itinerary')).toBeInTheDocument();
    expect(screen.getByText('Explore & Customize')).toBeInTheDocument();
  });

  it('renders step numbers 01, 02, 03', () => {
    render(<HowItWorks />);
    expect(screen.getByText('01')).toBeInTheDocument();
    expect(screen.getByText('02')).toBeInTheDocument();
    expect(screen.getByText('03')).toBeInTheDocument();
  });

  it('renders step descriptions', () => {
    render(<HowItWorks />);
    expect(screen.getByText(/enter your destination/i)).toBeInTheDocument();
    expect(screen.getByText(/complete day-by-day plan/i)).toBeInTheDocument();
  });
});
