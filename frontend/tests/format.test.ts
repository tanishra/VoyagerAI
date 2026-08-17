import { describe, it, expect } from 'vitest';
import { formatCurrency, formatNumber, getCurrencySymbol, CURRENCY_MAP } from '@/lib/format';

describe('formatCurrency', () => {
  it('formats USD for English locale', () => {
    const result = formatCurrency(1000, 'en');
    expect(result).toContain('1,000');
    expect(result).toMatch(/\$/);
  });

  it('formats EUR for Spanish locale', () => {
    const result = formatCurrency(1000, 'es');
    expect(result).toContain('1000');
    expect(result).toMatch(/€|EUR/);
  });

  it('formats JPY with no decimals for Japanese locale', () => {
    const result = formatCurrency(1000, 'ja');
    expect(result).not.toContain('.');
    expect(result).toContain('1,000');
  });

  it('formats INR for Hindi locale', () => {
    const result = formatCurrency(1000, 'hi');
    expect(result).toContain('1,000');
  });

  it('falls back to USD for unknown locale', () => {
    const result = formatCurrency(1000, 'en' as never);
    expect(result).toContain('1,000');
  });

  it('uses default locale when none provided', () => {
    const result = formatCurrency(500);
    expect(result).toContain('500');
  });
});

describe('formatNumber', () => {
  it('formats numbers with locale-specific grouping', () => {
    expect(formatNumber(1000000, 'en')).toBe('1,000,000');
    expect(formatNumber(1000000, 'de')).toBe('1.000.000');
  });
});

describe('getCurrencySymbol', () => {
  it('returns dollar sign for en', () => {
    const symbol = getCurrencySymbol('en');
    expect(symbol).toContain('$');
  });

  it('returns yen sign for ja', () => {
    const symbol = getCurrencySymbol('ja');
    expect(symbol).toMatch(/¥|￥|円/);
  });
});

describe('CURRENCY_MAP', () => {
  it('maps all supported locales', () => {
    expect(CURRENCY_MAP.en).toBe('USD');
    expect(CURRENCY_MAP.es).toBe('EUR');
    expect(CURRENCY_MAP.fr).toBe('EUR');
    expect(CURRENCY_MAP.de).toBe('EUR');
    expect(CURRENCY_MAP.hi).toBe('INR');
    expect(CURRENCY_MAP.ja).toBe('JPY');
  });
});

describe('formatCurrency snapshots per locale', () => {
  it('matches snapshot for en', () => {
    expect(formatCurrency(1500, 'en')).toMatchSnapshot();
  });
  it('matches snapshot for es', () => {
    expect(formatCurrency(1500, 'es')).toMatchSnapshot();
  });
  it('matches snapshot for fr', () => {
    expect(formatCurrency(1500, 'fr')).toMatchSnapshot();
  });
  it('matches snapshot for de', () => {
    expect(formatCurrency(1500, 'de')).toMatchSnapshot();
  });
  it('matches snapshot for hi', () => {
    expect(formatCurrency(1500, 'hi')).toMatchSnapshot();
  });
  it('matches snapshot for ja', () => {
    expect(formatCurrency(1500, 'ja')).toMatchSnapshot();
  });
});
