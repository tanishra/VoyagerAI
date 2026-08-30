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

const baseThread: ThreadMeta = {
  thread_id: 'chat:abc:t1',
  summary: 'Plan a 3-day Tokyo trip',
  created_at: 1722800000,
  updated_at: 1722801234,
  status: 'idle',
  message_count: 4,
};

const mockProps = {
  threads: [baseThread],
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

describe('ThreadSidebar Pinning', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('calls onTogglePin when pin is clicked in three-dot menu', () => {
    const onTogglePin = vi.fn();
    render(<ThreadSidebar {...mockProps} onTogglePin={onTogglePin} />);

    // Open the three-dot menu
    const menuButton = screen.getByLabelText('threads.moreOptions');
    fireEvent.click(menuButton);

    // Click "Pin"
    const pinButton = screen.getByText('threads.pin');
    fireEvent.click(pinButton);

    expect(onTogglePin).toHaveBeenCalledWith('chat:abc:t1', true);
  });

  it('shows "Unpin" when thread is already pinned', () => {
    const pinnedThread: ThreadMeta = { ...baseThread, pinned: true, pinned_at: 1722801300 };
    render(
      <ThreadSidebar
        {...mockProps}
        threads={[pinnedThread]}
        onTogglePin={vi.fn()}
      />
    );

    // Open the three-dot menu
    const menuButton = screen.getByLabelText('threads.moreOptions');
    fireEvent.click(menuButton);

    expect(screen.getByText('threads.unpin')).toBeDefined();
  });

  it('renders pinned section when a thread is pinned', () => {
    const pinnedThread: ThreadMeta = { ...baseThread, pinned: true, pinned_at: 1722801300 };
    const unpinnedThread: ThreadMeta = {
      ...baseThread,
      thread_id: 'chat:abc:t2',
      summary: 'Weekend in Paris',
      pinned: false,
    };

    render(
      <ThreadSidebar
        {...mockProps}
        threads={[pinnedThread, unpinnedThread]}
        onTogglePin={vi.fn()}
      />
    );

    expect(screen.getByText('threads.pinned')).toBeDefined();
    // Pinned thread should appear in the pinned section
    expect(screen.getByText('Plan a 3-day Tokyo trip')).toBeDefined();
    // Unpinned thread should also appear in date groups
    expect(screen.getByText('Weekend in Paris')).toBeDefined();
  });

  it('does not show pinned section when no threads are pinned', () => {
    render(
      <ThreadSidebar
        {...mockProps}
        threads={[baseThread]}
        onTogglePin={vi.fn()}
      />
    );

    expect(screen.queryByText('threads.pinned')).toBeNull();
  });
});
