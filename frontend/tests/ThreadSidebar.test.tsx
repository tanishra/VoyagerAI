import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ThreadSidebar from '@/app/chat/ThreadSidebar';
import type { ThreadMeta } from '@/lib/threads-api';

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
      />,
    );
    fireEvent.click(screen.getByText('New Chat'));
    expect(onNewChat).toHaveBeenCalled();
  });

  it('calls onDelete when delete button is clicked twice (confirm)', () => {
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
      />,
    );
    // First click shows confirm
    const deleteButtons = screen.getAllByLabelText('Delete thread');
    fireEvent.click(deleteButtons[0]);
    expect(onDelete).not.toHaveBeenCalled();
    // Second click confirms
    const confirmButton = screen.getByText('Confirm?');
    fireEvent.click(confirmButton);
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
      />,
    );
    expect(screen.queryByText('Load more')).not.toBeInTheDocument();
  });
});
