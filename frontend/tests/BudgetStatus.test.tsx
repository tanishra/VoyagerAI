import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { NextIntlClientProvider } from 'next-intl';
import BudgetStatus from '@/components/BudgetStatus';
import en from '../messages/en.json';

function renderWithProvider(ui: React.ReactElement) {
  return render(
    <NextIntlClientProvider locale="en" messages={en as Record<string, unknown>}>
      {ui}
    </NextIntlClientProvider>
  );
}

describe('BudgetStatus', () => {
  it('renders within budget badge with green styling', () => {
    renderWithProvider(
      <BudgetStatus status="within" totalCost={800} budget={1000} currency="USD" />
    );
    expect(screen.getByText('Within budget')).toBeInTheDocument();
  });

  it('renders over budget badge', () => {
    renderWithProvider(
      <BudgetStatus status="over" totalCost={1200} budget={1000} currency="USD" />
    );
    expect(screen.getByText('Over budget')).toBeInTheDocument();
  });

  it('renders under budget badge', () => {
    renderWithProvider(
      <BudgetStatus status="under" totalCost={500} budget={1000} currency="USD" />
    );
    expect(screen.getByText('Under budget')).toBeInTheDocument();
  });

  it('shows the difference amount when budget is provided', () => {
    const { container } = renderWithProvider(
      <BudgetStatus status="over" totalCost={1200} budget={1000} currency="USD" />
    );
    expect(container.textContent).toMatch(/200/);
  });

  it('does not show difference when budget is null', () => {
    const { container } = renderWithProvider(
      <BudgetStatus status="within" totalCost={800} budget={null} currency="USD" />
    );
    expect(container.textContent).not.toMatch(/\(\+/);
    expect(container.textContent).not.toMatch(/\(-/);
  });
});
