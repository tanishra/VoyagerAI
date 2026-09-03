import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';

// Mock next-intl
vi.mock('next-intl', () => ({
  useTranslations: (namespace: string) => (key: string) => `${namespace}.${key}`,
}));

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

// Mock fetch
const mockFetch = vi.fn();
global.fetch = mockFetch as unknown as typeof fetch;

// Mock window.open
const mockOpen = vi.fn();
global.window.open = mockOpen as unknown as typeof window.open;

// Import after mocks
import AdminCostsPage from '@/app/[locale]/admin/costs/page';

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

describe('AdminCostsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows access denied when API returns 403', async () => {
    mockFetch.mockResolvedValueOnce({
      status: 403,
      ok: false,
    });
    mockFetch.mockResolvedValueOnce({
      status: 403,
      ok: false,
    });

    render(<AdminCostsPage />);

    await waitFor(() => {
      expect(screen.getByText('admin.accessDenied')).toBeDefined();
    });
  });

  it('renders summary cards with stats data', async () => {
    mockFetch.mockResolvedValueOnce({
      status: 200,
      ok: true,
      json: async () => mockStats,
    });
    mockFetch.mockResolvedValueOnce({
      status: 200,
      ok: true,
      json: async () => mockFeedback,
    });

    render(<AdminCostsPage />);

    await waitFor(() => {
      expect(screen.getByText('$0.1234')).toBeDefined();
      expect(screen.getByText('42')).toBeDefined();
    });
  });

  it('renders daily cost chart section', async () => {
    mockFetch.mockResolvedValueOnce({
      status: 200,
      ok: true,
      json: async () => mockStats,
    });
    mockFetch.mockResolvedValueOnce({
      status: 200,
      ok: true,
      json: async () => mockFeedback,
    });

    render(<AdminCostsPage />);

    await waitFor(() => {
      expect(screen.getByText('admin.dailyCosts')).toBeDefined();
    });
  });

  it('renders subagent breakdown section', async () => {
    mockFetch.mockResolvedValueOnce({
      status: 200,
      ok: true,
      json: async () => mockStats,
    });
    mockFetch.mockResolvedValueOnce({
      status: 200,
      ok: true,
      json: async () => mockFeedback,
    });

    render(<AdminCostsPage />);

    await waitFor(() => {
      expect(screen.getByText('admin.subagentBreakdown')).toBeDefined();
    });
  });

  it('renders top users table with data', async () => {
    mockFetch.mockResolvedValueOnce({
      status: 200,
      ok: true,
      json: async () => mockStats,
    });
    mockFetch.mockResolvedValueOnce({
      status: 200,
      ok: true,
      json: async () => mockFeedback,
    });

    render(<AdminCostsPage />);

    await waitFor(() => {
      expect(screen.getByText('admin.topUsers')).toBeDefined();
    });
  });

  it('triggers CSV export on button click', async () => {
    mockFetch.mockResolvedValueOnce({
      status: 200,
      ok: true,
      json: async () => mockStats,
    });
    mockFetch.mockResolvedValueOnce({
      status: 200,
      ok: true,
      json: async () => mockFeedback,
    });

    render(<AdminCostsPage />);

    await waitFor(() => {
      expect(screen.getByText('admin.exportCsv')).toBeDefined();
    });

    fireEvent.click(screen.getByText('admin.exportCsv'));
    expect(mockOpen).toHaveBeenCalledWith(
      expect.stringContaining('/admin/costs/export'),
      '_blank'
    );
  });

  it('renders feedback summary section with data', async () => {
    mockFetch.mockResolvedValueOnce({
      status: 200,
      ok: true,
      json: async () => mockStats,
    });
    mockFetch.mockResolvedValueOnce({
      status: 200,
      ok: true,
      json: async () => mockFeedback,
    });

    render(<AdminCostsPage />);

    await waitFor(() => {
      expect(screen.getByText('admin.feedbackTitle')).toBeDefined();
      expect(screen.getByText('15')).toBeDefined();
      expect(screen.getByText('5')).toBeDefined();
      expect(screen.getByText('75%')).toBeDefined();
    });
  });
});
