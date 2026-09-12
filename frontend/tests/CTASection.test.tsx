import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import CTASection from '@/components/CTASection';

describe('CTASection', () => {
  it('renders heading', () => {
    render(<CTASection />);
    expect(screen.getByText('Where will you go next?')).toBeInTheDocument();
  });

  it('renders description', () => {
    render(<CTASection />);
    expect(screen.getByText(/A personalized itinerary/i)).toBeInTheDocument();
  });

  it('renders CTA button linking to /chat', () => {
    render(<CTASection />);
    const btn = screen.getByText('Plan Your Trip');
    expect(btn.closest('a')).toHaveAttribute('href', '/chat');
  });
});
