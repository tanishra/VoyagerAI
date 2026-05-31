import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import WarningsSection from '@/components/WarningsSection';

describe('WarningsSection', () => {
  it('renders travel warnings count', () => {
    render(<WarningsSection warnings={['Watch out for pickpockets']} packingEssentials={[]} />);
    expect(screen.getByText(/Travel Warnings/)).toBeInTheDocument();
    expect(screen.getByText('(1)')).toBeInTheDocument();
  });

  it('renders warning text', () => {
    render(<WarningsSection warnings={['Watch out for pickpockets', 'Avoid drinking tap water']} packingEssentials={[]} />);
    expect(screen.getByText('Watch out for pickpockets')).toBeInTheDocument();
    expect(screen.getByText('Avoid drinking tap water')).toBeInTheDocument();
  });

  it('renders packing essentials count', () => {
    render(<WarningsSection warnings={[]} packingEssentials={['Sunscreen', 'Umbrella']} />);
    expect(screen.getByText('Packing Essentials')).toBeInTheDocument();
    expect(screen.getByText('(2)')).toBeInTheDocument();
  });

  it('renders packing essential items as badges', () => {
    render(<WarningsSection warnings={[]} packingEssentials={['Sunscreen', 'Mosquito repellent', 'Comfortable shoes']} />);
    expect(screen.getByText('Sunscreen')).toBeInTheDocument();
    expect(screen.getByText('Mosquito repellent')).toBeInTheDocument();
    expect(screen.getByText('Comfortable shoes')).toBeInTheDocument();
  });

  it('returns null when both arrays are empty', () => {
    const { container } = render(<WarningsSection warnings={[]} packingEssentials={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it('toggles warnings section on click', () => {
    render(<WarningsSection warnings={['Warning 1', 'Warning 2']} packingEssentials={[]} />);
    expect(screen.getByText('Warning 1')).toBeInTheDocument();
    fireEvent.click(screen.getByText(/Travel Warnings/));
    expect(screen.queryByText('Warning 1')).not.toBeInTheDocument();
    fireEvent.click(screen.getByText(/Travel Warnings/));
    expect(screen.getByText('Warning 1')).toBeInTheDocument();
  });

  it('toggles packing essentials section on click', () => {
    render(<WarningsSection warnings={[]} packingEssentials={['Hat', 'Sunglasses']} />);
    expect(screen.getByText('Hat')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Packing Essentials'));
    expect(screen.queryByText('Hat')).not.toBeInTheDocument();
    fireEvent.click(screen.getByText('Packing Essentials'));
    expect(screen.getByText('Hat')).toBeInTheDocument();
  });

  it('shows chevron icon in warnings header', () => {
    const { container } = render(<WarningsSection warnings={['Test']} packingEssentials={[]} />);
    const chevron = container.querySelector('.lucide-chevron-down');
    expect(chevron).toBeInTheDocument();
  });

  it('shows alert icon wrapper in warnings header', () => {
    const { container } = render(<WarningsSection warnings={['Test']} packingEssentials={[]} />);
    const iconWrapper = container.querySelector('.bg-amber-500\\/10');
    expect(iconWrapper).toBeTruthy();
  });

  it('shows luggage icon wrapper in packing header', () => {
    const { container } = render(<WarningsSection warnings={[]} packingEssentials={['Sunscreen']} />);
    const iconWrapper = container.querySelector('.bg-cyan-500\\/10');
    expect(iconWrapper).toBeTruthy();
  });

  it('handles long warning lists', () => {
    const warnings = Array.from({ length: 10 }, (_, i) => `Warning ${i + 1}`);
    render(<WarningsSection warnings={warnings} packingEssentials={[]} />);
    expect(screen.getByText('Warning 10')).toBeInTheDocument();
  });
});
