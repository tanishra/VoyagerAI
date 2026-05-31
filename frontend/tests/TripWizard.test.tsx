import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import TripWizard from '@/components/TripWizard';

const defaultProps = {
  onSubmit: () => {},
  loading: false,
};

describe('TripWizard', () => {
  it('renders step 1 (destination) by default', () => {
    render(<TripWizard {...defaultProps} />);
    expect(screen.getByText('Where to?')).toBeInTheDocument();
    expect(screen.getByLabelText('Travel destination')).toBeInTheDocument();
    expect(screen.getByLabelText('Number of travel days')).toBeInTheDocument();
    expect(screen.getByLabelText('Budget in US dollars')).toBeInTheDocument();
  });

  it('shows popular destination quick picks', () => {
    render(<TripWizard {...defaultProps} />);
    expect(screen.getByText('Tokyo')).toBeInTheDocument();
    expect(screen.getByText('Paris')).toBeInTheDocument();
    expect(screen.getByText('Bali')).toBeInTheDocument();
    expect(screen.getByText('Rome')).toBeInTheDocument();
  });

  it('shows budget quick picks', () => {
    render(<TripWizard {...defaultProps} />);
    expect(screen.getByText('$500')).toBeInTheDocument();
    expect(screen.getByText('$1500')).toBeInTheDocument();
    expect(screen.getByText('$3000')).toBeInTheDocument();
    expect(screen.getByText('$5000')).toBeInTheDocument();
  });

  it('updates destination when popular city is clicked', () => {
    render(<TripWizard {...defaultProps} />);
    fireEvent.click(screen.getByText('Tokyo'));
    const input = screen.getByLabelText('Travel destination') as HTMLInputElement;
    expect(input.value).toBe('Tokyo');
  });

  it('updates budget when quick pick is clicked', () => {
    render(<TripWizard {...defaultProps} />);
    fireEvent.click(screen.getByText('$3000'));
    const input = screen.getByLabelText('Budget in US dollars') as HTMLInputElement;
    expect(input.value).toBe('3000');
  });

  it('shows validation errors on empty destination', () => {
    render(<TripWizard {...defaultProps} />);
    fireEvent.click(screen.getByText('Next'));
    expect(screen.getByText('Enter a destination')).toBeInTheDocument();
  });

  it('navigates to step 2 when step 1 is valid', () => {
    render(<TripWizard {...defaultProps} />);
    fireEvent.change(screen.getByLabelText('Travel destination'), { target: { value: 'Tokyo' } });
    fireEvent.click(screen.getByText('Next'));
    expect(screen.getByText('Your Vibe')).toBeInTheDocument();
    expect(screen.getByRole('radiogroup', { name: 'Travel style' })).toBeInTheDocument();
  });

  it('shows travel style options on step 2', () => {
    render(<TripWizard {...defaultProps} />);
    fireEvent.change(screen.getByLabelText('Travel destination'), { target: { value: 'Paris' } });
    fireEvent.click(screen.getByText('Next'));
    expect(screen.getByText('Adventure')).toBeInTheDocument();
    expect(screen.getByText('Cultural')).toBeInTheDocument();
    expect(screen.getByText('Luxury')).toBeInTheDocument();
    expect(screen.getByText('Budget')).toBeInTheDocument();
  });

  it('shows group type options on step 2', () => {
    render(<TripWizard {...defaultProps} />);
    fireEvent.change(screen.getByLabelText('Travel destination'), { target: { value: 'Paris' } });
    fireEvent.click(screen.getByText('Next'));
    expect(screen.getByText('Solo')).toBeInTheDocument();
    expect(screen.getByText('Couple')).toBeInTheDocument();
    expect(screen.getByText('Family')).toBeInTheDocument();
  });

  it('selects travel style on click', () => {
    render(<TripWizard {...defaultProps} />);
    fireEvent.change(screen.getByLabelText('Travel destination'), { target: { value: 'Paris' } });
    fireEvent.click(screen.getByText('Next'));
    const radios = screen.getAllByRole('radio');
    expect(radios.length).toBe(7);
    // Travel styles: Adventure, Cultural(default), Luxury, Budget
    // Group: Solo(default), Couple, Family
    expect(radios[1]).toHaveAttribute('aria-checked', 'true');

    // Work around stale DOM references by using a click on the text
    const luxuryText = screen.getByText('Luxury');
    fireEvent.click(luxuryText);

    const updatedRadios = screen.getAllByRole('radio');
    expect(updatedRadios[2]).toHaveAttribute('aria-checked', 'true');
    expect(updatedRadios[1]).toHaveAttribute('aria-checked', 'false');
    expect(updatedRadios[0]).toHaveAttribute('aria-checked', 'false');
    expect(updatedRadios[3]).toHaveAttribute('aria-checked', 'false');
  });

  it('navigates to step 3 from step 2', () => {
    render(<TripWizard {...defaultProps} />);
    fireEvent.change(screen.getByLabelText('Travel destination'), { target: { value: 'Bali' } });
    fireEvent.click(screen.getByText('Next'));
    fireEvent.click(screen.getByText('Next'));
    expect(screen.getByText('Almost there')).toBeInTheDocument();
    expect(screen.getByText('Trip Summary')).toBeInTheDocument();
  });

  it('shows trip summary on step 3', () => {
    render(<TripWizard {...defaultProps} />);
    fireEvent.change(screen.getByLabelText('Travel destination'), { target: { value: 'Rome' } });
    fireEvent.change(screen.getByLabelText('Number of travel days'), { target: { value: '7' } });
    fireEvent.change(screen.getByLabelText('Budget in US dollars'), { target: { value: '5000' } });
    fireEvent.click(screen.getByText('Next'));
    fireEvent.click(screen.getByText('Next'));
    expect(screen.getByText(/7 days/)).toBeInTheDocument();
    expect(screen.getByText(/5000/)).toBeInTheDocument();
  });

  it('calls onSubmit when submitted with valid data', () => {
    let submitted = false;
    const onSubmit = () => { submitted = true; };
    render(<TripWizard onSubmit={onSubmit} loading={false} />);
    fireEvent.change(screen.getByLabelText('Travel destination'), { target: { value: 'Rome' } });
    fireEvent.click(screen.getByText('Next'));
    fireEvent.click(screen.getByText('Next'));
    fireEvent.click(screen.getByText('Generate Itinerary'));
    expect(submitted).toBe(true);
  });

  it('shows loading state on submit button', () => {
    render(<TripWizard {...defaultProps} loading={true} />);
    // Navigate to step 3 to see the submit button
    fireEvent.change(screen.getByLabelText('Travel destination'), { target: { value: 'Tokyo' } });
    fireEvent.click(screen.getByText('Next'));
    fireEvent.click(screen.getByText('Next'));
    const btn = screen.getByText('Creating…');
    expect(btn).toBeInTheDocument();
    expect(btn.closest('button')).toBeDisabled();
  });

  it('shows Back button on steps > 0', () => {
    render(<TripWizard {...defaultProps} />);
    expect(screen.queryByText('Back')).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Travel destination'), { target: { value: 'Paris' } });
    fireEvent.click(screen.getByText('Next'));
    expect(screen.getByText('Back')).toBeInTheDocument();
  });

  it('goes back to previous step', () => {
    render(<TripWizard {...defaultProps} />);
    fireEvent.change(screen.getByLabelText('Travel destination'), { target: { value: 'Paris' } });
    fireEvent.click(screen.getByText('Next'));
    expect(screen.getByText('Your Vibe')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Back'));
    expect(screen.getByText('Where to?')).toBeInTheDocument();
  });

  it('shows progress step indicators', () => {
    render(<TripWizard {...defaultProps} />);
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('shows step labels on desktop', () => {
    render(<TripWizard {...defaultProps} />);
    const destLabels = screen.getAllByText('Destination');
    expect(destLabels.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Style & Budget')).toBeInTheDocument();
    expect(screen.getByText('Preferences')).toBeInTheDocument();
  });

  it('accepts dietary input on step 3', () => {
    render(<TripWizard {...defaultProps} />);
    fireEvent.change(screen.getByLabelText('Travel destination'), { target: { value: 'Tokyo' } });
    fireEvent.click(screen.getByText('Next'));
    fireEvent.click(screen.getByText('Next'));
    const dietary = screen.getByPlaceholderText('e.g. Vegetarian, Halal, Gluten-free');
    fireEvent.change(dietary, { target: { value: 'Vegetarian' } });
    expect((dietary as HTMLInputElement).value).toBe('Vegetarian');
  });

  it('accepts constraints textarea on step 3', () => {
    render(<TripWizard {...defaultProps} />);
    fireEvent.change(screen.getByLabelText('Travel destination'), { target: { value: 'Tokyo' } });
    fireEvent.click(screen.getByText('Next'));
    fireEvent.click(screen.getByText('Next'));
    const constraints = screen.getByPlaceholderText('e.g. Wheelchair accessible, no long walks, avoid heights...');
    fireEvent.change(constraints, { target: { value: 'No stairs' } });
    expect((constraints as HTMLTextAreaElement).value).toBe('No stairs');
  });
});
