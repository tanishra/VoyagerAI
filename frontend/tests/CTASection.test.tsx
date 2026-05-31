import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import CTASection from '@/components/CTASection';

describe('CTASection', () => {
  it('renders heading', () => {
    render(<CTASection />);
    expect(screen.getByText('Ready to Plan Your Next Adventure?')).toBeInTheDocument();
  });

  it('renders description', () => {
    render(<CTASection />);
    expect(screen.getByText(/completely free/i)).toBeInTheDocument();
  });

  it('renders CTA button linking to /plan', () => {
    render(<CTASection />);
    const btn = screen.getByText('Plan Your Trip Now');
    expect(btn.closest('a')).toHaveAttribute('href', '/plan');
  });
});
