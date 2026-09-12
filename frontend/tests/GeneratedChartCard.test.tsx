import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import GeneratedChartCard from '@/components/GeneratedChartCard';
import type { GeneratedChart } from '@/lib/types';

const mockBarChart: GeneratedChart = {
  type: 'chart',
  chart_type: 'bar',
  title: 'Cost Breakdown',
  data: [
    { label: 'Flights', 'Cost (USD)': 450 },
    { label: 'Hotels', 'Cost (USD)': 800 },
    { label: 'Food', 'Cost (USD)': 300 },
  ],
  series_keys: ['Cost (USD)'],
};

const mockPieChart: GeneratedChart = {
  type: 'chart',
  chart_type: 'pie',
  title: 'Budget Split',
  data: [
    { label: 'Transport', Amount: 200 },
    { label: 'Lodging', Amount: 600 },
  ],
  series_keys: ['Amount'],
};

describe('GeneratedChartCard', () => {
  it('renders bar chart title', () => {
    render(<GeneratedChartCard chart={mockBarChart} />);
    expect(screen.getByText('Cost Breakdown')).toBeInTheDocument();
  });

  it('renders pie chart title', () => {
    render(<GeneratedChartCard chart={mockPieChart} />);
    expect(screen.getByText('Budget Split')).toBeInTheDocument();
  });

  it('renders chart container with correct height', () => {
    const { container } = render(<GeneratedChartCard chart={mockBarChart} />);
    const chartContainer = container.querySelector('.h-\\[280px\\]');
    expect(chartContainer).toBeInTheDocument();
  });

  it('renders bar chart with correct title and container', () => {
    const { container } = render(<GeneratedChartCard chart={mockBarChart} />);
    expect(screen.getByText('Cost Breakdown')).toBeInTheDocument();
    expect(container.querySelector('.h-\\[280px\\]')).toBeInTheDocument();
  });

  it('renders pie chart with correct title and container', () => {
    const { container } = render(<GeneratedChartCard chart={mockPieChart} />);
    expect(screen.getByText('Budget Split')).toBeInTheDocument();
    expect(container.querySelector('.h-\\[280px\\]')).toBeInTheDocument();
  });
});
