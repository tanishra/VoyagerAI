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
  };
});
