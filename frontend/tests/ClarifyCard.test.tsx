import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import ClarifyCard from '@/app/[locale]/chat/ClarifyCard';
import type { ClarifyData } from '@/lib/types';

const twoQuestions: ClarifyData = {
  questions: [
    {
      field: 'travel_style',
      header: 'Travel style',
      question: 'What pace do you prefer?',
      options: [
        { label: 'Relaxed', value: 'relaxed' },
        { label: 'Adventurous', value: 'adventurous' },
      ],
      multi_select: false,
    },
    {
      field: 'group_type',
      header: 'Group',
      question: 'Who is travelling?',
      options: [
        { label: 'Solo', value: 'solo' },
        { label: 'Friends', value: 'friends' },
      ],
      multi_select: false,
    },
  ],
};

const click = (el: Element) => act(() => { fireEvent.click(el); });

describe('ClarifyCard (U7)', () => {
  it('renders questions and options', () => {
    render(<ClarifyCard data={twoQuestions} onSend={() => {}} />);
    expect(screen.getByText('What pace do you prefer?')).toBeInTheDocument();
    expect(screen.getByText('Who is travelling?')).toBeInTheDocument();
    expect(screen.getByText('Relaxed pace')).toBeInTheDocument(); // enum label localized
    expect(screen.getAllByText('Other')).toHaveLength(2);
  });

  it('Send disabled until every question answered', () => {
    render(<ClarifyCard data={twoQuestions} onSend={() => {}} />);
    const send = () => screen.getByRole('button', { name: /send answers/i });
    expect(send()).toBeDisabled();
    click(screen.getByText('Relaxed pace'));
    expect(send()).toBeDisabled(); // second question unanswered
    click(screen.getByText('Solo'));
    expect(send()).not.toBeDisabled();
  });

  it('single-select replaces the previous choice', () => {
    render(<ClarifyCard data={twoQuestions} onSend={() => {}} />);
    click(screen.getByText('Relaxed pace'));
    expect(screen.getByText('Relaxed pace')).toHaveAttribute('aria-pressed', 'true');
    click(screen.getByText('Adventurous'));
    expect(screen.getByText('Adventurous')).toHaveAttribute('aria-pressed', 'true');
    // option buttons remount on selection change — re-query
    expect(screen.getByText('Relaxed pace')).toHaveAttribute('aria-pressed', 'false');
  });

  it('multi-select accumulates choices', () => {
    const multi: ClarifyData = {
      questions: [{
        field: 'dietary_restrictions',
        header: 'Dietary',
        question: 'Any dietary needs?',
        options: [{ label: 'Vegetarian' }, { label: 'Vegan' }],
        multi_select: true,
      }],
    };
    render(<ClarifyCard data={multi} onSend={() => {}} />);
    click(screen.getByText('Vegetarian'));
    click(screen.getByText('Vegan'));
    expect(screen.getByText('Vegetarian')).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByText('Vegan')).toHaveAttribute('aria-pressed', 'true');
  });

  it('Other input counts as an answer and is included in the composed text', () => {
    const onSend = vi.fn();
    const single: ClarifyData = { questions: [twoQuestions.questions[0]] };
    render(<ClarifyCard data={single} onSend={onSend} />);
    click(screen.getByText('Other'));
    fireEvent.change(screen.getByPlaceholderText(/type your own answer/i), {
      target: { value: 'Very fast' },
    });
    click(screen.getByRole('button', { name: /send answers/i }));
    expect(onSend).toHaveBeenCalledWith('Travel style: Very fast');
  });

  it('composes header: label per question', () => {
    const onSend = vi.fn();
    render(<ClarifyCard data={twoQuestions} onSend={onSend} />);
    click(screen.getByText('Adventurous'));
    click(screen.getByText('Friends'));
    click(screen.getByRole('button', { name: /send answers/i }));
    expect(onSend).toHaveBeenCalledWith('Travel style: Adventurous; Group: Friends');
  });
});
