import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render } from '@testing-library/react';
import ServiceWorkerRegister from '@/components/ServiceWorkerRegister';

const registerMock = vi.fn().mockResolvedValue({});

function stubServiceWorker(controller: unknown = { scriptURL: '/sw.js' }) {
  Object.defineProperty(navigator, 'serviceWorker', {
    value: {
      controller,
      register: registerMock,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    },
    configurable: true,
  });
}

describe('ServiceWorkerRegister', () => {
  beforeEach(() => {
    registerMock.mockClear();
    vi.stubEnv('NODE_ENV', 'production');
  });

  it('registers /sw.js in production', () => {
    stubServiceWorker();
    render(<ServiceWorkerRegister />);
    expect(registerMock).toHaveBeenCalledWith('/sw.js');
  });

  it('swallows registration failure', async () => {
    registerMock.mockRejectedValueOnce(new Error('denied'));
    stubServiceWorker();
    expect(() => render(<ServiceWorkerRegister />)).not.toThrow();
  });

  it('does nothing when serviceWorker unsupported', () => {
    Object.defineProperty(navigator, 'serviceWorker', {
      value: undefined,
      configurable: true,
    });
    expect(() => render(<ServiceWorkerRegister />)).not.toThrow();
  });
});
