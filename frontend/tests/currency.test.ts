import { describe, it, expect, vi } from 'vitest';

// Unmock @/lib/currency for this test file — we need the real implementation
vi.unmock('@/lib/currency');

import {
  SUPPORTED_CURRENCIES,
  CURRENCY_SYMBOLS,
  CURRENCY_NAMES,
  getDefaultCurrencyForLocale,
  setStoredCurrency,
  getStoredCurrency,
  getEffectiveCurrency,
} from '@/lib/currency';

describe('currency constants', () => {
  it('includes USD, INR, EUR, JPY, GBP, AUD', () => {
    expect(SUPPORTED_CURRENCIES).toContain('USD');
    expect(SUPPORTED_CURRENCIES).toContain('INR');
    expect(SUPPORTED_CURRENCIES).toContain('EUR');
    expect(SUPPORTED_CURRENCIES).toContain('JPY');
    expect(SUPPORTED_CURRENCIES).toContain('GBP');
    expect(SUPPORTED_CURRENCIES).toContain('AUD');
  });

  it('has symbols for all currencies', () => {
    for (const c of SUPPORTED_CURRENCIES) {
      expect(CURRENCY_SYMBOLS[c]).toBeTruthy();
    }
  });

  it('has names for all currencies', () => {
    for (const c of SUPPORTED_CURRENCIES) {
      expect(CURRENCY_NAMES[c]).toBeTruthy();
    }
  });
});

describe('getDefaultCurrencyForLocale', () => {
  it('returns USD for en', () => {
    expect(getDefaultCurrencyForLocale('en')).toBe('USD');
  });

  it('returns INR for hi', () => {
    expect(getDefaultCurrencyForLocale('hi')).toBe('INR');
  });

  it('returns JPY for ja', () => {
    expect(getDefaultCurrencyForLocale('ja')).toBe('JPY');
  });

  it('returns EUR for es, fr, de', () => {
    expect(getDefaultCurrencyForLocale('es')).toBe('EUR');
    expect(getDefaultCurrencyForLocale('fr')).toBe('EUR');
    expect(getDefaultCurrencyForLocale('de')).toBe('EUR');
  });
});

describe('stored currency', () => {
  it('setStoredCurrency writes to cookie and localStorage', () => {
    setStoredCurrency('INR');
    expect(getStoredCurrency()).toBe('INR');
  });

  it('getStoredCurrency returns null when nothing stored', () => {
    document.cookie = 'VOYAGER_CURRENCY=;max-age=0';
    try { localStorage.removeItem('VOYAGER_CURRENCY'); } catch { /* */ }
    expect(getStoredCurrency()).toBeNull();
  });

  it('getEffectiveCurrency falls back to locale default', () => {
    document.cookie = 'VOYAGER_CURRENCY=;max-age=0';
    try { localStorage.removeItem('VOYAGER_CURRENCY'); } catch { /* */ }
    expect(getEffectiveCurrency('hi')).toBe('INR');
    expect(getEffectiveCurrency('en')).toBe('USD');
  });

  it('getEffectiveCurrency uses stored currency when available', () => {
    setStoredCurrency('EUR');
    expect(getEffectiveCurrency('en')).toBe('EUR');
    // cleanup
    document.cookie = 'VOYAGER_CURRENCY=;max-age=0';
    try { localStorage.removeItem('VOYAGER_CURRENCY'); } catch { /* */ }
  });
});
