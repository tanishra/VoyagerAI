import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ThreadSidebar from '@/app/[locale]/chat/ThreadSidebar';
import type { ThreadMeta } from '@/lib/threads-api';

vi.mock('@/lib/share-api', () => ({
  listShares: vi.fn().mockResolvedValue([]),
  revokeShare: vi.fn().mockResolvedValue(true),
}));

vi.mock('@/lib/threads-api', () => ({
  searchThreads: vi.fn().mockResolvedValue({ results: [], total: 0, has_more: false }),
}));

vi.mock('next/navigation', () => ({
  usePathname: vi.fn().mockReturnValue('/en/chat'),
  useRouter: vi.fn().mockReturnValue({ push: vi.fn() }),
}));

vi.mock('@/lib/useLocale', () => ({
  useLocale: vi.fn().mockReturnValue('en'),
  setLocale: vi.fn(),
  locales: ['en', 'fr'],
}));

vi.mock('next-intl', () => ({
  useTranslations: (namespace: string) => (key: string, params?: Record<string, unknown>) => {
    if (params && key === 'searchResults') return `${params.count} results found`;
    return `${namespace}.${key}`;
  },
}));

const mockThreads: ThreadMeta[] = [
  {
    thread_id: 'chat:abc:t1',
    summary: 'Plan a 3-day Tokyo trip',
    created_at: 1722800000,
    updated_at: 1722801234,
    status: 'idle',
    message_count: 4,
  },
  {
    thread_id: 'chat:abc:t2',
    summary: 'Weekend in Paris',
    created_at: 1722700000,
    updated_at: 1722705678,
    status: 'idle',
    message_count: 2,
  },
];

const mockProps = {
  threads: mockThreads,
  activeThreadId: null,
  loadingHistory: false,
  hasMore: false,
  loadingMore: false,
  onSelect: vi.fn(),
  onDelete: vi.fn(),
  onNewChat: vi.fn(),
  onLoadMore: vi.fn(),
  user: null,
};

describe('ThreadSidebar Search', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('client-side search filters threads by summary', () => {
    render(<ThreadSidebar {...mockProps} />);

    const input = screen.getByPlaceholderText('threads.search');
    fireEvent.change(input, { target: { value: 'Tokyo' } });

    expect(screen.getByText('Plan a 3-day Tokyo trip')).toBeDefined();
    expect(screen.queryByText('Weekend in Paris')).toBeNull();
  });

  it('shows "Search all messages" button when query is entered', () => {
    render(<ThreadSidebar {...mockProps} />);

    const input = screen.getByPlaceholderText('threads.search');
    fireEvent.change(input, { target: { value: 'Tokyo' } });

    expect(screen.getByText('threads.searchAllMessages')).toBeDefined();
  });

  it('deep search shows results from backend', async () => {
    const { searchThreads } = await import('@/lib/threads-api');
    vi.mocked(searchThreads).mockResolvedValueOnce({
      results: [
        {
          thread_id: 'chat:abc:t1',
          summary: 'Tokyo trip',
          snippet: 'Plan a trip to Tokyo with temple visits',
          updated_at: 1722801234,
          message_count: 4,
        },
      ],
      total: 1,
      has_more: false,
    });

    render(<ThreadSidebar {...mockProps} />);

    const input = screen.getByPlaceholderText('threads.search');
    fireEvent.change(input, { target: { value: 'Tokyo' } });

    const deepSearchBtn = screen.getByText('threads.searchAllMessages');
    fireEvent.click(deepSearchBtn);

    await waitFor(() => {
      expect(screen.getByText('1 results found')).toBeDefined();
      expect(screen.getByText('Tokyo trip')).toBeDefined();
    });
  });

  it('clear search resets to normal thread list', async () => {
    const { searchThreads } = await import('@/lib/threads-api');
    vi.mocked(searchThreads).mockResolvedValueOnce({
      results: [
        {
          thread_id: 'chat:abc:t1',
          summary: 'Tokyo trip',
          snippet: 'Plan a trip to Tokyo',
          updated_at: 1722801234,
          message_count: 4,
        },
      ],
      total: 1,
      has_more: false,
    });

    render(<ThreadSidebar {...mockProps} />);

    // Enter search and trigger deep search
    const input = screen.getByPlaceholderText('threads.search');
    fireEvent.change(input, { target: { value: 'Tokyo' } });
    fireEvent.click(screen.getByText('threads.searchAllMessages'));

    await waitFor(() => {
      expect(screen.getByText('Tokyo trip')).toBeDefined();
    });

    // Clear deep search — back to normal view (client-side filter still active for "Tokyo")
    fireEvent.click(screen.getByText('threads.backToConversations'));

    // Should show normal thread list again (filtered by "Tokyo" client-side)
    expect(screen.getByText('Plan a 3-day Tokyo trip')).toBeDefined();
    // "Weekend in Paris" is filtered out because searchQuery is still "Tokyo"
    expect(screen.queryByText('Tokyo trip')).toBeNull();
  });
});
