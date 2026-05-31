import { describe, it, expect, vi, beforeAll, afterAll } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import Home from '@/app/page';

// Mock framer-motion to render children directly
vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: any) => {
      // Filter out framer-motion specific props
      const { initial, animate, exit, transition, variants, custom, whileInView, ...rest } = props;
      return <div {...rest}>{children}</div>;
    },
    span: ({ children, ...props }: any) => {
      const { initial, animate, exit, transition, ...rest } = props;
      return <span {...rest}>{children}</span>;
    },
    h1: ({ children, ...props }: any) => {
      const { initial, animate, ...rest } = props;
      return <h1 {...rest}>{children}</h1>;
    },
    p: ({ children, ...props }: any) => {
      const { initial, animate, ...rest } = props;
      return <p {...rest}>{children}</p>;
    },
    ul: ({ children, ...props }: any) => {
      const { initial, animate, exit, ...rest } = props;
      return <ul {...rest}>{children}</ul>;
    },
    li: ({ children, ...props }: any) => {
      const { initial, animate, exit, ...rest } = props;
      return <li {...rest}>{children}</li>;
    },
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
  useScroll: () => ({ scrollYProgress: { on: () => {} } }),
  useSpring: () => ({ set: () => {} }),
}));

// Mock lucide-react to render simple elements
vi.mock('lucide-react', () => ({
  Globe: () => <span data-testid="globe" />,
  Sparkles: () => <span data-testid="sparkles" />,
  Plane: () => <span data-testid="plane" />,
  ArrowLeft: () => <span data-testid="arrow-left" />,
  MapPin: () => <span data-testid="map-pin" />,
  Calendar: () => <span data-testid="calendar" />,
  DollarSign: () => <span data-testid="dollar" />,
  Send: () => <span data-testid="send" />,
  Users: () => <span data-testid="users" />,
  Utensils: () => <span data-testid="utensils" />,
  Compass: () => <span data-testid="compass" />,
  Gem: () => <span data-testid="gem" />,
  Wallet: () => <span data-testid="wallet" />,
  Heart: () => <span data-testid="heart" />,
  UsersRound: () => <span data-testid="users-round" />,
  AlertCircle: () => <span data-testid="alert-circle" />,
  ArrowRight: () => <span data-testid="arrow-right" />,
  Check: () => <span data-testid="check" />,
  Sunrise: () => <span data-testid="sunrise" />,
  Palmtree: () => <span data-testid="palmtree" />,
  Sun: () => <span data-testid="sun" />,
  Moon: () => <span data-testid="moon" />,
  Clock: () => <span data-testid="clock" />,
  Car: () => <span data-testid="car" />,
  Hotel: () => <span data-testid="hotel" />,
  Lightbulb: () => <span data-testid="lightbulb" />,
  RefreshCw: () => <span data-testid="refresh" />,
  ChevronDown: () => <span data-testid="chevron-down" />,
  Timer: () => <span data-testid="timer" />,
  TrendingUp: () => <span data-testid="trending-up" />,
  TrendingDown: () => <span data-testid="trending-down" />,
  AlertTriangle: () => <span data-testid="alert-triangle" />,
  Eye: () => <span data-testid="eye" />,
  Luggage: () => <span data-testid="luggage" />,
  User: () => <span data-testid="user" />,
}));

// Mock the lazy-loaded ItineraryView
vi.mock('@/components/ItineraryView', () => ({
  default: ({ onReset, itinerary }: any) => (
    <div data-testid="itinerary-view">
      <span>{itinerary.destination}</span>
      <button onClick={onReset}>Plan Another Trip</button>
    </div>
  ),
}));

describe('Home page integration', () => {
  beforeAll(() => {
    global.fetch = vi.fn();
  });

  afterAll(() => {
    vi.restoreAllMocks();
  });

  it('renders TravelAI title', () => {
    render(<Home />);
    expect(screen.getByText('TravelAI')).toBeInTheDocument();
  });

  it('renders tagline', () => {
    render(<Home />);
    expect(screen.getByText('AI-powered trip planning — personalized itineraries in seconds')).toBeInTheDocument();
  });

  it('renders TripWizard form by default', () => {
    render(<Home />);
    expect(screen.getByText('Where to?')).toBeInTheDocument();
    expect(screen.getByLabelText('Travel destination')).toBeInTheDocument();
  });

  it('renders footer', () => {
    render(<Home />);
    expect(screen.getByText('Built with AI · Powered by Google ADK')).toBeInTheDocument();
  });

  it('renders Globe and Sparkles icons in header', () => {
    const { container } = render(<Home />);
    expect(container.querySelector('[data-testid="globe"]')).toBeInTheDocument();
    expect(container.querySelector('[data-testid="sparkles"]')).toBeInTheDocument();
  });

  it('submits form and shows loading with destination name', async () => {
    const { container } = render(<Home />);
    // Fill and submit the form
    fireEvent.change(screen.getByLabelText('Travel destination'), { target: { value: 'Tokyo' } });
    fireEvent.click(screen.getByText('Next'));
    fireEvent.click(screen.getByText('Next'));
    fireEvent.click(screen.getByText('Generate Itinerary'));
    // Should show loading state
    await waitFor(() => {
      expect(screen.getByText('Tokyo')).toBeInTheDocument();
    });
  });

  it('handles API error gracefully', async () => {
    (global.fetch as any).mockRejectedValueOnce(new Error('Network error'));
    render(<Home />);
    fireEvent.change(screen.getByLabelText('Travel destination'), { target: { value: 'Paris' } });
    fireEvent.click(screen.getByText('Next'));
    fireEvent.click(screen.getByText('Next'));
    fireEvent.click(screen.getByText('Generate Itinerary'));
    const errorMsg = await screen.findByText('Unable to connect to the server. Make sure the backend is running.');
    expect(errorMsg).toBeInTheDocument();
  });

  it('dismisses error on close button', async () => {
    (global.fetch as any).mockRejectedValueOnce(new Error('Network error'));
    render(<Home />);
    fireEvent.change(screen.getByLabelText('Travel destination'), { target: { value: 'Paris' } });
    fireEvent.click(screen.getByText('Next'));
    fireEvent.click(screen.getByText('Next'));
    fireEvent.click(screen.getByText('Generate Itinerary'));
    await screen.findByText('Unable to connect to the server. Make sure the backend is running.');
    fireEvent.click(screen.getByLabelText('Dismiss error'));
    expect(screen.queryByText('Unable to connect to the server. Make sure the backend is running.')).not.toBeInTheDocument();
  });
});
