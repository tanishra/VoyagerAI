import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import SubagentTimeline from '@/components/SubagentTimeline';
import type { ToolCallEntry } from '@/lib/types';

// framer-motion and next-intl are mocked in tests/setup.ts

const makeToolCall = (overrides?: Partial<ToolCallEntry>): ToolCallEntry => ({
  run_id: 'r1',
  name: 'internet_search',
  status: 'done',
  started_at: 1000,
  ended_at: 2000,
  ...overrides,
});

describe('SubagentTimeline', () => {
  it('returns null when toolCalls is empty', () => {
    const { container } = render(<SubagentTimeline toolCalls={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders flat tool calls when no parent_run_id', () => {
    const toolCalls = [
      makeToolCall({ run_id: 'r1', name: 'internet_search', status: 'done' }),
      makeToolCall({ run_id: 'r2', name: 'calculator', status: 'running' }),
    ];
    render(<SubagentTimeline toolCalls={toolCalls} />);
    expect(screen.getByText('internet_search')).toBeInTheDocument();
    expect(screen.getByText('calculator')).toBeInTheDocument();
  });

  it('groups nested tool calls under parent subagent', () => {
    const toolCalls = [
      makeToolCall({ run_id: 'task-1', name: 'researcher', status: 'running' }),
      makeToolCall({ run_id: 'search-1', name: 'internet_search', status: 'done', parent_run_id: 'task-1' }),
    ];
    render(<SubagentTimeline toolCalls={toolCalls} />);
    // Parent subagent name should be visible
    expect(screen.getByText('researcher')).toBeInTheDocument();
    // Nested tool call should NOT be visible initially (collapsed by default)
    expect(screen.queryByText('internet_search')).not.toBeInTheDocument();
  });

  it('shows progress description under running subagent', () => {
    const toolCalls = [
      makeToolCall({ run_id: 'task-1', name: 'researcher', status: 'running' }),
    ];
    const progressMap = { 'task-1': 'Searching for hotels in Tokyo...' };
    render(<SubagentTimeline toolCalls={toolCalls} progressMap={progressMap} isStreaming={true} />);
    expect(screen.getByText('Searching for hotels in Tokyo...')).toBeInTheDocument();
  });

  it('truncates long progress descriptions with ellipsis', () => {
    const longDesc = 'A'.repeat(100);
    const toolCalls = [
      makeToolCall({ run_id: 'task-1', name: 'researcher', status: 'running' }),
    ];
    const progressMap = { 'task-1': longDesc };
    render(<SubagentTimeline toolCalls={toolCalls} progressMap={progressMap} isStreaming={true} />);
    const descEl = screen.getByText(/AAA\.\.\./);
    expect(descEl).toBeInTheDocument();
    // Should have title attribute for tooltip
    expect(descEl.closest('p')).toHaveAttribute('title', longDesc);
  });

  it('expand subagent reveals nested tool calls', () => {
    const toolCalls = [
      makeToolCall({ run_id: 'task-1', name: 'researcher', status: 'done' }),
      makeToolCall({ run_id: 'search-1', name: 'internet_search', status: 'done', parent_run_id: 'task-1' }),
    ];
    render(<SubagentTimeline toolCalls={toolCalls} />);
    // Initially collapsed
    expect(screen.queryByText('internet_search')).not.toBeInTheDocument();

    // Click the expand button
    const expandBtn = screen.getByRole('button', { name: 'Expand' });
    fireEvent.click(expandBtn);
    expect(screen.getByText('internet_search')).toBeInTheDocument();
  });

  it('shows status indicators correctly (running/done/error)', () => {
    const toolCalls = [
      makeToolCall({ run_id: 'r1', name: 'tool_a', status: 'running' }),
      makeToolCall({ run_id: 'r2', name: 'tool_b', status: 'done' }),
      makeToolCall({ run_id: 'r3', name: 'tool_c', status: 'error' }),
    ];
    render(<SubagentTimeline toolCalls={toolCalls} />);
    expect(screen.getByText('tool_a')).toBeInTheDocument();
    expect(screen.getByText('running…')).toBeInTheDocument();
    expect(screen.getByText('tool_b')).toBeInTheDocument();
    expect(screen.getByText('failed')).toBeInTheDocument();
    expect(screen.getByText('tool_c')).toBeInTheDocument();
  });
});
