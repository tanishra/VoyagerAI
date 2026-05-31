import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import FaqSection from '@/components/FaqSection';

describe('FaqSection', () => {
  it('renders search input', () => {
    render(<FaqSection />);
    expect(screen.getByPlaceholderText('Search FAQs...')).toBeInTheDocument();
  });

  it('renders all FAQ questions', () => {
    render(<FaqSection />);
    expect(screen.getByText('How does Gemini generate my itinerary?')).toBeInTheDocument();
    expect(screen.getByText('Is it really free?')).toBeInTheDocument();
    expect(screen.getByText("Can I customize the itinerary after it's generated?")).toBeInTheDocument();
    expect(screen.getByText('How accurate is the budget tracking?')).toBeInTheDocument();
    expect(screen.getByText('What destinations are supported?')).toBeInTheDocument();
    expect(screen.getByText('How long does it take to generate a plan?')).toBeInTheDocument();
    expect(screen.getByText('Can I save or share my itinerary?')).toBeInTheDocument();
    expect(screen.getByText('What about dietary restrictions and accessibility?')).toBeInTheDocument();
  });

  it('filters FAQs when searching', () => {
    render(<FaqSection />);
    const searchInput = screen.getByPlaceholderText('Search FAQs...');
    fireEvent.change(searchInput, { target: { value: 'budget' } });
    expect(screen.getByText('How accurate is the budget tracking?')).toBeInTheDocument();
    expect(screen.queryByText('What destinations are supported?')).not.toBeInTheDocument();
  });

  it('shows empty state when no matches found', () => {
    render(<FaqSection />);
    const searchInput = screen.getByPlaceholderText('Search FAQs...');
    fireEvent.change(searchInput, { target: { value: 'xyznonexistent' } });
    expect(screen.getByText(/no results found/i)).toBeInTheDocument();
  });
});
