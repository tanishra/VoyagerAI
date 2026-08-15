import { getRequestConfig } from 'next-intl/server';
import { headers } from 'next/headers';

export { locales, defaultLocale, localeNames, localeFlags } from './lib/i18n-config';
export type { Locale } from './lib/i18n-config';

import { locales, defaultLocale } from './lib/i18n-config';
import type { Locale } from './lib/i18n-config';

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

export default getRequestConfig(async ({ requestLocale }) => {
  const requested = await requestLocale;
  let locale = requested as Locale | undefined;

  if (!locale || !locales.includes(locale)) {
    const headerList = await headers();
    const cookieHeader = headerList.get('cookie') ?? '';
    const cookieLocale = cookieHeader
      .split(';')
      .map((c) => c.trim())
      .find((c) => c.startsWith('NEXT_LOCALE='))
      ?.split('=')[1] as Locale | undefined;

    if (cookieLocale && locales.includes(cookieLocale)) {
      locale = cookieLocale;
    } else {
      const acceptLang = headerList.get('accept-language');
      locale = parseAcceptLanguage(acceptLang) ?? defaultLocale;
    }
  }

  return {
    locale,
    messages: (await import(`./messages/${locale}.json`)).default,
  };
});
