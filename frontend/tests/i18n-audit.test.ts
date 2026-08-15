import { describe, it, expect } from 'vitest';
import en from '../messages/en.json';
import es from '../messages/es.json';
import fr from '../messages/fr.json';
import de from '../messages/de.json';
import hi from '../messages/hi.json';
import ja from '../messages/ja.json';

const locales = { en, es, fr, de, hi, ja };

function flattenKeys(obj: Record<string, unknown>, prefix = ''): Set<string> {
  const keys = new Set<string>();
  for (const [key, value] of Object.entries(obj)) {
    const fullKey = prefix ? `${prefix}.${key}` : key;
    if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
      for (const k of flattenKeys(value as Record<string, unknown>, fullKey)) {
        keys.add(k);
      }
    } else {
      keys.add(fullKey);
    }
  }
  return keys;
}

describe('i18n translation completeness audit', () => {
  const enKeys = flattenKeys(en);

  Object.entries(locales).forEach(([locale, catalog]) => {
    if (locale === 'en') return;

    it(`${locale} has identical key set to en (${enKeys.size} keys)`, () => {
      const localeKeys = flattenKeys(catalog);
      const missing = [...enKeys].filter((k) => !localeKeys.has(k));
      const extra = [...localeKeys].filter((k) => !enKeys.has(k));
      expect(missing, `Missing keys in ${locale}: ${missing.join(', ')}`).toEqual([]);
      expect(extra, `Extra keys in ${locale}: ${extra.join(', ')}`).toEqual([]);
    });
  });

  it('en catalog has at least 100 keys (sanity check)', () => {
    expect(enKeys.size).toBeGreaterThanOrEqual(100);
  });
});
