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

// Mock recharts
vi.mock('recharts', () => ({
  LineChart: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  AreaChart: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  BarChart: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  Line: () => <div />,
  Area: () => <div />,
  Bar: () => <div />,
  XAxis: () => <div />,
  YAxis: () => <div />,
  CartesianGrid: () => <div />,
  Tooltip: () => <div />,
  ResponsiveContainer: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
}));

// Mock the observability API
const mockGetSessions = vi.fn();
const mockGetSessionDetail = vi.fn();
const mockGetErrors = vi.fn();
const mockGetErrorSummary = vi.fn();
const mockGetUsage = vi.fn();

vi.mock('@/lib/observability-api', () => ({
  getSessions: (...args: unknown[]) => mockGetSessions(...args),
  getSessionDetail: (...args: unknown[]) => mockGetSessionDetail(...args),
  getErrors: (...args: unknown[]) => mockGetErrors(...args),
  getErrorSummary: (...args: unknown[]) => mockGetErrorSummary(...args),
  getUsage: (...args: unknown[]) => mockGetUsage(...args),
}));

// Mock feedback API
vi.mock('@/lib/feedback-api', () => ({
  getFeedbackAggregate: vi.fn().mockResolvedValue(null),
}));

// Mock fetch for CostsTab and SecurityTab
const mockFetch = vi.fn();
global.fetch = mockFetch as unknown as typeof fetch;

// Mock getSession for AdminGuard
const mockGetSession = vi.fn();
vi.mock('@/lib/auth', () => ({
  getSession: (...args: unknown[]) => mockGetSession(...args),
}));

// Mock window.location.href for redirect tests
const mockLocationHref = vi.fn();
delete (window as Partial<Window>).location;
Object.defineProperty(window, 'location', {
  value: {
    get href() { return ''; },
    set href(v: string) { mockLocationHref(v); },
  },
  writable: true,
});

// Import after mocks
import AdminPage from '@/app/[locale]/admin/page';
import { SessionsTable } from '@/components/admin/SessionsTable';
import { TraceWaterfall } from '@/components/admin/TraceWaterfall';
import { ErrorsPanel } from '@/components/admin/ErrorsPanel';
import { UsagePanel } from '@/components/admin/UsagePanel';

const mockSessionData = {
  sessions: [
    {
      thread_id: 'thread-1',
      user_hash: 'abc123def456',
      start_time: 1700000000,
      end_time: 1700000100,
      duration_seconds: 100,
      status: 'completed',
      subagent_count: 3,
      tool_call_count: 5,
      total_tokens_in: 1000,
      total_tokens_out: 500,
      total_cost_usd: 0.05,
      model_used: 'gpt-4o',
    },
    {
      thread_id: 'thread-2',
      user_hash: 'xyz789abc012',
      start_time: 1700000200,
      end_time: null,
      duration_seconds: null,
      status: 'running',
      subagent_count: 0,
      tool_call_count: 0,
      total_tokens_in: 0,
      total_tokens_out: 0,
      total_cost_usd: 0,
      model_used: '',
    },
  ],
  total: 2,
  limit: 20,
  offset: 0,
};

const mockEvents = [
  {
    thread_id: 'thread-1',
    event_type: 'tool_start',
    run_id: 'r1',
    name: 'get_weather',
    parent_run_id: '',
    input: { _redacted: true },
    output: '',
    error: '',
    tokens_in: 0,
    tokens_out: 0,
    cost_usd: 0,
    duration_ms: 0,
    model: '',
    timestamp: 1700000001,
  },
  {
    thread_id: 'thread-1',
    event_type: 'tool_end',
    run_id: 'r1',
    name: 'get_weather',
    parent_run_id: '',
    input: null,
    output: 'Sunny, 22°C',
    error: '',
    tokens_in: 0,
    tokens_out: 0,
    cost_usd: 0,
    duration_ms: 150,
    model: '',
    timestamp: 1700000002,
  },
];

const mockErrorSummary = {
  total_errors: 2,
  by_subagent: [{ name: 'weather_agent', count: 2 }],
  by_tool: [{ name: 'get_weather', count: 2 }],
  per_day: [{ date: '2024-01-01', count: 2 }],
};

const mockErrorEvents = [
  {
    thread_id: 'thread-1',
    subagent_name: 'weather_agent',
    tool_name: 'get_weather',
    error_message: 'API timeout',
    timestamp: 1700000003,
  },
];

const mockUsageData = {
  per_day: [
    { date: '2024-01-01', tokens_in: 1000, tokens_out: 500, cost: 0.05, sessions: 1 },
  ],
  per_subagent: [
    { name: 'orchestrator', tokens_in: 500, tokens_out: 200, cost: 0.03 },
  ],
  per_user: [
    { user_hash: 'abc123def456', sessions: 1, cost: 0.05 },
  ],
  totals: { tokens_in: 1000, tokens_out: 500, cost: 0.05, sessions: 1 },
};

describe('AdminPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetSessions.mockResolvedValue(mockSessionData);
    mockGetSessionDetail.mockResolvedValue({ session: mockSessionData.sessions[0], events: mockEvents });
    mockGetErrors.mockResolvedValue(mockErrorEvents);
    mockGetErrorSummary.mockResolvedValue(mockErrorSummary);
    mockGetUsage.mockResolvedValue(mockUsageData);
    mockFetch.mockResolvedValue({ ok: true, json: async () => ({}) });
    mockGetSession.mockResolvedValue({
      user_id: 'admin@example.com',
      display_name: 'Admin',
      avatar_url: null,
      email: 'admin@example.com',
      is_admin: true,
    });
  });

  it('renders tab bar with all tabs', async () => {
    render(<AdminPage />);
    await waitFor(() => {
      expect(screen.getByText('admin.tabSessions')).toBeDefined();
    });
    expect(screen.getByText('admin.tabTrace')).toBeDefined();
    expect(screen.getByText('admin.tabErrors')).toBeDefined();
    expect(screen.getByText('admin.tabUsage')).toBeDefined();
    expect(screen.getByText('admin.tabCosts')).toBeDefined();
    expect(screen.getByText('admin.tabSecurity')).toBeDefined();
  });

  it('shows sessions table by default', async () => {
    render(<AdminPage />);
    await waitFor(() => {
      expect(mockGetSessions).toHaveBeenCalled();
    });
  });

  it('shows access denied when user is not admin', async () => {
    mockGetSession.mockResolvedValue({
      user_id: 'user@example.com',
      display_name: 'User',
      avatar_url: null,
      email: 'user@example.com',
      is_admin: false,
    });
    render(<AdminPage />);
    await waitFor(() => {
      expect(screen.getByText('Access Denied')).toBeDefined();
    });
  });

  it('redirects to login when not authenticated', async () => {
    mockGetSession.mockResolvedValue(null);
    render(<AdminPage />);
    await waitFor(() => {
      expect(mockLocationHref).toHaveBeenCalledWith('/login');
    });
  });

  it('switches to trace tab when session is selected', async () => {
    render(<AdminPage />);
    await waitFor(() => {
      expect(mockGetSessions).toHaveBeenCalled();
    });
    // Click on a session row (user_hash is visible text)
    const row = await waitFor(() => screen.getByText('abc123def456'));
    fireEvent.click(row);
    await waitFor(() => {
      expect(mockGetSessionDetail).toHaveBeenCalledWith('thread-1');
    });
  });

  it('switches to errors tab', async () => {
    render(<AdminPage />);
    await waitFor(() => {
      expect(screen.getByText('admin.tabErrors')).toBeDefined();
    });
    fireEvent.click(screen.getByText('admin.tabErrors'));
    await waitFor(() => {
      expect(mockGetErrorSummary).toHaveBeenCalled();
      expect(mockGetErrors).toHaveBeenCalled();
    });
  });

  it('switches to usage tab', async () => {
    render(<AdminPage />);
    await waitFor(() => {
      expect(screen.getByText('admin.tabUsage')).toBeDefined();
    });
    fireEvent.click(screen.getByText('admin.tabUsage'));
    await waitFor(() => {
      expect(mockGetUsage).toHaveBeenCalled();
    });
  });
});

describe('SessionsTable', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetSessions.mockResolvedValue(mockSessionData);
  });

  it('renders session rows', async () => {
    render(<SessionsTable onSelectSession={vi.fn()} />);
    await waitFor(() => {
      expect(screen.getByText('abc123def456')).toBeDefined();
      expect(screen.getByText('xyz789abc012')).toBeDefined();
    });
  });

  it('calls onSelectSession when row is clicked', async () => {
    const onSelect = vi.fn();
    render(<SessionsTable onSelectSession={onSelect} />);
    await waitFor(() => {
      expect(screen.getByText('abc123def456')).toBeDefined();
    });
    fireEvent.click(screen.getByText('abc123def456'));
    expect(onSelect).toHaveBeenCalledWith('thread-1');
  });

  it('shows empty state when no sessions', async () => {
    mockGetSessions.mockResolvedValue({ sessions: [], total: 0, limit: 20, offset: 0 });
    render(<SessionsTable onSelectSession={vi.fn()} />);
    await waitFor(() => {
      expect(screen.getByText('admin.noSessions')).toBeDefined();
    });
  });
});

describe('TraceWaterfall', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetSessionDetail.mockResolvedValue({ session: mockSessionData.sessions[0], events: mockEvents });
  });

  it('shows prompt when no thread selected', () => {
    render(<TraceWaterfall threadId={null} />);
    expect(screen.getByText('admin.selectSessionPrompt')).toBeDefined();
  });

  it('renders events when thread is selected', async () => {
    render(<TraceWaterfall threadId="thread-1" />);
    await waitFor(() => {
      expect(mockGetSessionDetail).toHaveBeenCalledWith('thread-1');
    });
    await waitFor(() => {
      expect(screen.getAllByText('get_weather').length).toBeGreaterThan(0);
    });
  });
});

describe('ErrorsPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetErrorSummary.mockResolvedValue(mockErrorSummary);
    mockGetErrors.mockResolvedValue(mockErrorEvents);
  });

  it('renders error summary', async () => {
    render(<ErrorsPanel />);
    await waitFor(() => {
      expect(mockGetErrorSummary).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect(screen.getAllByText('admin.totalErrors').length).toBeGreaterThan(0);
    });
  });

  it('renders recent errors', async () => {
    render(<ErrorsPanel />);
    await waitFor(() => {
      expect(screen.getAllByText('API timeout').length).toBeGreaterThan(0);
    });
  });
});

describe('UsagePanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetUsage.mockResolvedValue(mockUsageData);
  });

  it('renders usage totals', async () => {
    render(<UsagePanel />);
    await waitFor(() => {
      expect(mockGetUsage).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect(screen.getAllByText('admin.totalCost').length).toBeGreaterThan(0);
    });
  });

  it('renders per-user table', async () => {
    render(<UsagePanel />);
    await waitFor(() => {
      expect(screen.getByText('abc123def456')).toBeDefined();
    });
  });
});
