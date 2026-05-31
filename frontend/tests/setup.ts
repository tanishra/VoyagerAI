import '@testing-library/jest-dom/vitest';
import React from 'react';
import { vi } from 'vitest';

vi.mock('framer-motion', () => ({
  motion: new Proxy(
    {},
    {
      get: (_target, prop) => {
        if (typeof prop === 'string') {
          return ({ children, ...props }: any) => {
            const {
              initial,
              animate,
              exit,
              transition,
              variants,
              custom,
              whileInView,
              whileHover,
              whileTap,
              onAnimationComplete,
              layout,
              layoutId,
              ...rest
            } = props;
            return React.createElement(prop, rest, children);
          };
        }
        return undefined;
      },
    }
  ),
  AnimatePresence: ({ children }: any) => React.createElement(React.Fragment, null, children),
  useScroll: () => ({ scrollYProgress: { on: () => {} } }),
  useSpring: () => ({ set: () => {} }),
  useAnimation: () => ({ start: () => {}, set: () => {} }),
  useMotionValue: (initial: any) => ({ get: () => initial, set: () => {} }),
  useTransform: () => ({ get: () => 0 }),
}));
