import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import Navbar from '@/components/Navbar';

vi.mock('next/navigation', () => ({
  usePathname: () => '/',
  useRouter: () => ({ push: vi.fn() }),
}));

describe('Navbar', () => {
  it('renders the VoyagerAI logo', () => {
    render(<Navbar />);
    expect(screen.getByText('VoyagerAI')).toBeInTheDocument();
  });

  it('renders desktop nav links', () => {
    render(<Navbar />);
    expect(screen.getByText('Home')).toBeInTheDocument();
    expect(screen.getByText('Chat')).toBeInTheDocument();
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
    expect(logo.closest('a')).toHaveAttribute('href', '/en');
  });
});
