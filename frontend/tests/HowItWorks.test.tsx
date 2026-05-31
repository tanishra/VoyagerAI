import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import HowItWorks from '@/components/HowItWorks';

describe('HowItWorks', () => {
  it('renders section title', () => {
    render(<HowItWorks />);
    expect(screen.getByText('How It Works')).toBeInTheDocument();
  });

  it('renders all step titles', () => {
    render(<HowItWorks />);
    expect(screen.getByText('Tell Us Your Preferences')).toBeInTheDocument();
    expect(screen.getByText('Gemini Generates Your Itinerary')).toBeInTheDocument();
    expect(screen.getByText('Explore & Customize')).toBeInTheDocument();
  });

  it('renders step numbers', () => {
    render(<HowItWorks />);
    expect(screen.getByText('Step 1')).toBeInTheDocument();
    expect(screen.getByText('Step 2')).toBeInTheDocument();
    expect(screen.getByText('Step 3')).toBeInTheDocument();
  });

  it('renders step descriptions', () => {
    render(<HowItWorks />);
    expect(screen.getByText(/enter your destination/i)).toBeInTheDocument();
    expect(screen.getByText(/complete day-by-day plan/i)).toBeInTheDocument();
  });
});
