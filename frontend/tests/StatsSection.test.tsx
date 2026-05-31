import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import StatsSection from '@/components/StatsSection';

describe('StatsSection', () => {
  it('renders all stat labels', () => {
    render(<StatsSection />);
    expect(screen.getByText('Trips Planned')).toBeInTheDocument();
    expect(screen.getByText('Destinations')).toBeInTheDocument();
    expect(screen.getByText('Gemini Accuracy')).toBeInTheDocument();
    expect(screen.getByText('Years Running')).toBeInTheDocument();
  });

  it('renders stat icons', () => {
    const { container } = render(<StatsSection />);
    const icons = container.querySelectorAll('svg');
    expect(icons.length).toBeGreaterThanOrEqual(4);
  });
});
