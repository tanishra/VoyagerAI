import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';

// Mock next-intl — stable function references per namespace (avoids useCallback re-firing)
vi.mock('next-intl', () => {
  const cache: Record<string, (key: string) => string> = {};
  return {
    useTranslations: (namespace: string) => {
      if (!cache[namespace]) {
        cache[namespace] = (key: string) => `${namespace}.${key}`;
      }
      return cache[namespace];
    },
  };
});

// Mock framer-motion
vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <div {...props}>{children}</div>
    ),
  },
}));

// Mock next/link
vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: React.PropsWithChildren<{ href: string }>) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

// Mock child components to isolate CostsTab logic
vi.mock('@/components/admin/CostChart', () => ({
  CostChart: ({ data }: { data: { date: string; cost: number }[] }) => (
    <div data-testid="cost-chart" data-points={data.length}>{data.length} points</div>
  ),
}));

vi.mock('@/components/admin/SubagentCostBreakdown', () => ({
  SubagentCostBreakdown: ({ data }: { data: { name: string; cost: number }[] }) => (
    <div data-testid="subagent-breakdown" data-count={data.length}>{data.length} agents</div>
  ),
}));

vi.mock('@/components/admin/TopUsersTable', () => ({
  TopUsersTable: ({ data }: { data: { user_id: string; cost: number }[] }) => (
    <div data-testid="top-users" data-count={data.length}>{data.length} users</div>
  ),
}));

vi.mock('@/components/admin/TokenEfficiencyTable', () => ({
  TokenEfficiencyTable: ({ data }: { data: { thread_id: string }[] }) => (
    <div data-testid="token-efficiency" data-count={data.length}>{data.length} sessions</div>
  ),
}));

vi.mock('@/components/admin/FeedbackSummary', () => ({
  default: ({ data }: { data: { total_up: number; total_down: number; total_ratings: number } | null }) => (
    <div data-testid="feedback-summary" data-ratings={data?.total_ratings ?? 0}>
      {data ? `${data.total_up}up ${data.total_down}down` : 'no feedback'}
    </div>
  ),
}));

// Mock feedback-api
vi.mock('@/lib/feedback-api', () => ({
  getFeedbackAggregate: vi.fn(),
}));

// Mock fetch
const mockFetch = vi.fn();
global.fetch = mockFetch as unknown as typeof fetch;

// Mock window.open
const mockOpen = vi.fn();
global.window.open = mockOpen as unknown as typeof window.open;

// Import after mocks
import { CostsTab } from '@/components/admin/CostsTab';
import { getFeedbackAggregate } from '@/lib/feedback-api';

const mockStats = {
  total_cost: 0.1234,
  total_conversations: 42,
  avg_cost_per_conversation: 0.0029,
  total_input_tokens: 50000,
  total_output_tokens: 15000,
  per_day: [
    { date: '2025-01-01', cost: 0.05 },
    { date: '2025-01-02', cost: 0.07 },
  ],
  per_subagent: [
    { name: 'researcher', cost: 0.08, input_tokens: 30000, output_tokens: 8000 },
    { name: 'validator', cost: 0.04, input_tokens: 20000, output_tokens: 7000 },
  ],
  top_users: [
    { user_id: 'user123abc', cost: 0.05 },
  ],
  poor_efficiency_sessions: [
    { thread_id: 'thread456def', user_id: 'user123abc', efficiency_ratio: 75.5, cost: 0.03 },
  ],
};

const mockFeedback = {
  total_up: 15,
  total_down: 5,
  total_ratings: 20,
  satisfaction_ratio: 0.75,
  recent_comments: [
    { comment: 'Wrong prices in itinerary', thread_id: 'thread456def', created_at: 1700000000 },
    { comment: 'Bad restaurant recs', thread_id: 'thread789ghi', created_at: 1700000100 },
  ],
};

describe('CostsTab', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getFeedbackAggregate).mockResolvedValue(mockFeedback);
  });

  it('shows loading spinner while fetching data', () => {
    mockFetch.mockReturnValue(new Promise(() => {}));

    render(<CostsTab />);

    expect(document.querySelector('.animate-spin')).toBeInTheDocument();
  });

  it('shows error message when API returns 403', async () => {
    mockFetch.mockResolvedValueOnce({
      status: 403,
      ok: false,
    });

    render(<CostsTab />);

    await waitFor(() => {
      expect(screen.getByText('admin.loadError')).toBeInTheDocument();
    });
  });

  it('renders summary cards with stats data', async () => {
    mockFetch.mockResolvedValueOnce({
      status: 200,
      ok: true,
      json: async () => mockStats,
    });

    render(<CostsTab />);

    await waitFor(() => {
      expect(screen.getByText('$0.1234')).toBeInTheDocument();
      expect(screen.getByText('42')).toBeInTheDocument();
      expect(screen.getByText('$0.0029')).toBeInTheDocument();
    });
  });

  it('renders cost chart with per-day data', async () => {
    mockFetch.mockResolvedValueOnce({
      status: 200,
      ok: true,
      json: async () => mockStats,
    });

    render(<CostsTab />);

    await waitFor(() => {
      expect(screen.getByTestId('cost-chart')).toBeInTheDocument();
      expect(screen.getByTestId('cost-chart').getAttribute('data-points')).toBe('2');
    });
  });

  it('renders subagent breakdown with data', async () => {
    mockFetch.mockResolvedValueOnce({
      status: 200,
      ok: true,
      json: async () => mockStats,
    });

    render(<CostsTab />);

    await waitFor(() => {
      expect(screen.getByTestId('subagent-breakdown')).toBeInTheDocument();
      expect(screen.getByTestId('subagent-breakdown').getAttribute('data-count')).toBe('2');
    });
  });

  it('renders top users table with data', async () => {
    mockFetch.mockResolvedValueOnce({
      status: 200,
      ok: true,
      json: async () => mockStats,
    });

    render(<CostsTab />);

    await waitFor(() => {
      expect(screen.getByTestId('top-users')).toBeInTheDocument();
      expect(screen.getByTestId('top-users').getAttribute('data-count')).toBe('1');
    });
  });

  it('triggers CSV export on button click', async () => {
    mockFetch.mockResolvedValueOnce({
      status: 200,
      ok: true,
      json: async () => mockStats,
    });

    render(<CostsTab />);

    await waitFor(() => {
      expect(screen.getByText('admin.exportCsv')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('admin.exportCsv'));
    expect(mockOpen).toHaveBeenCalledWith(
      expect.stringContaining('/admin/costs/export'),
      '_blank'
    );
  });

  it('renders feedback summary with data', async () => {
    mockFetch.mockResolvedValueOnce({
      status: 200,
      ok: true,
      json: async () => mockStats,
    });

    render(<CostsTab />);

    await waitFor(() => {
      expect(screen.getByTestId('feedback-summary')).toBeInTheDocument();
      expect(screen.getByTestId('feedback-summary').getAttribute('data-ratings')).toBe('20');
    });
  });

  it('renders feedback summary with no data when feedback API fails', async () => {
    mockFetch.mockResolvedValueOnce({
      status: 200,
      ok: true,
      json: async () => mockStats,
    });
    vi.mocked(getFeedbackAggregate).mockRejectedValue(new Error('fail'));

    render(<CostsTab />);

    await waitFor(() => {
      expect(screen.getByTestId('feedback-summary')).toBeInTheDocument();
      expect(screen.getByTestId('feedback-summary').getAttribute('data-ratings')).toBe('0');
    });
  });

  it('switches period and refetches when period button clicked', async () => {
    mockFetch.mockResolvedValueOnce({
      status: 200,
      ok: true,
      json: async () => mockStats,
    });
    mockFetch.mockResolvedValueOnce({
      status: 200,
      ok: true,
      json: async () => ({ ...mockStats, total_conversations: 99 }),
    });

    render(<CostsTab />);

    await waitFor(() => {
      expect(screen.getByText('42')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('admin.periodDay'));

    await waitFor(() => {
      expect(screen.getByText('99')).toBeInTheDocument();
    });
  });
});
