import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import CopyButton from '@/components/CopyButton';

const mockWriteText = vi.fn();

beforeEach(() => {
  vi.useFakeTimers();
  mockWriteText.mockResolvedValue(undefined);
  Object.assign(navigator, {
    clipboard: { writeText: mockWriteText },
  });
});

afterEach(() => {
  vi.useRealTimers();
  mockWriteText.mockReset();
});

describe('CopyButton', () => {
  it('renders a button with Copy icon', () => {
    render(<CopyButton content="hello" />);
    const btn = screen.getByRole('button');
    expect(btn).toBeInTheDocument();
    expect(btn).toHaveAttribute('aria-label', 'Copy');
  });

  it('click calls navigator.clipboard.writeText with the content', () => {
    render(<CopyButton content="hello world" />);
    fireEvent.click(screen.getByRole('button'));
    expect(mockWriteText).toHaveBeenCalledWith('hello world');
  });

  it('shows Check icon after click then reverts to Copy after 2 seconds', () => {
    render(<CopyButton content="test" />);
    const btn = screen.getByRole('button');
    fireEvent.click(btn);
    expect(btn).toHaveAttribute('aria-label', 'Copy');
    const checkIcon = btn.querySelector('.text-emerald-600');
    expect(checkIcon).toBeInTheDocument();
    act(() => {
      vi.advanceTimersByTime(2000);
    });
    const checkAfter = btn.querySelector('.text-emerald-600');
    expect(checkAfter).not.toBeInTheDocument();
  });

  it('accepts custom className', () => {
    render(<CopyButton content="x" className="custom-class" />);
    const btn = screen.getByRole('button');
    expect(btn.className).toContain('custom-class');
  });

  it('accepts custom label for aria-label', () => {
    render(<CopyButton content="x" label="Copy itinerary" />);
    const btn = screen.getByRole('button');
    expect(btn).toHaveAttribute('aria-label', 'Copy itinerary');
    expect(btn).toHaveAttribute('title', 'Copy itinerary');
  });

  it('works with empty string content', () => {
    render(<CopyButton content="" />);
    fireEvent.click(screen.getByRole('button'));
    expect(mockWriteText).toHaveBeenCalledWith('');
  });

  it('works with multiline content', () => {
    const multiline = 'line1\nline2\nline3';
    render(<CopyButton content={multiline} />);
    fireEvent.click(screen.getByRole('button'));
    expect(mockWriteText).toHaveBeenCalledWith(multiline);
  });

  it('works with special characters (emoji, unicode)', () => {
    const special = '📍 Tokyo — $1,200 🎒';
    render(<CopyButton content={special} />);
    fireEvent.click(screen.getByRole('button'));
    expect(mockWriteText).toHaveBeenCalledWith(special);
  });
});
