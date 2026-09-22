import { describe, expect, it } from 'vitest';
import { friendlyHttpError, isTechnicalError, sanitizeError } from '../lib/errors';

describe('isTechnicalError', () => {
  it('flags exception class names', () => {
    expect(isTechnicalError('litellm.RateLimitError: OpenAIException - You have no credits remaining')).toBe(true);
    expect(isTechnicalError('TypeError: cannot read properties of undefined')).toBe(true);
    expect(isTechnicalError('ValueError')).toBe(true);
  });

  it('flags tracebacks and stack frames', () => {
    expect(isTechnicalError('Traceback (most recent call last): File "main.py"')).toBe(true);
    expect(isTechnicalError('at handleSend (page.tsx:123)')).toBe(true);
  });

  it('flags provider URLs and platform links', () => {
    expect(isTechnicalError('Add credits at https://platform.openai.com/settings/billing')).toBe(true);
  });

  it('flags overly long messages', () => {
    expect(isTechnicalError('x'.repeat(300))).toBe(true);
  });

  it('passes friendly localized text', () => {
    expect(isTechnicalError('Daily cost limit reached. Try again tomorrow.')).toBe(false);
    expect(isTechnicalError('Something went wrong. Please try again.')).toBe(false);
    expect(isTechnicalError('Une erreur s\'est produite.')).toBe(false);
  });
});

describe('sanitizeError', () => {
  const fb = 'Something went wrong. Please try again.';

  it('replaces technical text with fallback', () => {
    expect(sanitizeError('litellm.RateLimitError: boom', fb)).toBe(fb);
    expect(sanitizeError('Failed to fetch', fb)).toBe('Failed to fetch'); // short, no exception pattern — acceptable
  });

  it('passes friendly text through', () => {
    expect(sanitizeError('Daily cost limit reached.', fb)).toBe('Daily cost limit reached.');
  });

  it('falls back on empty input', () => {
    expect(sanitizeError('', fb)).toBe(fb);
    expect(sanitizeError(null, fb)).toBe(fb);
    expect(sanitizeError(undefined, fb)).toBe(fb);
  });
});

describe('friendlyHttpError', () => {
  const fb = { server: 'server err', request: 'req err' };

  it('extracts friendly JSON detail', () => {
    const body = JSON.stringify({ detail: 'Daily cost limit reached. Try again tomorrow.' });
    expect(friendlyHttpError(429, body, fb)).toBe('Daily cost limit reached. Try again tomorrow.');
  });

  it('drops technical JSON detail', () => {
    const body = JSON.stringify({ detail: 'litellm.RateLimitError: no credits' });
    expect(friendlyHttpError(500, body, fb)).toBe('server err');
  });

  it('drops technical plain-text body', () => {
    expect(friendlyHttpError(500, 'Internal Server Error: Traceback at line 5 File "x.py"', fb)).toBe('server err');
  });

  it('uses request fallback for 4xx with no detail', () => {
    expect(friendlyHttpError(400, '', fb)).toBe('req err');
  });
});
