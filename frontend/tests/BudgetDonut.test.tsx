import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { NextIntlClientProvider } from 'next-intl';
import BudgetDonut from '@/components/BudgetDonut';
import en from '../messages/en.json';

function renderWithProvider(ui: React.ReactElement) {
  return render(
    <NextIntlClientProvider locale="en" messages={en as Record<string, unknown>}>
      {ui}
    </NextIntlClientProvider>
  );
}

const mockBreakdown = {
  accommodation: 300,
  food: 200,
  activities: 150,
  transport: 50,
  total: 700,
};

describe('BudgetDonut', () => {
  it('renders N/A when breakdown is null', () => {
    renderWithProvider(<BudgetDonut breakdown={null} currency="USD" />);
    expect(screen.getByText('N/A')).toBeInTheDocument();
  });

  it('renders N/A when total is 0', () => {
    renderWithProvider(
      <BudgetDonut breakdown={{ accommodation: 0, food: 0, activities: 0, transport: 0, total: 0 }} currency="USD" />
    );
    expect(screen.getByText('N/A')).toBeInTheDocument();
  });

  it('renders donut chart with segments when breakdown is provided', () => {
    const { container } = renderWithProvider(
      <BudgetDonut breakdown={mockBreakdown} currency="USD" />
    );
    expect(container.querySelector('svg')).toBeInTheDocument();
  });

  it('shows total in center', () => {
    renderWithProvider(
      <BudgetDonut breakdown={mockBreakdown} currency="USD" />
    );
    expect(screen.getByText('Total')).toBeInTheDocument();
  });

  it('renders legend with category labels', () => {
    renderWithProvider(
      <BudgetDonut breakdown={mockBreakdown} currency="USD" />
    );
    expect(screen.getByText('Accommodation')).toBeInTheDocument();
    expect(screen.getByText('Food')).toBeInTheDocument();
    expect(screen.getByText('Activities')).toBeInTheDocument();
    expect(screen.getByText('Transport')).toBeInTheDocument();
  });
});
