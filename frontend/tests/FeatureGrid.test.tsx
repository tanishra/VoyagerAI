import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import FeatureGrid from '@/components/FeatureGrid';

describe('FeatureGrid', () => {
  it('renders section title', () => {
    render(<FeatureGrid />);
    expect(screen.getByText('Everything You Need')).toBeInTheDocument();
  });

  it('renders all feature titles', () => {
    render(<FeatureGrid />);
    expect(screen.getByText('Gemini-Powered Planning')).toBeInTheDocument();
    expect(screen.getByText('Budget Tracking')).toBeInTheDocument();
    expect(screen.getByText('Day-by-Day Plans')).toBeInTheDocument();
    expect(screen.getByText('Local Tips')).toBeInTheDocument();
    expect(screen.getByText('Packing Essentials')).toBeInTheDocument();
    expect(screen.getByText('Replan Any Day')).toBeInTheDocument();
  });

  it('renders feature descriptions', () => {
    render(<FeatureGrid />);
    expect(screen.getByText(/Gemini generates/i)).toBeInTheDocument();
    expect(screen.getByText(/real-time budget gauge/i)).toBeInTheDocument();
  });
});
