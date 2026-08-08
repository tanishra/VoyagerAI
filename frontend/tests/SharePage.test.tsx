import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import SharePage from '@/app/share/[token]/page';

vi.mock('next/navigation', () => ({
  useParams: () => ({ token: 'test-token-123' }),
}));

const mockGetShare = vi.fn();
vi.mock('@/lib/share-api', () => ({
  getShare: (...args: unknown[]) => mockGetShare(...args),
}));

describe('SharePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders itinerary when share is valid', async () => {
    mockGetShare.mockResolvedValueOnce({
      itinerary: {
        destination: 'Paris, France',
        total_days: 3,
        estimated_total_cost_usd: 1200,
        budget_status: 'within',
        visa_note: 'Schengen',
        best_season_note: 'April-June',
        days: [
          {
            day: 1,
            theme: 'Arrival',
            morning: { activity: 'Check-in', location: 'Hotel', cost_usd: 0, duration: '1h' },
            afternoon: { activity: 'Eiffel Tower', location: 'Champ de Mars', cost_usd: 30, duration: '3h' },
            evening: { activity: 'Dinner', location: 'Bistro', cost_usd: 50, duration: '2h' },
            transport: 'Metro',
            accommodation: 'Hotel',
            daily_cost_usd: 400,
            tips: [],
          },
        ],
        warnings: ['Pickpockets'],
        packing_essentials: ['Shoes'],
      },
      destination: 'Paris, France',
      created_at: 1700000000,
      expires_at: 1700604800,
    });

    render(<SharePage />);

    await waitFor(() => {
      expect(screen.getAllByText('Paris, France').length).toBeGreaterThan(0);
    });
    expect(screen.getByText('Powered by VoyagerAI')).toBeInTheDocument();
  });

  it('renders expired message when share is invalid', async () => {
    mockGetShare.mockResolvedValueOnce(null);

    render(<SharePage />);

    await waitFor(() => {
      expect(screen.getByText('Link expired')).toBeInTheDocument();
    });
  });
});
