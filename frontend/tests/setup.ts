import '@testing-library/jest-dom/vitest';
import React from 'react';
import { vi } from 'vitest';

class MockIntersectionObserver {
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
}

Object.defineProperty(window, 'IntersectionObserver', {
  writable: true,
  configurable: true,
  value: MockIntersectionObserver,
});

vi.mock('next/navigation', () => ({
  usePathname: () => '/',
}));

vi.mock('next-intl', async () => {
  const en = (await import('../messages/en.json')).default;
  const { vi } = await import('vitest');

  function getNestedValue(obj: Record<string, unknown>, path: string): unknown {
    const parts = path.split('.');
    let current: unknown = obj;
    for (const part of parts) {
      if (current && typeof current === 'object' && part in current) {
        current = (current as Record<string, unknown>)[part];
      } else {
        return undefined;
      }
    }
    return current;
  }

  function interpolate(str: string, values?: Record<string, unknown>): string {
    if (!values) return str;
    return str.replace(/\{(\w+)\}/g, (_, key: string) =>
      key in values ? String(values[key]) : `{${key}}`,
    );
  }

  const useTranslations = (namespace?: string) => {
    return (key: string, values?: Record<string, unknown>) => {
      const fullKey = namespace ? `${namespace}.${key}` : key;
      const val = getNestedValue(en, fullKey);
      if (typeof val === 'string') {
        return interpolate(val, values);
      }
      return key;
    };
  };

  const useLocale = () => 'en';

  return {
    useTranslations,
    useLocale,
    NextIntlClientProvider: ({ children }: { children: React.ReactNode }) =>
      React.createElement(React.Fragment, null, children),
  };
});

vi.mock('@/lib/useLocale', async () => {
  const { vi } = await import('vitest');
  return {
    useLocale: () => 'en',
    setLocale: vi.fn(),
    locales: ['en', 'es', 'fr', 'de', 'hi', 'ja'],
    defaultLocale: 'en',
  };
});

vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { children?: React.ReactNode }) =>
    React.createElement('a', { href, ...props }, children),
}));

vi.mock('framer-motion', () => {
  const makeMotion = (tag: string) => {
    const Component: React.FC<{ children?: React.ReactNode } & Record<string, unknown>> = ({ children, ...props }) =>
      React.createElement(tag, props as React.HTMLAttributes<HTMLElement>, children);
    Component.displayName = `MockMotion.${tag}`;
    return Component;
  };

  return {
    motion: new Proxy(
      {},
      {
        get: (_target, prop) => {
          if (typeof prop === 'string') {
            return makeMotion(prop);
          }
          return undefined;
        },
      },
    ),
    AnimatePresence: ({ children }: { children?: React.ReactNode }) => React.createElement(React.Fragment, null, children),
    useScroll: () => ({ scrollYProgress: { on: () => {} } }),
    useSpring: () => ({ set: () => {} }),
    useAnimation: () => ({ start: () => {}, set: () => {} }),
    useMotionValue: (initial: number) => ({ get: () => initial, set: () => {} }),
    useTransform: () => ({ get: () => 0 }),
    useInView: () => true,
  };
});
