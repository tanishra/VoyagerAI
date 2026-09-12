import type { Locale } from '@/lib/i18n-config';

export const SUPPORTED_CURRENCIES = ['USD', 'INR', 'EUR', 'JPY', 'GBP', 'AUD'] as const;
export type Currency = (typeof SUPPORTED_CURRENCIES)[number];

export const CURRENCY_SYMBOLS: Record<Currency, string> = {
  USD: '$',
  INR: '₹',
  EUR: '€',
  JPY: '¥',
  GBP: '£',
  AUD: 'A$',
};

export const CURRENCY_NAMES: Record<Currency, string> = {
  USD: 'US Dollar',
  INR: 'Indian Rupee',
  EUR: 'Euro',
  JPY: 'Japanese Yen',
  GBP: 'British Pound',
  AUD: 'Australian Dollar',
};

const LOCALE_CURRENCY_DEFAULT: Record<Locale, Currency> = {
  en: 'USD',
  es: 'EUR',
  fr: 'EUR',
  de: 'EUR',
  hi: 'INR',
  ja: 'JPY',
};

const STORAGE_KEY = 'VOYAGER_CURRENCY';
const COOKIE_KEY = 'VOYAGER_CURRENCY';

export function getDefaultCurrencyForLocale(locale: Locale): Currency {
  return LOCALE_CURRENCY_DEFAULT[locale] ?? 'USD';
}

export function getStoredCurrency(): Currency | null {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(new RegExp(`${COOKIE_KEY}=([^;]+)`));
  if (match) {
    const val = match[1] as Currency;
    if (SUPPORTED_CURRENCIES.includes(val)) return val;
  }
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored && SUPPORTED_CURRENCIES.includes(stored as Currency)) {
      return stored as Currency;
    }
  } catch {
    // localStorage unavailable
  }
  return null;
}

export function setStoredCurrency(currency: Currency): void {
  document.cookie = `${COOKIE_KEY}=${currency};path=/;max-age=31536000;SameSite=Lax`;
  try {
    localStorage.setItem(STORAGE_KEY, currency);
  } catch {
    // localStorage unavailable
  }
}

export function getEffectiveCurrency(locale: Locale): Currency {
  return getStoredCurrency() ?? getDefaultCurrencyForLocale(locale);
}
