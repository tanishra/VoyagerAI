import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import Navbar from '@/components/Navbar';

describe('Navbar', () => {
  it('renders the VoyagerAI logo', () => {
    render(<Navbar />);
    expect(screen.getByText('VoyagerAI')).toBeInTheDocument();
  });

  it('renders desktop nav links', () => {
    render(<Navbar />);
    expect(screen.getByText('Home')).toBeInTheDocument();
    expect(screen.getByText('Plan Trip')).toBeInTheDocument();
    expect(screen.getByText('About')).toBeInTheDocument();
    expect(screen.getByText('FAQ')).toBeInTheDocument();
  });

  it('renders mobile menu button', () => {
    render(<Navbar />);
    expect(screen.getByLabelText('Open menu')).toBeInTheDocument();
  });

  it('has correct href for logo link', () => {
    render(<Navbar />);
    const logo = screen.getByText('VoyagerAI');
    expect(logo.closest('a')).toHaveAttribute('href', '/');
  });
});
