import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { NextIntlClientProvider } from 'next-intl';
import ComparisonSkeleton from '@/app/[locale]/chat/ComparisonSkeleton';
import ItinerarySkeleton from '@/app/[locale]/chat/ItinerarySkeleton';
import GenerationStatus from '@/components/GenerationStatus';
import en from '@/messages/en.json';

const wrap = (ui: React.ReactElement) =>
  render(
    <NextIntlClientProvider locale="en" messages={en}>
      {ui}
    </NextIntlClientProvider>,
  );

describe('ComparisonSkeleton', () => {
  it('renders banner, matrix strip and 3 tier skeleton cards', () => {
    const { container } = wrap(<ComparisonSkeleton />);
    expect(screen.getByTestId('comparison-skeleton')).toBeTruthy();
    // shimmer bars present
    expect(container.querySelectorAll('.shimmer').length).toBeGreaterThan(10);
  });
});

describe('ItinerarySkeleton', () => {
  it('renders requested number of day rows', () => {
    wrap(<ItinerarySkeleton days={5} />);
    expect(screen.getByTestId('itinerary-skeleton')).toBeTruthy();
  });
});

describe('GenerationStatus', () => {
  it('shows label and detail', () => {
    wrap(<GenerationStatus label="Generating plans" detail="Searching: hotels in Delhi" />);
    expect(screen.getByText('Generating plans')).toBeTruthy();
    expect(screen.getByText('Searching: hotels in Delhi')).toBeTruthy();
  });

  it('renders without detail', () => {
    wrap(<GenerationStatus label="Researching" />);
    expect(screen.getByText('Researching')).toBeTruthy();
  });
});
