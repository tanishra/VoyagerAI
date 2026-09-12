import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { NextIntlClientProvider } from 'next-intl';
import ItineraryEditor from '@/components/ItineraryEditor';
import en from '../messages/en.json';
import type { Itinerary } from '@/lib/types';

vi.mock('@/lib/useLocale', () => ({
  useLocale: () => 'en',
}));

vi.mock('@/lib/useCurrency', () => ({
  useCurrency: () => ['USD', vi.fn()],
}));

function renderWithProvider(ui: React.ReactElement) {
  return render(
    <NextIntlClientProvider locale="en" messages={en as Record<string, unknown>}>
      {ui}
    </NextIntlClientProvider>
  );
}

const makeItinerary = (overrides?: Partial<Itinerary>): Itinerary => ({
  destination: 'Tokyo',
  total_days: 2,
  estimated_total_cost_usd: 100,
  budget_status: 'within',
  visa_note: 'No visa',
  best_season_note: 'Spring',
  days: [
    {
      day: 1,
      theme: 'Arrival',
      morning: { activity: 'Check-in', location: 'Hotel', cost_usd: 20, duration: '1h' },
      afternoon: { activity: 'Park visit', location: 'Park', cost_usd: 10, duration: '2h' },
      evening: { activity: 'Dinner', location: 'Restaurant', cost_usd: 30, duration: '1h' },
      transport: 'Train',
      accommodation: 'Hotel',
      daily_cost_usd: 60,
      tips: ['Tip 1'],
    },
    {
      day: 2,
      theme: 'Temples',
      morning: { activity: 'Temple', location: 'Asakusa', cost_usd: 0, duration: '2h' },
      afternoon: { activity: 'Shopping', location: 'Shibuya', cost_usd: 20, duration: '3h' },
      evening: { activity: 'Bar', location: 'Shinjuku', cost_usd: 20, duration: '2h' },
      transport: 'Subway',
      accommodation: 'Hotel',
      daily_cost_usd: 40,
      tips: ['Tip 2'],
    },
  ],
  warnings: [],
  packing_essentials: [],
  ...overrides,
});

describe('ItineraryEditor', () => {
  it('renders the editor modal with destination', () => {
    renderWithProvider(
      <ItineraryEditor
        itinerary={makeItinerary()}
        threadId="t1"
        onClose={() => {}}
        onSave={() => {}}
      />
    );
    expect(screen.getByText('Edit Itinerary')).toBeInTheDocument();
    expect(screen.getByText('Tokyo')).toBeInTheDocument();
  });

  it('renders day columns for each day', () => {
    renderWithProvider(
      <ItineraryEditor
        itinerary={makeItinerary()}
        threadId="t1"
        onClose={() => {}}
        onSave={() => {}}
      />
    );
    expect(screen.getByText('Day 1')).toBeInTheDocument();
    expect(screen.getByText('Day 2')).toBeInTheDocument();
  });

  it('renders activity names in the board', () => {
    renderWithProvider(
      <ItineraryEditor
        itinerary={makeItinerary()}
        threadId="t1"
        onClose={() => {}}
        onSave={() => {}}
      />
    );
    expect(screen.getByText('Check-in')).toBeInTheDocument();
    expect(screen.getByText('Park visit')).toBeInTheDocument();
    expect(screen.getByText('Temple')).toBeInTheDocument();
  });

  it('renders Save Changes button', () => {
    renderWithProvider(
      <ItineraryEditor
        itinerary={makeItinerary()}
        threadId="t1"
        onClose={() => {}}
        onSave={() => {}}
      />
    );
    expect(screen.getByText('Save Changes')).toBeInTheDocument();
  });

  it('renders Discard button', () => {
    renderWithProvider(
      <ItineraryEditor
        itinerary={makeItinerary()}
        threadId="t1"
        onClose={() => {}}
        onSave={() => {}}
      />
    );
    expect(screen.getAllByText('Discard Changes').length).toBeGreaterThanOrEqual(1);
  });

  it('renders Add Activity button for each day', () => {
    renderWithProvider(
      <ItineraryEditor
        itinerary={makeItinerary()}
        threadId="t1"
        onClose={() => {}}
        onSave={() => {}}
      />
    );
    const addButtons = screen.getAllByText('Add Activity');
    expect(addButtons.length).toBe(2);
  });

  it('shows AddActivityForm when Add Activity is clicked', () => {
    renderWithProvider(
      <ItineraryEditor
        itinerary={makeItinerary()}
        threadId="t1"
        onClose={() => {}}
        onSave={() => {}}
      />
    );
    const addButtons = screen.getAllByText('Add Activity');
    fireEvent.click(addButtons[0]);
    expect(screen.getByPlaceholderText('Activity Name')).toBeInTheDocument();
  });

  it('removes activity and shows undo toast', () => {
    renderWithProvider(
      <ItineraryEditor
        itinerary={makeItinerary()}
        threadId="t1"
        onClose={() => {}}
        onSave={() => {}}
      />
    );
    const removeButtons = screen.getAllByLabelText('Remove Activity');
    fireEvent.click(removeButtons[0]);
    expect(screen.getByText(/Removed 'Check-in'/)).toBeInTheDocument();
    expect(screen.getByText('Undo')).toBeInTheDocument();
  });

  it('restores activity when Undo is clicked', () => {
    renderWithProvider(
      <ItineraryEditor
        itinerary={makeItinerary()}
        threadId="t1"
        onClose={() => {}}
        onSave={() => {}}
      />
    );
    const removeButtons = screen.getAllByLabelText('Remove Activity');
    fireEvent.click(removeButtons[0]);
    expect(screen.getByText(/Removed 'Check-in'/)).toBeInTheDocument();
    fireEvent.click(screen.getByText('Undo'));
    expect(screen.getByText('Check-in')).toBeInTheDocument();
  });

  it('calls onClose when close button is clicked', () => {
    const onClose = vi.fn();
    renderWithProvider(
      <ItineraryEditor
        itinerary={makeItinerary()}
        threadId="t1"
        onClose={onClose}
        onSave={() => {}}
      />
    );
    fireEvent.click(screen.getByLabelText('Close'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('calls onSave with modified itinerary when Save is clicked', () => {
    const onSave = vi.fn();
    renderWithProvider(
      <ItineraryEditor
        itinerary={makeItinerary()}
        threadId="t1"
        onClose={() => {}}
        onSave={onSave}
      />
    );
    const removeButtons = screen.getAllByLabelText('Remove Activity');
    fireEvent.click(removeButtons[0]);
    fireEvent.click(screen.getByText('Save Changes'));
    expect(onSave).toHaveBeenCalledTimes(1);
    const saved = onSave.mock.calls[0][0];
    expect(saved.days[0].morning.activity).toBe('');
  });

  it('shows discard confirmation when there are unsaved changes', () => {
    renderWithProvider(
      <ItineraryEditor
        itinerary={makeItinerary()}
        threadId="t1"
        onClose={() => {}}
        onSave={() => {}}
      />
    );
    const removeButtons = screen.getAllByLabelText('Remove Activity');
    fireEvent.click(removeButtons[0]);
    fireEvent.click(screen.getAllByText('Discard Changes')[0]);
    expect(screen.getByText('You have unsaved changes. Discard them?')).toBeInTheDocument();
  });

  it('closes discard confirmation when Cancel is clicked', () => {
    renderWithProvider(
      <ItineraryEditor
        itinerary={makeItinerary()}
        threadId="t1"
        onClose={() => {}}
        onSave={() => {}}
      />
    );
    const removeButtons = screen.getAllByLabelText('Remove Activity');
    fireEvent.click(removeButtons[0]);
    fireEvent.click(screen.getAllByText('Discard Changes')[0]);
    expect(screen.getByText('You have unsaved changes. Discard them?')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Cancel'));
    expect(screen.queryByText('You have unsaved changes. Discard them?')).not.toBeInTheDocument();
  });

  it('renders drop here placeholder for empty slots', () => {
    const itin = makeItinerary();
    itin.days[0].morning = { activity: '', location: '', cost_usd: 0, duration: '' };
    renderWithProvider(
      <ItineraryEditor
        itinerary={itin}
        threadId="t1"
        onClose={() => {}}
        onSave={() => {}}
      />
    );
    expect(screen.getAllByText('Drop activity here').length).toBeGreaterThanOrEqual(1);
  });

  it('renders BudgetStatus badge', () => {
    renderWithProvider(
      <ItineraryEditor
        itinerary={makeItinerary()}
        threadId="t1"
        onClose={() => {}}
        onSave={() => {}}
      />
    );
    expect(screen.getByText('Within budget')).toBeInTheDocument();
  });
});
