import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ThreadSidebar from '@/app/chat/ThreadSidebar';
import type { ThreadMeta } from '@/lib/threads-api';
import type { ShareLink } from '@/lib/share-api';

vi.mock('next/navigation', () => ({
  useParams: () => ({}),
  useRouter: () => ({ push: vi.fn() }),
}));

const mockListShares = vi.fn();
const mockRevokeShare = vi.fn();
vi.mock('@/lib/share-api', () => ({
  listShares: (...args: unknown[]) => mockListShares(...args),
  revokeShare: (...args: unknown[]) => mockRevokeShare(...args),
}));

const mockThreads: ThreadMeta[] = [
  {
    thread_id: 'chat:abc:thread1',
    summary: 'Paris trip',
    created_at: 1700000000,
    updated_at: 1700000100,
    status: 'idle',
    message_count: 5,
  },
];

const mockShares: ShareLink[] = [
  {
    token: 'token-abc',
    thread_id: 'chat:abc:thread1',
    destination: 'Paris, France',
    created_at: 1700000000,
    expires_at: 1700604800,
    share_url: 'http://localhost:3000/share/token-abc',
  },
];

const defaultProps = {
  threads: mockThreads,
  activeThreadId: null,
  loadingHistory: false,
  hasMore: false,
  loadingMore: false,
  onSelect: vi.fn(),
  onDelete: vi.fn(),
  onNewChat: vi.fn(),
  onLoadMore: vi.fn(),
};

describe('ThreadSidebar — Shared Links', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows empty state when no shares exist', async () => {
    mockListShares.mockResolvedValueOnce([]);

    render(<ThreadSidebar {...defaultProps} />);

    // Expand the shared links section
    fireEvent.click(screen.getByText('Shared Links'));

    await waitFor(() => {
      expect(screen.getByText(/No shared links yet/)).toBeInTheDocument();
    });
  });

  it('lists active share links with destination', async () => {
    mockListShares.mockResolvedValueOnce(mockShares);

    render(<ThreadSidebar {...defaultProps} />);

    fireEvent.click(screen.getByText('Shared Links'));

    await waitFor(() => {
      expect(screen.getByText('Paris, France')).toBeInTheDocument();
    });
  });

  it('shows share count badge', async () => {
    mockListShares.mockResolvedValueOnce(mockShares);

    render(<ThreadSidebar {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText('1')).toBeInTheDocument();
    });
  });

  it('revokes a share link on click', async () => {
    mockListShares.mockResolvedValueOnce(mockShares);
    mockRevokeShare.mockResolvedValueOnce(true);

    render(<ThreadSidebar {...defaultProps} />);

    fireEvent.click(screen.getByText('Shared Links'));

    await waitFor(() => {
      expect(screen.getByText('Paris, France')).toBeInTheDocument();
    });

    const revokeBtn = screen.getByLabelText('Revoke share link');
    fireEvent.click(revokeBtn);

    await waitFor(() => {
      expect(mockRevokeShare).toHaveBeenCalledWith('token-abc');
    });
  });
});
