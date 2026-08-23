import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { ChevronLeft, ChevronRight, RotateCcw } from 'lucide-react';
import type { BranchInfo } from '@/lib/types';

function BranchNavigation({
  branches,
  activeBranchIndex,
  onSwitchBranch,
  onRegenerate,
  regenerating,
}: {
  branches: BranchInfo[];
  activeBranchIndex: number;
  onSwitchBranch: (checkpointId: string, index: number) => void;
  onRegenerate: () => void;
  regenerating: boolean;
}) {
  return (
    <div className="flex items-center gap-1">
      <button
        onClick={onRegenerate}
        disabled={regenerating}
        aria-label={regenerating ? 'Regenerating...' : 'Regenerate'}
      >
        <RotateCcw className="w-3.5 h-3.5" />
      </button>
      {branches.length > 1 && (
        <div className="flex items-center gap-0.5" data-testid="branch-nav">
          <button
            onClick={() => {
              const prevIdx = activeBranchIndex > 0 ? activeBranchIndex - 1 : branches.length - 1;
              onSwitchBranch(branches[prevIdx].checkpoint_id, prevIdx);
            }}
            aria-label="Previous branch"
            data-testid="prev-branch"
          >
            <ChevronLeft className="w-3.5 h-3.5" />
          </button>
          <span data-testid="branch-count">
            {activeBranchIndex + 1}/{branches.length}
          </span>
          <button
            onClick={() => {
              const nextIdx = activeBranchIndex < branches.length - 1 ? activeBranchIndex + 1 : 0;
              onSwitchBranch(branches[nextIdx].checkpoint_id, nextIdx);
            }}
            aria-label="Next branch"
            data-testid="next-branch"
          >
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}

describe('BranchNavigation', () => {
  it('renders branch navigation when branches > 1', () => {
    const branches: BranchInfo[] = [
      { checkpoint_id: 'b1', is_current: true },
      { checkpoint_id: 'b2', is_current: false },
      { checkpoint_id: 'b3', is_current: false },
    ];
    render(
      <BranchNavigation
        branches={branches}
        activeBranchIndex={0}
        onSwitchBranch={() => {}}
        onRegenerate={() => {}}
        regenerating={false}
      />,
    );
    expect(screen.getByTestId('branch-nav')).toBeDefined();
  });

  it('does not render branch navigation when branches <= 1', () => {
    render(
      <BranchNavigation
        branches={[{ checkpoint_id: 'b1', is_current: true }]}
        activeBranchIndex={0}
        onSwitchBranch={() => {}}
        onRegenerate={() => {}}
        regenerating={false}
      />,
    );
    expect(screen.queryByTestId('branch-nav')).toBeNull();
  });

  it('displays correct branch count (2/3)', () => {
    const branches: BranchInfo[] = [
      { checkpoint_id: 'b1', is_current: false },
      { checkpoint_id: 'b2', is_current: true },
      { checkpoint_id: 'b3', is_current: false },
    ];
    render(
      <BranchNavigation
        branches={branches}
        activeBranchIndex={1}
        onSwitchBranch={() => {}}
        onRegenerate={() => {}}
        regenerating={false}
      />,
    );
    expect(screen.getByTestId('branch-count').textContent).toBe('2/3');
  });

  it('calls onSwitchBranch with correct index when previous is clicked', () => {
    const branches: BranchInfo[] = [
      { checkpoint_id: 'b1', is_current: false },
      { checkpoint_id: 'b2', is_current: true },
    ];
    const onSwitch = vi.fn();
    render(
      <BranchNavigation
        branches={branches}
        activeBranchIndex={1}
        onSwitchBranch={onSwitch}
        onRegenerate={() => {}}
        regenerating={false}
      />,
    );
    screen.getByTestId('prev-branch').click();
    expect(onSwitch).toHaveBeenCalledWith('b1', 0);
  });

  it('calls onSwitchBranch with correct index when next is clicked', () => {
    const branches: BranchInfo[] = [
      { checkpoint_id: 'b1', is_current: true },
      { checkpoint_id: 'b2', is_current: false },
    ];
    const onSwitch = vi.fn();
    render(
      <BranchNavigation
        branches={branches}
        activeBranchIndex={0}
        onSwitchBranch={onSwitch}
        onRegenerate={() => {}}
        regenerating={false}
      />,
    );
    screen.getByTestId('next-branch').click();
    expect(onSwitch).toHaveBeenCalledWith('b2', 1);
  });

  it('wraps around to last branch when previous is clicked at index 0', () => {
    const branches: BranchInfo[] = [
      { checkpoint_id: 'b1', is_current: true },
      { checkpoint_id: 'b2', is_current: false },
      { checkpoint_id: 'b3', is_current: false },
    ];
    const onSwitch = vi.fn();
    render(
      <BranchNavigation
        branches={branches}
        activeBranchIndex={0}
        onSwitchBranch={onSwitch}
        onRegenerate={() => {}}
        regenerating={false}
      />,
    );
    screen.getByTestId('prev-branch').click();
    expect(onSwitch).toHaveBeenCalledWith('b3', 2);
  });

  it('disables regenerate button when regenerating', () => {
    render(
      <BranchNavigation
        branches={[]}
        activeBranchIndex={0}
        onSwitchBranch={() => {}}
        onRegenerate={() => {}}
        regenerating={true}
      />,
    );
    const regenBtn = screen.getByLabelText('Regenerating...');
    expect(regenBtn.hasAttribute('disabled')).toBe(true);
  });
});
