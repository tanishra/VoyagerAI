import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { NextIntlClientProvider } from 'next-intl';
import EditableActivityCard from '@/components/EditableActivityCard';
import en from '../messages/en.json';
import type { TimeSlot } from '@/lib/types';

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

const makeSlot = (overrides?: Partial<TimeSlot>): TimeSlot => ({
  activity: 'Visit Museum',
  location: 'Downtown',
  cost_usd: 20,
  duration: '2h',
  ...overrides,
});

describe('EditableActivityCard', () => {
  it('renders activity name and location', () => {
    renderWithProvider(
      <EditableActivityCard
        slot={makeSlot()}
        slotKey="morning"
        onRemove={() => {}}
      />
    );
    expect(screen.getByText('Visit Museum')).toBeInTheDocument();
    expect(screen.getByText('Downtown')).toBeInTheDocument();
  });

  it('renders slot label', () => {
    renderWithProvider(
      <EditableActivityCard
        slot={makeSlot()}
        slotKey="afternoon"
        onRemove={() => {}}
      />
    );
    expect(screen.getByText('Afternoon')).toBeInTheDocument();
  });

  it('shows custom badge when isCustom is true', () => {
    renderWithProvider(
      <EditableActivityCard
        slot={makeSlot()}
        slotKey="morning"
        onRemove={() => {}}
        isCustom
      />
    );
    expect(screen.getByText(/Custom/)).toBeInTheDocument();
  });

  it('calls onRemove when remove button is clicked', () => {
    const onRemove = vi.fn();
    renderWithProvider(
      <EditableActivityCard
        slot={makeSlot()}
        slotKey="morning"
        onRemove={onRemove}
      />
    );
    fireEvent.click(screen.getByLabelText('Remove Activity'));
    expect(onRemove).toHaveBeenCalledTimes(1);
  });

  it('calls onMoveUp when up button is clicked', () => {
    const onMoveUp = vi.fn();
    renderWithProvider(
      <EditableActivityCard
        slot={makeSlot()}
        slotKey="morning"
        onRemove={() => {}}
        onMoveUp={onMoveUp}
      />
    );
    fireEvent.click(screen.getByLabelText('Move up'));
    expect(onMoveUp).toHaveBeenCalledTimes(1);
  });

  it('calls onMoveDown when down button is clicked', () => {
    const onMoveDown = vi.fn();
    renderWithProvider(
      <EditableActivityCard
        slot={makeSlot()}
        slotKey="morning"
        onRemove={() => {}}
        onMoveDown={onMoveDown}
      />
    );
    fireEvent.click(screen.getByLabelText('Move down'));
    expect(onMoveDown).toHaveBeenCalledTimes(1);
  });

  it('calls onMoveLeft when left button is clicked', () => {
    const onMoveLeft = vi.fn();
    renderWithProvider(
      <EditableActivityCard
        slot={makeSlot()}
        slotKey="morning"
        onRemove={() => {}}
        onMoveLeft={onMoveLeft}
      />
    );
    fireEvent.click(screen.getByLabelText('Move left'));
    expect(onMoveLeft).toHaveBeenCalledTimes(1);
  });

  it('calls onMoveRight when right button is clicked', () => {
    const onMoveRight = vi.fn();
    renderWithProvider(
      <EditableActivityCard
        slot={makeSlot()}
        slotKey="morning"
        onRemove={() => {}}
        onMoveRight={onMoveRight}
      />
    );
    fireEvent.click(screen.getByLabelText('Move right'));
    expect(onMoveRight).toHaveBeenCalledTimes(1);
  });

  it('does not render move buttons when canMove flags are false', () => {
    renderWithProvider(
      <EditableActivityCard
        slot={makeSlot()}
        slotKey="morning"
        onRemove={() => {}}
        onMoveUp={() => {}}
        onMoveDown={() => {}}
        onMoveLeft={() => {}}
        onMoveRight={() => {}}
        canMoveUp={false}
        canMoveDown={false}
        canMoveLeft={false}
        canMoveRight={false}
      />
    );
    expect(screen.queryByLabelText('Move up')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Move down')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Move left')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Move right')).not.toBeInTheDocument();
  });

  it('applies dragging styles when isDragging is true', () => {
    const { container } = renderWithProvider(
      <EditableActivityCard
        slot={makeSlot()}
        slotKey="morning"
        onRemove={() => {}}
        isDragging
      />
    );
    expect(container.firstChild).toHaveClass('opacity-50');
  });

  it('renders duration when present', () => {
    renderWithProvider(
      <EditableActivityCard
        slot={makeSlot({ duration: '3h' })}
        slotKey="morning"
        onRemove={() => {}}
      />
    );
    expect(screen.getByText('3h')).toBeInTheDocument();
  });

  it('does not render cost when cost_usd is 0', () => {
    renderWithProvider(
      <EditableActivityCard
        slot={makeSlot({ cost_usd: 0 })}
        slotKey="morning"
        onRemove={() => {}}
      />
    );
    expect(screen.queryByText('$0')).not.toBeInTheDocument();
  });
});
