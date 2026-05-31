import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import LoadingSkeleton from '@/components/LoadingSkeleton';

describe('LoadingSkeleton', () => {
  it('renders hero skeleton', () => {
    const { container } = render(<LoadingSkeleton />);
    const shimmerBlocks = container.querySelectorAll('.shimmer');
    expect(shimmerBlocks.length).toBeGreaterThan(5);
  });

  it('renders budget gauge skeleton circle', () => {
    const { container } = render(<LoadingSkeleton />);
    const circleSkeleton = container.querySelector('.rounded-full.shrink-0');
    expect(circleSkeleton).toBeInTheDocument();
  });

  it('renders 4 timeline day skeletons', () => {
    const { container } = render(<LoadingSkeleton />);
    // 1 budget summary grid + 4 day card grids = 5 total
    const allGrids = container.querySelectorAll('.grid.grid-cols-3');
    expect(allGrids.length).toBe(5);
    // 4 day card grids each have a rounded-xl shimmer child
    const dayGrids = container.querySelectorAll('.grid.grid-cols-3.gap-2');
    expect(dayGrids.length).toBe(4);
  });

  it('has staggered animation delays for day skeletons', () => {
    const { container } = render(<LoadingSkeleton />);
    const dayCards = container.querySelectorAll('[class*="flex-1"]');
    expect(dayCards.length).toBeGreaterThanOrEqual(4);
  });

  it('renders within a max-w-4xl container', () => {
    const { container } = render(<LoadingSkeleton />);
    const outerDiv = container.firstChild as HTMLElement;
    expect(outerDiv.className).toContain('max-w-4xl');
  });

  it('renders transport and accommodation shimmer rows in day cards', () => {
    const { container } = render(<LoadingSkeleton />);
    const flexRows = container.querySelectorAll('.flex.gap-4.pt-2');
    expect(flexRows.length).toBe(4);
  });

  it('renders card header shimmer elements', () => {
    const { container } = render(<LoadingSkeleton />);
    const cardHeaders = container.querySelectorAll('[class*="pb-3"]');
    expect(cardHeaders.length).toBe(4);
  });
});
