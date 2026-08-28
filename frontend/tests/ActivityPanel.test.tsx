import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ActivityPanel from '@/components/ActivityPanel';
import type { ActivityData } from '@/lib/types';

// framer-motion and next-intl are mocked in tests/setup.ts

const makeActivity = (overrides?: Partial<ActivityData>): ActivityData => ({
  thinking: [],
  tool_calls: [],
  usage: [],
  total_input_tokens: 0,
  total_output_tokens: 0,
  ...overrides,
});

describe('ActivityPanel', () => {
  it('renders null when no activity and not streaming', () => {
    const { container } = render(
      <ActivityPanel activity={null} activeWorkers={[]} isStreaming={false} hasText={false} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders collapsed summary when not streaming and has activity', () => {
    const activity = makeActivity({
      tool_calls: [
        { run_id: 'r1', name: 'researcher', status: 'done', started_at: 1000, ended_at: 2000 },
      ],
      total_input_tokens: 500,
      total_output_tokens: 300,
    });
    render(
      <ActivityPanel activity={activity} activeWorkers={[]} isStreaming={false} hasText={true} />,
    );
    const btn = screen.getByRole('button');
    expect(btn).toBeInTheDocument();
  });

  it('auto-expands when streaming and no text yet', () => {
    const activity = makeActivity({
      tool_calls: [
        { run_id: 'r1', name: 'internet_search', status: 'done', started_at: 1000, ended_at: 2000 },
      ],
    });
    render(
      <ActivityPanel activity={activity} activeWorkers={['researcher']} isStreaming={true} hasText={false} />,
    );
    expect(screen.getByText('internet_search')).toBeInTheDocument();
  });

  it('auto-collapses when text starts streaming', () => {
    const activity = makeActivity({
      tool_calls: [
        { run_id: 'r1', name: 'internet_search', status: 'done', started_at: 1000, ended_at: 2000 },
      ],
    });
    const { rerender } = render(
      <ActivityPanel activity={activity} activeWorkers={[]} isStreaming={true} hasText={false} />,
    );
    expect(screen.getByText('internet_search')).toBeInTheDocument();

    rerender(
      <ActivityPanel activity={activity} activeWorkers={[]} isStreaming={true} hasText={true} />,
    );
    expect(screen.queryByText('internet_search')).not.toBeInTheDocument();
  });

  it('manual expand/collapse works via clicking the header button', () => {
    const activity = makeActivity({
      tool_calls: [
        { run_id: 'r1', name: 'internet_search', status: 'done', started_at: 1000, ended_at: 2000 },
      ],
    });
    render(
      <ActivityPanel activity={activity} activeWorkers={[]} isStreaming={false} hasText={true} />,
    );
    expect(screen.queryByText('internet_search')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button'));
    expect(screen.getByText('internet_search')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button'));
    expect(screen.queryByText('internet_search')).not.toBeInTheDocument();
  });

  it('shows thinking block header when expanded', () => {
    const activity = makeActivity({
      thinking: [{ text: 'Reasoning step 1' }, { text: 'Reasoning step 2' }],
    });
    render(
      <ActivityPanel activity={activity} activeWorkers={[]} isStreaming={true} hasText={false} />,
    );
    expect(screen.getByText(/Thinking/)).toBeInTheDocument();
  });

  it('shows tool calls when expanded', () => {
    const activity = makeActivity({
      tool_calls: [
        { run_id: 'r1', name: 'internet_search', status: 'done', started_at: 1000, ended_at: 2000 },
      ],
    });
    render(
      <ActivityPanel activity={activity} activeWorkers={[]} isStreaming={true} hasText={false} />,
    );
    expect(screen.getByText('internet_search')).toBeInTheDocument();
  });

  it('shows token usage summary when expanded', () => {
    const activity = makeActivity({
      tool_calls: [
        { run_id: 'r1', name: 'internet_search', status: 'done', started_at: 1000, ended_at: 2000 },
      ],
      total_input_tokens: 1200,
      total_output_tokens: 800,
    });
    render(
      <ActivityPanel activity={activity} activeWorkers={[]} isStreaming={true} hasText={false} />,
    );
    expect(screen.getByText(/1200/)).toBeInTheDocument();
    expect(screen.getByText(/800/)).toBeInTheDocument();
  });
});
