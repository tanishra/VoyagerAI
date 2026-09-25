import { describe, it, expect } from 'vitest';
import { stripStructuredTags } from '@/lib/utils';

describe('stripStructuredTags', () => {
  it('strips complete comparison and itinerary blocks', () => {
    const text = 'Intro <comparison>{"plans":[]}</comparison> outro <itinerary>{"days":[]}</itinerary> end';
    const result = stripStructuredTags(text);
    expect(result).toBe('Intro  outro  end');
  });

  it('strips partial tags during streaming', () => {
    const text = 'Intro <comparison>{"plans":[{"tier":"budg';
    expect(stripStructuredTags(text)).toBe('Intro');
  });

  it('truncates untagged multi-tier plan prose at the first tier header', () => {
    const text = [
      'Here are three itinerary options for your 5-day trip to Tokyo:',
      'Budget Plan',
      '- Total Cost: ₹45,000',
      '- Accommodation: Hostel',
      'Balanced Plan',
      '- Total Cost: ₹75,000',
      'Premium Plan',
      '- Total Cost: ₹1,12,500',
      'Which tier do you prefer?',
    ].join('\n');
    const result = stripStructuredTags(text);
    expect(result).not.toContain('Total Cost');
    expect(result).not.toContain('Premium Plan');
    expect(result).toContain('Tokyo');
  });

  it('leaves single-tier mentions untouched', () => {
    const text = 'The Budget Plan would be cheapest for you.';
    expect(stripStructuredTags(text)).toBe(text);
  });

  it('strips clarify_answers blocks from user messages', () => {
    const text = 'Destination: Delhi; Trip length: 3 days\n<clarify_answers>{"destination":"delhi","total_days":"3"}</clarify_answers>';
    expect(stripStructuredTags(text)).toBe('Destination: Delhi; Trip length: 3 days');
  });

  it('returns plain text unchanged', () => {
    const text = 'Just a normal chat reply about Tokyo.';
    expect(stripStructuredTags(text)).toBe(text);
  });
});
