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
  it('renders one question per tab with switchable chips', () => {
    render(<ClarifyCard data={twoQuestions} onSend={() => {}} />);
    // first question active; second lives on its own tab
    expect(screen.getByText('What pace do you prefer?')).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Group' })).toBeInTheDocument();
    expect(screen.getByText('Relaxed pace')).toBeInTheDocument(); // enum label localized
    expect(screen.getAllByText('Other')).toHaveLength(1);
    // switch to second question via its tab
    click(screen.getByRole('tab', { name: 'Group' }));
    expect(screen.getByText('Who is travelling?')).toBeInTheDocument();
  });

  it('Send disabled until every question answered', () => {
    render(<ClarifyCard data={twoQuestions} onSend={() => {}} />);
    const send = () => screen.getByRole('button', { name: /send answers/i });
    expect(send()).toBeDisabled();
    click(screen.getByText('Relaxed pace')); // auto-advances to Q2
    expect(send()).toBeDisabled(); // second question unanswered
    click(screen.getByText('Solo'));
    expect(send()).not.toBeDisabled();
  });

  it('single-select replaces the previous choice', () => {
    render(<ClarifyCard data={twoQuestions} onSend={() => {}} />);
    click(screen.getByText('Relaxed pace')); // auto-advances to Q2
    click(screen.getByRole('tab', { name: 'Travel style' })); // back to Q1
    click(screen.getByText('Adventurous'));
    click(screen.getByRole('tab', { name: 'Travel style' }));
    expect(screen.getByText('Adventurous').closest('button')).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByText('Relaxed pace').closest('button')).toHaveAttribute('aria-pressed', 'false');
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
    expect(screen.getByText('Vegetarian').closest('button')).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByText('Vegan').closest('button')).toHaveAttribute('aria-pressed', 'true');
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
    expect(onSend).toHaveBeenCalledWith('Travel style: Very fast\n<clarify_answers>{"travel_style":"Very fast"}</clarify_answers>');
  });

  it('composes header: label per question', () => {
    const onSend = vi.fn();
    render(<ClarifyCard data={twoQuestions} onSend={onSend} />);
    click(screen.getByText('Adventurous')); // auto-advances to Q2
    click(screen.getByText('Friends'));
    click(screen.getByRole('button', { name: /send answers/i }));
    expect(onSend).toHaveBeenCalledWith('Travel style: Adventurous; Group: Friends\n<clarify_answers>{"travel_style":"adventurous","group_type":"friends"}</clarify_answers>');
  });
});

describe('ClarifyCard keyboard nav', () => {
  const key = (k: string) => act(() => { fireEvent.keyDown(document.activeElement ?? document.body, { key: k }); });

  it('number key selects option and auto-advances', () => {
    render(<ClarifyCard data={twoQuestions} onSend={() => {}} />);
    key('1'); // picks option 1 of Q1 → jumps to Q2
    expect(screen.getByText('Who is travelling?')).toBeInTheDocument();
    click(screen.getByRole('tab', { name: 'Travel style' }));
    expect(screen.getByText('Relaxed pace').closest('button')).toHaveAttribute('aria-pressed', 'true');
  });

  it('arrows move focus, Enter selects', () => {
    render(<ClarifyCard data={twoQuestions} onSend={() => {}} />);
    key('ArrowDown');
    key('Enter'); // selects option 2 (Adventurous) → auto-advances to Q2
    expect(screen.getByText('Who is travelling?')).toBeInTheDocument();
    click(screen.getByRole('tab', { name: 'Travel style' }));
    expect(screen.getByText('Adventurous').closest('button')).toHaveAttribute('aria-pressed', 'true');
  });

  it('left/right arrows switch question tabs', () => {
    render(<ClarifyCard data={twoQuestions} onSend={() => {}} />);
    key('ArrowRight');
    expect(screen.getByText('Who is travelling?')).toBeInTheDocument();
    key('ArrowLeft');
    expect(screen.getByText('What pace do you prefer?')).toBeInTheDocument();
  });

  it('Enter submits when all questions answered', () => {
    const onSend = vi.fn();
    render(<ClarifyCard data={twoQuestions} onSend={onSend} />);
    key('1'); // Q1 → auto-advance
    key('1'); // Q2 → all answered
    key('Enter');
    expect(onSend).toHaveBeenCalledWith('Travel style: Relaxed pace; Group: Solo\n<clarify_answers>{"travel_style":"relaxed","group_type":"solo"}</clarify_answers>');
  });

  it('typing a letter opens Other and seeds the input', () => {
    render(<ClarifyCard data={{ questions: [twoQuestions.questions[0]] }} onSend={() => {}} />);
    key('x');
    const input = screen.getByPlaceholderText(/type your own answer/i);
    expect(input).toHaveValue('x');
    expect(document.activeElement).toBe(input);
  });
});
