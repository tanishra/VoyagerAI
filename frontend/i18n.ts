import { getRequestConfig } from 'next-intl/server';
import { headers } from 'next/headers';

export const locales = ['en', 'es', 'fr', 'de', 'hi', 'ja'] as const;
export type Locale = (typeof locales)[number];
export const defaultLocale: Locale = 'en';

export const localeNames: Record<Locale, string> = {
  en: 'English',
  es: 'Spanish',
  fr: 'French',
  de: 'German',
  hi: 'Hindi',
  ja: 'Japanese',
};

export const localeFlags: Record<Locale, string> = {
  en: '🇺🇸',
  es: '🇪🇸',
  fr: '🇫🇷',
  de: '🇩🇪',
  hi: '🇮🇳',
  ja: '🇯🇵',
};

function parseAcceptLanguage(header: string | null): Locale | null {
  if (!header) return null;
  const preferred = header
    .split(',')
    .map((part) => {
      const [lang, q] = part.trim().split(';q=');
      return { lang: lang.trim().toLowerCase(), q: q ? parseFloat(q) : 1 };
    })
    .sort((a, b) => b.q - a.q);

  for (const { lang } of preferred) {
    const match = locales.find((l) => lang === l || lang.startsWith(l + '-'));
    if (match) return match;
  }
  return null;
}

export default getRequestConfig(async () => {
  const headerList = await headers();
  const cookieHeader = headerList.get('cookie') ?? '';
  const cookieLocale = cookieHeader
    .split(';')
    .map((c) => c.trim())
    .find((c) => c.startsWith('NEXT_LOCALE='))
    ?.split('=')[1] as Locale | undefined;

  const acceptLang = headerList.get('accept-language');
  const locale = cookieLocale ?? parseAcceptLanguage(acceptLang) ?? defaultLocale;

  return {
    locale,
    messages: (await import(`./messages/${locale}.json`)).default,
  };
});
