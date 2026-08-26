import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { createRef } from 'react';
import SuggestionPrompts from '@/components/SuggestionPrompts';

function makeT(prefix = 'cat'): (key: string) => string {
  return (key: string) => {
    const map: Record<string, string> = {
      greeting: 'Plan your next adventure',
      subtitle: 'Tell me about your trip',
      placeholder: 'Describe your dream trip...',
      messageInput: 'Message input',
      send: 'Send message',
      enterToSend: 'Press Enter to send',
      catAdventure: 'Adventure',
      catFood: 'Food',
      catFamily: 'Family',
      catBudget: 'Budget',
      catLuxury: 'Luxury',
      catCultural: 'Cultural',
      catAdventureSuggestion1: 'Trekking Patagonia',
      catAdventureSuggestion2: 'Scuba diving in the Great Barrier Reef',
      catAdventureSuggestion3: 'Safari in Serengeti',
      catAdventureSuggestion4: 'Rock climbing in Joshua Tree',
      catAdventureSuggestion5: 'Kayaking through Halong Bay',
      catAdventureSuggestion6: 'Hiking the Inca Trail',
      catFoodSuggestion1: 'Street food tour in Bangkok',
      catFoodSuggestion2: 'Wine tasting in Tuscany',
      catFoodSuggestion3: 'Sushi making class in Tokyo',
      catFoodSuggestion4: 'Tapas crawl in Barcelona',
      catFoodSuggestion5: 'Coffee plantation tour in Colombia',
      catFoodSuggestion6: 'Cooking class in Marrakech',
      catFamilySuggestion1: 'Disney World Orlando family trip',
      catFamilySuggestion2: 'London with kids',
      catFamilySuggestion3: 'Costa Rica family adventure',
      catFamilySuggestion4: 'Singapore family weekend',
      catFamilySuggestion5: 'Grand Canyon family road trip',
      catFamilySuggestion6: 'Tokyo Disneyland and city tour',
      catBudgetSuggestion1: '5-day Vietnam backpacking under $500',
      catBudgetSuggestion2: 'Eastern Europe on a shoestring',
      catBudgetSuggestion3: 'Thailand island hopping on a budget',
      catBudgetSuggestion4: 'Portugal road trip under $1000',
      catBudgetSuggestion5: 'Mexico City budget weekend',
      catBudgetSuggestion6: 'Cambodia temple tour on a budget',
      catLuxurySuggestion1: 'Maldives overwater villa retreat',
      catLuxurySuggestion2: 'Private yacht charter in Greek Islands',
      catLuxurySuggestion3: 'Dubai luxury shopping weekend',
      catLuxurySuggestion4: 'Seychelles private island resort',
      catLuxurySuggestion5: 'First-class train journey on the Orient Express',
      catLuxurySuggestion6: 'Bora Bora luxury honeymoon',
      catCulturalSuggestion1: 'Kyoto temples and tea ceremony tour',
      catCulturalSuggestion2: 'Ancient ruins of Petra, Jordan',
      catCulturalSuggestion3: 'Art and history in Rome',
      catCulturalSuggestion4: 'Mayan heritage tour in Guatemala',
      catCulturalSuggestion5: 'Istanbul mosque and bazaar tour',
      catCulturalSuggestion6: 'Opera and architecture in Vienna',
    };
    return map[key] ?? key;
  };
}

const defaultProps = {
  onSend: vi.fn(),
  input: '',
  setInput: vi.fn(),
  inputRef: createRef<HTMLTextAreaElement>(),
  handleKeyDown: vi.fn(),
  t: makeT(),
};

describe('SuggestionPrompts', () => {
  it('renders greeting and subtitle', () => {
    render(<SuggestionPrompts {...defaultProps} />);
    expect(screen.getByText('Plan your next adventure')).toBeInTheDocument();
    expect(screen.getByText('Tell me about your trip')).toBeInTheDocument();
  });

  it('renders 6 category pills', () => {
    render(<SuggestionPrompts {...defaultProps} />);
    expect(screen.getByText('Adventure')).toBeInTheDocument();
    expect(screen.getByText('Food')).toBeInTheDocument();
    expect(screen.getByText('Family')).toBeInTheDocument();
    expect(screen.getByText('Budget')).toBeInTheDocument();
    expect(screen.getByText('Luxury')).toBeInTheDocument();
    expect(screen.getByText('Cultural')).toBeInTheDocument();
  });

  it('default selected category is Adventure', () => {
    render(<SuggestionPrompts {...defaultProps} />);
    const adventureBtn = screen.getByText('Adventure').closest('button');
    expect(adventureBtn).toHaveAttribute('aria-pressed', 'true');
  });

  it('renders 4 suggestion cards', () => {
    render(<SuggestionPrompts {...defaultProps} />);
    const cards = screen.getAllByRole('button').filter(
      (btn) => btn.getAttribute('aria-pressed') === null && btn.textContent !== 'Send message',
    );
    const suggestionTexts = [
      'Trekking Patagonia', 'Scuba diving in the Great Barrier Reef',
      'Safari in Serengeti', 'Rock climbing in Joshua Tree',
      'Kayaking through Halong Bay', 'Hiking the Inca Trail',
    ];
    let matchCount = 0;
    for (const card of cards) {
      if (suggestionTexts.some((s) => card.textContent?.includes(s))) {
        matchCount++;
      }
    }
    expect(matchCount).toBe(4);
  });

  it('clicking a category pill changes displayed suggestions', () => {
    render(<SuggestionPrompts {...defaultProps} />);
    fireEvent.click(screen.getByText('Food'));
    const foodBtn = screen.getByText('Food').closest('button');
    expect(foodBtn).toHaveAttribute('aria-pressed', 'true');
    const adventureBtn = screen.getByText('Adventure').closest('button');
    expect(adventureBtn).toHaveAttribute('aria-pressed', 'false');
  });

  it('clicking a suggestion card calls onSend with suggestion text', () => {
    const onSend = vi.fn();
    render(<SuggestionPrompts {...defaultProps} onSend={onSend} />);
    const suggestionTexts = [
      'Trekking Patagonia', 'Scuba diving in the Great Barrier Reef',
      'Safari in Serengeti', 'Rock climbing in Joshua Tree',
      'Kayaking through Halong Bay', 'Hiking the Inca Trail',
    ];
    for (const card of screen.getAllByRole('button')) {
      if (suggestionTexts.some((s) => card.textContent?.includes(s))) {
        fireEvent.click(card);
        expect(onSend).toHaveBeenCalledTimes(1);
        expect(onSend).toHaveBeenCalledWith(expect.stringMatching(/Trekking|Scuba|Safari|Rock climbing|Kayaking|Hiking/));
        return;
      }
    }
    expect.fail('No suggestion card found to click');
  });

  it('renders centered input bar', () => {
    render(<SuggestionPrompts {...defaultProps} />);
    expect(screen.getByPlaceholderText('Describe your dream trip...')).toBeInTheDocument();
  });

  it('typing in input updates value via setInput', () => {
    const setInput = vi.fn();
    render(<SuggestionPrompts {...defaultProps} setInput={setInput} />);
    const textarea = screen.getByPlaceholderText('Describe your dream trip...');
    fireEvent.change(textarea, { target: { value: 'Plan a trip' } });
    expect(setInput).toHaveBeenCalledWith('Plan a trip');
  });

  it('send button is disabled when input is empty', () => {
    render(<SuggestionPrompts {...defaultProps} input="" />);
    const sendBtn = screen.getByLabelText('Send message');
    expect(sendBtn).toBeDisabled();
  });

  it('send button calls onSend when clicked with input', () => {
    const onSend = vi.fn();
    render(<SuggestionPrompts {...defaultProps} onSend={onSend} input="Plan a trip to Japan" />);
    const sendBtn = screen.getByLabelText('Send message');
    expect(sendBtn).not.toBeDisabled();
    fireEvent.click(sendBtn);
    expect(onSend).toHaveBeenCalledTimes(1);
  });
});
