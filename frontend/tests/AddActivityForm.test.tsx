import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { NextIntlClientProvider } from 'next-intl';
import AddActivityForm from '@/components/AddActivityForm';
import en from '../messages/en.json';

function renderWithProvider(ui: React.ReactElement) {
  return render(
    <NextIntlClientProvider locale="en" messages={en as Record<string, unknown>}>
      {ui}
    </NextIntlClientProvider>
  );
}

describe('AddActivityForm', () => {
  it('renders form with activity name input', () => {
    renderWithProvider(<AddActivityForm onAdd={() => {}} onCancel={() => {}} />);
    expect(screen.getByPlaceholderText('Activity Name')).toBeInTheDocument();
  });

  it('renders location and duration inputs', () => {
    renderWithProvider(<AddActivityForm onAdd={() => {}} onCancel={() => {}} />);
    expect(screen.getByPlaceholderText('Location (optional)')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Duration (e.g., 2h)')).toBeInTheDocument();
  });

  it('renders cost input', () => {
    renderWithProvider(<AddActivityForm onAdd={() => {}} onCancel={() => {}} />);
    expect(screen.getByPlaceholderText('Estimated Cost')).toBeInTheDocument();
  });

  it('calls onAdd with correct slot data when form is submitted', () => {
    const onAdd = vi.fn();
    renderWithProvider(<AddActivityForm onAdd={onAdd} onCancel={() => {}} />);

    fireEvent.change(screen.getByPlaceholderText('Activity Name'), { target: { value: 'Visit Park' } });
    fireEvent.change(screen.getByPlaceholderText('Location (optional)'), { target: { value: 'Central Park' } });
    fireEvent.change(screen.getByPlaceholderText('Estimated Cost'), { target: { value: '15' } });
    fireEvent.change(screen.getByPlaceholderText('Duration (e.g., 2h)'), { target: { value: '3h' } });

    const submitButton = screen.getAllByRole('button', { name: 'Add Activity' }).find(
      (btn) => (btn as HTMLButtonElement).type === 'submit'
    )!;
    fireEvent.click(submitButton);
    expect(onAdd).toHaveBeenCalledTimes(1);
    const slot = onAdd.mock.calls[0][0];
    expect(slot.activity).toBe('Visit Park');
    expect(slot.location).toBe('Central Park');
    expect(slot.cost_usd).toBe(15);
    expect(slot.duration).toBe('3h');
  });

  it('does not call onAdd when activity name is empty', () => {
    const onAdd = vi.fn();
    renderWithProvider(<AddActivityForm onAdd={onAdd} onCancel={() => {}} />);

    const submitButton = screen.getAllByRole('button', { name: 'Add Activity' }).find(
      (btn) => (btn as HTMLButtonElement).type === 'submit'
    )!;
    fireEvent.click(submitButton);
    expect(onAdd).not.toHaveBeenCalled();
  });

  it('sets cost to 0 when cost field is empty', () => {
    const onAdd = vi.fn();
    renderWithProvider(<AddActivityForm onAdd={onAdd} onCancel={() => {}} />);

    const submitButton = screen.getAllByRole('button', { name: 'Add Activity' }).find(
      (btn) => (btn as HTMLButtonElement).type === 'submit'
    )!;
    fireEvent.change(screen.getByPlaceholderText('Activity Name'), { target: { value: 'Free Walk' } });
    fireEvent.click(submitButton);

    const slot = onAdd.mock.calls[0][0];
    expect(slot.cost_usd).toBe(0);
  });

  it('calls onCancel when cancel button is clicked', () => {
    const onCancel = vi.fn();
    renderWithProvider(<AddActivityForm onAdd={() => {}} onCancel={onCancel} />);

    fireEvent.click(screen.getByText('Cancel'));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it('calls onCancel when X button is clicked', () => {
    const onCancel = vi.fn();
    renderWithProvider(<AddActivityForm onAdd={() => {}} onCancel={onCancel} />);

    fireEvent.click(screen.getByLabelText('Cancel'));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it('shows error message when submitting without name', () => {
    renderWithProvider(<AddActivityForm onAdd={() => {}} onCancel={() => {}} />);

    const submitButton = screen.getAllByRole('button', { name: 'Add Activity' }).find(
      (btn) => (btn as HTMLButtonElement).type === 'submit'
    )!;
    fireEvent.click(submitButton);
    expect(screen.getByText('Activity Name')).toBeInTheDocument();
  });
});
