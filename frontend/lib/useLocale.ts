'use client';

import { useLocale as useNextIntlLocale } from 'next-intl';
import { locales, defaultLocale, type Locale } from '@/lib/i18n-config';

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
  const pathname = window.location.pathname;
  const segments = pathname.split('/');
  if (segments.length > 1 && locales.includes(segments[1] as Locale)) {
    segments[1] = locale;
    window.location.href = segments.join('/');
  } else {
    window.location.href = `/${locale}${pathname}`;
  }
}

export { locales, defaultLocale, type Locale };
