import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import ThreadSidebar from '@/app/[locale]/chat/ThreadSidebar';
import type { ThreadMeta } from '@/lib/threads-api';

vi.mock('@/lib/share-api', () => ({
  listShares: vi.fn().mockResolvedValue([]),
  revokeShare: vi.fn().mockResolvedValue(true),
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

vi.mock('@/components/LanguageSwitcher', () => ({
  default: () => <div data-testid="lang-switcher" />,
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
    status: 'error',
    message_count: 2,
  },
];

describe('ThreadSidebar', () => {
  it('renders thread list', () => {
    render(
      <ThreadSidebar
        threads={mockThreads}
        activeThreadId={null}
        loadingHistory={false}
        hasMore={false}
        loadingMore={false}
        onSelect={() => {}}
        onDelete={() => {}}
        onNewChat={() => {}}
        onLoadMore={() => {}}
        user={null}
      />,
    );
    expect(screen.getByText('Plan a 3-day Tokyo trip')).toBeInTheDocument();
    expect(screen.getByText('Weekend in Paris')).toBeInTheDocument();
  });

  it('shows empty state when no threads', () => {
    render(
      <ThreadSidebar
        threads={[]}
        activeThreadId={null}
        loadingHistory={false}
        hasMore={false}
        loadingMore={false}
        onSelect={() => {}}
        onDelete={() => {}}
        onNewChat={() => {}}
        onLoadMore={() => {}}
        user={null}
      />,
    );
    expect(screen.getByText('No conversations yet. Start chatting!')).toBeInTheDocument();
  });

  it('calls onSelect when thread is clicked', () => {
    const onSelect = vi.fn();
    render(
      <ThreadSidebar
        threads={mockThreads}
        activeThreadId={null}
        loadingHistory={false}
        hasMore={false}
        loadingMore={false}
        onSelect={onSelect}
        onDelete={() => {}}
        onNewChat={() => {}}
        onLoadMore={() => {}}
        user={null}
      />,
    );
    fireEvent.click(screen.getByText('Plan a 3-day Tokyo trip'));
    expect(onSelect).toHaveBeenCalledWith('chat:abc:t1');
  });

  it('calls onNewChat when New Chat button is clicked', () => {
    const onNewChat = vi.fn();
    render(
      <ThreadSidebar
        threads={mockThreads}
        activeThreadId={null}
        loadingHistory={false}
        hasMore={false}
        loadingMore={false}
        onSelect={() => {}}
        onDelete={() => {}}
        onNewChat={onNewChat}
        onLoadMore={() => {}}
        user={null}
      />,
    );
    fireEvent.click(screen.getByText('New Chat'));
    expect(onNewChat).toHaveBeenCalled();
  });

  it('calls onDelete when delete is confirmed via three-dot menu', () => {
    const onDelete = vi.fn();
    render(
      <ThreadSidebar
        threads={mockThreads}
        activeThreadId={null}
        loadingHistory={false}
        hasMore={false}
        loadingMore={false}
        onSelect={() => {}}
        onDelete={onDelete}
        onNewChat={() => {}}
        onLoadMore={() => {}}
        user={null}
      />,
    );
    // Click three-dot menu button
    const menuButtons = screen.getAllByLabelText('More options');
    fireEvent.click(menuButtons[0]);
    // Click "Delete" in dropdown
    const deleteBtn = screen.getByText('Delete');
    fireEvent.click(deleteBtn);
    expect(onDelete).not.toHaveBeenCalled();
    // Click "Confirm delete?" to confirm
    const confirmBtn = screen.getByText('Confirm delete?');
    fireEvent.click(confirmBtn);
    expect(onDelete).toHaveBeenCalledWith('chat:abc:t1');
  });

  it('shows Load more button when hasMore is true', () => {
    const onLoadMore = vi.fn();
    render(
      <ThreadSidebar
        threads={mockThreads}
        activeThreadId={null}
        loadingHistory={false}
        hasMore={true}
        loadingMore={false}
        onSelect={() => {}}
        onDelete={() => {}}
        onNewChat={() => {}}
        onLoadMore={onLoadMore}
        user={null}
      />,
    );
    const loadMoreBtn = screen.getByText('Load more');
    fireEvent.click(loadMoreBtn);
    expect(onLoadMore).toHaveBeenCalled();
  });

  it('does not show Load more when hasMore is false', () => {
    render(
      <ThreadSidebar
        threads={mockThreads}
        activeThreadId={null}
        loadingHistory={false}
        hasMore={false}
        loadingMore={false}
        onSelect={() => {}}
        onDelete={() => {}}
        onNewChat={() => {}}
        onLoadMore={() => {}}
        user={null}
      />,
    );
    expect(screen.queryByText('Load more')).not.toBeInTheDocument();
  });

  it('calls onSelect when Enter key is pressed on a thread item', () => {
    const onSelect = vi.fn();
    render(
      <ThreadSidebar
        threads={mockThreads}
        activeThreadId={null}
        loadingHistory={false}
        hasMore={false}
        loadingMore={false}
        onSelect={onSelect}
        onDelete={() => {}}
        onNewChat={() => {}}
        onLoadMore={() => {}}
        user={null}
      />,
    );
    const threadItem = screen.getByText('Plan a 3-day Tokyo trip').closest('[role="button"]');
    expect(threadItem).not.toBeNull();
    fireEvent.keyDown(threadItem!, { key: 'Enter' });
    expect(onSelect).toHaveBeenCalledWith('chat:abc:t1');
  });

  it('calls onSelect when Space key is pressed on a thread item', () => {
    const onSelect = vi.fn();
    render(
      <ThreadSidebar
        threads={mockThreads}
        activeThreadId={null}
        loadingHistory={false}
        hasMore={false}
        loadingMore={false}
        onSelect={onSelect}
        onDelete={() => {}}
        onNewChat={() => {}}
        onLoadMore={() => {}}
        user={null}
      />,
    );
    const threadItem = screen.getByText('Plan a 3-day Tokyo trip').closest('[role="button"]');
    expect(threadItem).not.toBeNull();
    fireEvent.keyDown(threadItem!, { key: ' ' });
    expect(onSelect).toHaveBeenCalledWith('chat:abc:t1');
  });
});
