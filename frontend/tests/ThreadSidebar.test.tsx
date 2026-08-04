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
  },
  {
    thread_id: 'chat:abc:t2',
    summary: 'Weekend in Paris',
    created_at: 1722700000,
    updated_at: 1722705678,
  },
];

describe('ThreadSidebar', () => {
  it('renders thread list', () => {
    render(
      <ThreadSidebar
        threads={mockThreads}
        activeThreadId={null}
        loadingHistory={false}
        onSelect={() => {}}
        onDelete={() => {}}
        onNewChat={() => {}}
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
        onSelect={() => {}}
        onDelete={() => {}}
        onNewChat={() => {}}
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
        onSelect={onSelect}
        onDelete={() => {}}
        onNewChat={() => {}}
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
        onSelect={() => {}}
        onDelete={() => {}}
        onNewChat={onNewChat}
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
        onSelect={() => {}}
        onDelete={onDelete}
        onNewChat={() => {}}
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
});
