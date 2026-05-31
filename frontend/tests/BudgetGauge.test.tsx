import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import BudgetGauge from '@/components/BudgetGauge';

describe('BudgetGauge', () => {
  it('renders SVG with aria-label showing percentage', () => {
    render(<BudgetGauge percent={65} status="within" />);
    const svg = screen.getByRole('img', { name: 'Budget usage at 65%' });
    expect(svg).toBeInTheDocument();
  });

  it('displays percentage text in center', () => {
    render(<BudgetGauge percent={42} status="over" />);
    expect(screen.getByText('42%')).toBeInTheDocument();
  });

  it('shows "used" label below percentage', () => {
    render(<BudgetGauge percent={80} status="under" />);
    expect(screen.getByText('used')).toBeInTheDocument();
  });

  it('caps percentage at 100', () => {
    render(<BudgetGauge percent={150} status="within" />);
    expect(screen.getByText('100%')).toBeInTheDocument();
  });

  it('applies correct color for within status (emerald)', () => {
    const { container } = render(<BudgetGauge percent={50} status="within" />);
    const textSpan = container.querySelector('.text-emerald-400');
    expect(textSpan).toBeTruthy();
  });

  it('applies correct color for over status (red)', () => {
    const { container } = render(<BudgetGauge percent={110} status="over" />);
    const textSpan = container.querySelector('.text-red-400');
    expect(textSpan).toBeTruthy();
  });

  it('applies correct color for under status (amber)', () => {
    const { container } = render(<BudgetGauge percent={30} status="under" />);
    const textSpan = container.querySelector('.text-amber-400');
    expect(textSpan).toBeTruthy();
  });

  it('renders with default size 120', () => {
    const { container } = render(<BudgetGauge percent={50} status="within" />);
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.style.width).toBe('120px');
    expect(wrapper.style.height).toBe('120px');
  });

  it('accepts custom size prop', () => {
    const { container } = render(<BudgetGauge percent={50} status="within" size={80} />);
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.style.width).toBe('80px');
    expect(wrapper.style.height).toBe('80px');
  });

  it('renders two circles (track + progress)', () => {
    const { container } = render(<BudgetGauge percent={75} status="within" />);
    const circles = container.querySelectorAll('circle');
    expect(circles.length).toBe(2);
  });

  it('shows 0% when percent is 0', () => {
    render(<BudgetGauge percent={0} status="within" />);
    expect(screen.getByText('0%')).toBeInTheDocument();
  });
});
