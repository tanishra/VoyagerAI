import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import Footer from '@/components/Footer';

describe('Footer', () => {
  it('renders VoyagerAI branding', () => {
    render(<Footer />);
    expect(screen.getByText('VoyagerAI')).toBeInTheDocument();
  });

  it('renders live clock', () => {
    render(<Footer />);
    const clock = document.querySelector('.tabular-nums');
    expect(clock).toBeInTheDocument();
  });
});
