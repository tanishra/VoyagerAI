import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import InstallPrompt from '@/components/InstallPrompt';

// Mock framer-motion
vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: { children: React.ReactNode } & Record<string, unknown>) => <div {...props}>{children}</div>,
  },
  AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

// Mock lucide-react
vi.mock('lucide-react', () => ({
  Download: () => <span data-testid="download" />,
  X: () => <span data-testid="x" />,
}));

beforeEach(() => {
  localStorage.clear();
  // Reset event listeners
  window.removeEventListener('beforeinstallprompt', () => {});
});

describe('InstallPrompt', () => {
  it('renders nothing when beforeinstallprompt has not fired', () => {
    const { container } = render(<InstallPrompt />);
    expect(container.querySelector('button')).toBeNull();
  });

  it('shows install button when beforeinstallprompt fires', () => {
    render(<InstallPrompt />);

    // Simulate beforeinstallprompt event
    const event = new Event('beforeinstallprompt');
    Object.defineProperty(event, 'prompt', { value: vi.fn().mockResolvedValue(undefined) });
    Object.defineProperty(event, 'userChoice', {
      value: Promise.resolve({ outcome: 'accepted' }),
    });
    act(() => {
      window.dispatchEvent(event);
    });

    expect(screen.getByText('Install App')).toBeInTheDocument();
  });

  it('dismiss hides the button and persists in localStorage', () => {
    render(<InstallPrompt />);

    // Fire beforeinstallprompt
    const event = new Event('beforeinstallprompt');
    Object.defineProperty(event, 'prompt', { value: vi.fn().mockResolvedValue(undefined) });
    Object.defineProperty(event, 'userChoice', {
      value: Promise.resolve({ outcome: 'accepted' }),
    });
    act(() => {
      window.dispatchEvent(event);
    });

    // Click dismiss button
    const dismissBtn = screen.getByLabelText('Dismiss install prompt');
    fireEvent.click(dismissBtn);

    expect(screen.queryByText('Install App')).not.toBeInTheDocument();
    expect(localStorage.getItem('voyagerai_install_dismissed')).toBe('true');
  });

  it('does not show when already dismissed in localStorage', () => {
    localStorage.setItem('voyagerai_install_dismissed', 'true');
    render(<InstallPrompt />);

    // Fire beforeinstallprompt — should not show because dismissed
    const event = new Event('beforeinstallprompt');
    Object.defineProperty(event, 'prompt', { value: vi.fn().mockResolvedValue(undefined) });
    Object.defineProperty(event, 'userChoice', {
      value: Promise.resolve({ outcome: 'accepted' }),
    });
    act(() => {
      window.dispatchEvent(event);
    });

    expect(screen.queryByText('Install App')).not.toBeInTheDocument();
  });
});
