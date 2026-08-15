import { defaultLocale, type Locale } from '@/lib/i18n-config';

const CURRENCY_MAP: Record<Locale, string> = {
  en: 'USD',
  es: 'EUR',
  fr: 'EUR',
  de: 'EUR',
  hi: 'INR',
  ja: 'JPY',
};

export function formatCurrency(
  amount: number,
  locale: Locale = defaultLocale,
  options?: Intl.NumberFormatOptions,
): string {
  const currency = CURRENCY_MAP[locale] ?? 'USD';
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency,
    minimumFractionDigits: currency === 'JPY' ? 0 : 0,
    maximumFractionDigits: currency === 'JPY' ? 0 : 2,
    ...options,
  }).format(amount);
}

export function formatNumber(
  value: number,
  locale: Locale = defaultLocale,
  options?: Intl.NumberFormatOptions,
): string {
  return new Intl.NumberFormat(locale, options).format(value);
}

export function getCurrencySymbol(locale: Locale = defaultLocale): string {
  const currency = CURRENCY_MAP[locale] ?? 'USD';
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })
    .format(0)
    .replace(/\d/g, '')
    .trim();
}

export { CURRENCY_MAP };
