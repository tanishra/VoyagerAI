import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import Navbar from '@/components/Navbar';
import { clearSessionCache } from '@/lib/auth';

const mockFetch = vi.fn();

vi.stubGlobal('fetch', mockFetch);

vi.mock('next/navigation', () => ({
  usePathname: () => '/',
  useRouter: () => ({ push: vi.fn() }),
}));

describe('Navbar auth', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    clearSessionCache();
  });

  it('shows Sign in button when not authenticated', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: async () => ({}),
    });

    render(<Navbar />);

    await waitFor(() => {
      expect(screen.getByText('Sign in')).toBeInTheDocument();
    });
  });

  it('shows user avatar and name when authenticated', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        user_id: 'alice@example.com',
        display_name: 'Alice',
        avatar_url: null,
        email: 'alice@example.com',
      }),
    });

    render(<Navbar />);

    await waitFor(() => {
      expect(screen.getByText('Alice')).toBeInTheDocument();
    });
  });

  it('shows Dev badge for dev@localhost user', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        user_id: 'dev@localhost',
        display_name: 'Dev User',
        avatar_url: null,
        email: 'dev@localhost',
      }),
    });

    render(<Navbar />);

    await waitFor(() => {
      expect(screen.getByText('Dev User')).toBeInTheDocument();
      expect(screen.getByText('Dev')).toBeInTheDocument();
    });
  });
});
