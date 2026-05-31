import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import TimelineDay from '@/components/TimelineDay';
import type { DayPlan } from '@/lib/types';

const mockDay: DayPlan = {
  day: 1,
  theme: 'Explore the City',
  morning: { activity: 'Visit Shibuya', location: 'Shibuya', cost_usd: 20, duration: '3h' },
  afternoon: { activity: 'Senso-ji Temple', location: 'Asakusa', cost_usd: 10, duration: '2h' },
  evening: { activity: 'Ramen Dinner', location: 'Shinjuku', cost_usd: 30, duration: '1.5h' },
  transport: 'Train pass - $15',
  accommodation: 'Hotel Shinjuku - $120/night',
  daily_cost_usd: 195,
  tips: ['Book train pass in advance', 'Carry cash for small shops'],
};

const defaultProps = {
  day: mockDay,
  index: 0,
  replanLoading: false,
  isLast: false,
  onReplan: vi.fn(),
};

describe('TimelineDay', () => {
  it('renders day number and theme', () => {
    render(<TimelineDay {...defaultProps} />);
    expect(screen.getByText('Day 1')).toBeInTheDocument();
    expect(screen.getByText('Explore the City')).toBeInTheDocument();
  });

  it('shows daily cost badge', () => {
    render(<TimelineDay {...defaultProps} />);
    expect(screen.getByText('195')).toBeInTheDocument();
  });

  it('shows morning time slot activity', () => {
    render(<TimelineDay {...defaultProps} />);
    expect(screen.getByText('Visit Shibuya')).toBeInTheDocument();
    expect(screen.getByText('Morning')).toBeInTheDocument();
  });

  it('shows afternoon time slot activity', () => {
    render(<TimelineDay {...defaultProps} />);
    expect(screen.getByText('Senso-ji Temple')).toBeInTheDocument();
    expect(screen.getByText('Afternoon')).toBeInTheDocument();
  });

  it('shows evening time slot activity', () => {
    render(<TimelineDay {...defaultProps} />);
    expect(screen.getByText('Ramen Dinner')).toBeInTheDocument();
    expect(screen.getByText('Evening')).toBeInTheDocument();
  });

  it('shows time slot locations', () => {
    render(<TimelineDay {...defaultProps} />);
    expect(screen.getByText('Shibuya')).toBeInTheDocument();
    expect(screen.getByText('Asakusa')).toBeInTheDocument();
    expect(screen.getByText('Shinjuku')).toBeInTheDocument();
  });

  it('shows time slot durations', () => {
    render(<TimelineDay {...defaultProps} />);
    expect(screen.getByText('3h')).toBeInTheDocument();
    expect(screen.getByText('2h')).toBeInTheDocument();
    expect(screen.getByText('1.5h')).toBeInTheDocument();
  });

  it('shows transport info', () => {
    render(<TimelineDay {...defaultProps} />);
    expect(screen.getByText('Train pass - $15')).toBeInTheDocument();
  });

  it('shows accommodation info', () => {
    render(<TimelineDay {...defaultProps} />);
    expect(screen.getByText('Hotel Shinjuku - $120/night')).toBeInTheDocument();
  });

  it('shows tips section', () => {
    render(<TimelineDay {...defaultProps} />);
    expect(screen.getByText('Tips')).toBeInTheDocument();
    expect(screen.getByText('Book train pass in advance')).toBeInTheDocument();
    expect(screen.getByText('Carry cash for small shops')).toBeInTheDocument();
  });

  it('shows timeline connector with day number', () => {
    render(<TimelineDay {...defaultProps} />);
    expect(screen.getByText('1')).toBeInTheDocument();
  });

  it('has collapse/expand button', () => {
    render(<TimelineDay {...defaultProps} />);
    const btn = screen.getByLabelText('Collapse day');
    expect(btn).toBeInTheDocument();
  });

  it('toggles expansion when chevron is clicked', () => {
    render(<TimelineDay {...defaultProps} />);
    const btn = screen.getByLabelText('Collapse day');
    fireEvent.click(btn);
    expect(screen.getByLabelText('Expand day')).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText('Expand day'));
    expect(screen.getByLabelText('Collapse day')).toBeInTheDocument();
  });

  it('shows replan button', () => {
    render(<TimelineDay {...defaultProps} />);
    expect(screen.getByText('Replan This Day')).toBeInTheDocument();
  });

  it('opens replan form when clicked', () => {
    render(<TimelineDay {...defaultProps} />);
    fireEvent.click(screen.getByText('Replan This Day'));
    expect(screen.getByLabelText('Reason to replan day 1')).toBeInTheDocument();
    expect(screen.getByText('Replan')).toBeInTheDocument();
    expect(screen.getByText('Cancel')).toBeInTheDocument();
  });

  it('calls onReplan with day number and reason', () => {
    const onReplan = vi.fn();
    render(<TimelineDay {...defaultProps} onReplan={onReplan} />);
    fireEvent.click(screen.getByText('Replan This Day'));
    const textarea = screen.getByLabelText('Reason to replan day 1');
    fireEvent.change(textarea, { target: { value: 'Too crowded' } });
    fireEvent.click(screen.getByText('Replan'));
    expect(onReplan).toHaveBeenCalledWith(1, 'Too crowded');
  });

  it('closes replan form after submission', () => {
    const onReplan = vi.fn();
    render(<TimelineDay {...defaultProps} onReplan={onReplan} />);
    fireEvent.click(screen.getByText('Replan This Day'));
    fireEvent.change(screen.getByLabelText('Reason to replan day 1'), { target: { value: 'Change' } });
    fireEvent.click(screen.getByText('Replan'));
    expect(screen.queryByText('Reason to replan day 1')).not.toBeInTheDocument();
  });

  it('closes replan form on Escape key', () => {
    render(<TimelineDay {...defaultProps} />);
    fireEvent.click(screen.getByText('Replan This Day'));
    const textarea = screen.getByLabelText('Reason to replan day 1');
    fireEvent.keyDown(textarea, { key: 'Escape' });
    expect(screen.queryByLabelText('Reason to replan day 1')).not.toBeInTheDocument();
  });

  it('closes replan form on Cancel', () => {
    render(<TimelineDay {...defaultProps} />);
    fireEvent.click(screen.getByText('Replan This Day'));
    fireEvent.click(screen.getByText('Cancel'));
    expect(screen.queryByLabelText('Reason to replan day 1')).not.toBeInTheDocument();
  });

  it('disables replan button when reason is empty', () => {
    render(<TimelineDay {...defaultProps} />);
    fireEvent.click(screen.getByText('Replan This Day'));
    const replanBtn = screen.getByText('Replan');
    expect(replanBtn.closest('button')).toBeDisabled();
  });

  it('shows loading state on replan button', () => {
    render(<TimelineDay {...defaultProps} replanLoading={true} />);
    fireEvent.click(screen.getByText('Replan This Day'));
    const replanBtn = screen.getByText('Replanning…');
    expect(replanBtn.closest('button')).toBeDisabled();
  });

  it('does not render connector line when isLast is true', () => {
    const { container } = render(<TimelineDay {...defaultProps} isLast={true} />);
    const gradients = container.querySelectorAll('[class*="bg-gradient-to-b"]');
    const connectorLine = Array.from(gradients).find(el =>
      el.className.includes('sky-500/40') || el.className.includes('to-transparent')
    );
    expect(connectorLine).toBeFalsy();
  });

  it('renders all time slot cost values', () => {
    render(<TimelineDay {...defaultProps} />);
    expect(screen.getByText('20')).toBeInTheDocument();
    expect(screen.getByText('10')).toBeInTheDocument();
    expect(screen.getByText('30')).toBeInTheDocument();
  });
});
