'use client';

import { useLocale as useNextIntlLocale } from 'next-intl';
import { locales, defaultLocale, type Locale } from '@/i18n';

export function useLocale(): Locale {
  const locale = useNextIntlLocale();
  return (locales as readonly string[]).includes(locale) ? (locale as Locale) : defaultLocale;
}

export function setLocale(locale: Locale) {
  document.cookie = `NEXT_LOCALE=${locale};path=/;max-age=31536000;SameSite=Lax`;
  try {
    localStorage.setItem('NEXT_LOCALE', locale);
  } catch {
    // localStorage unavailable
  }
  window.location.reload();
}

export { locales, defaultLocale, type Locale };
