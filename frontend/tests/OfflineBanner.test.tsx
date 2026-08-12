import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import OfflineBanner from '@/components/OfflineBanner';

// Mock framer-motion to avoid animation issues in jsdom
vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: { children: React.ReactNode } & Record<string, unknown>) => <div {...props}>{children}</div>,
  },
  AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

// Mock lucide-react icons
vi.mock('lucide-react', () => ({
  WifiOff: () => <span data-testid="wifi-off" />,
  Wifi: () => <span data-testid="wifi" />,
  CloudUpload: () => <span data-testid="cloud-upload" />,
}));

// Mock useOnlineStatus
const mockIsOnline = vi.fn();
vi.mock('@/lib/useOnlineStatus', () => ({
  useOnlineStatus: () => mockIsOnline(),
}));

beforeEach(() => {
  mockIsOnline.mockReturnValue(true);
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
  vi.clearAllMocks();
});

describe('OfflineBanner', () => {
  it('shows offline message when offline', () => {
    mockIsOnline.mockReturnValue(false);
    render(<OfflineBanner />);
    expect(screen.getByText(/You're offline/)).toBeInTheDocument();
  });

  it('shows nothing when online and not replaying after auto-dismiss', () => {
    mockIsOnline.mockReturnValue(true);
    const { container } = render(<OfflineBanner />);
    // On initial mount with online status, no back-online banner shows
    expect(container.querySelector('[class*="fixed"]')).toBeNull();
  });

  it('shows replaying message when replaying', () => {
    mockIsOnline.mockReturnValue(true);
    render(<OfflineBanner replaying={true} />);
    expect(screen.getByText(/sending queued messages/)).toBeInTheDocument();
  });

  it('shows back online briefly then auto-dismisses after reconnect', async () => {
    mockIsOnline.mockReturnValue(false);
    const { rerender } = render(<OfflineBanner />);
    expect(screen.getByText(/You.*offline/)).toBeInTheDocument();

    // Simulate going back online
    mockIsOnline.mockReturnValue(true);
    await act(async () => {
      rerender(<OfflineBanner />);
      // Flush the Promise.resolve().then() microtask
      await Promise.resolve();
    });

    // Should show "Back online" after reconnect
    expect(screen.getByText('Back online')).toBeInTheDocument();

    // After 3 seconds, should be dismissed
    act(() => {
      vi.advanceTimersByTime(3000);
    });
    expect(screen.queryByText('Back online')).not.toBeInTheDocument();
  });
});
