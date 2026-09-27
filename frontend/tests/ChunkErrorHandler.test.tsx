import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render } from '@testing-library/react';
import ChunkErrorHandler from '@/components/ChunkErrorHandler';

const reloadMock = vi.fn();

beforeEach(() => {
  reloadMock.mockClear();
  sessionStorage.clear();
  Object.defineProperty(window, 'location', {
    value: { ...window.location, reload: reloadMock },
    writable: true,
  });
});

describe('ChunkErrorHandler', () => {
  it('reloads once on a ChunkLoadError', () => {
    render(<ChunkErrorHandler />);
    const err = new Error('Loading chunk 123 failed');
    err.name = 'ChunkLoadError';
    window.dispatchEvent(new ErrorEvent('error', { error: err }));
    expect(reloadMock).toHaveBeenCalledTimes(1);
  });

  it('does not reload twice within the guard window', () => {
    render(<ChunkErrorHandler />);
    const err = new Error('Failed to fetch dynamically imported module');
    window.dispatchEvent(new ErrorEvent('error', { error: err }));
    window.dispatchEvent(new ErrorEvent('error', { error: err }));
    expect(reloadMock).toHaveBeenCalledTimes(1);
  });

  it('handles unhandledrejection with string reason', () => {
    render(<ChunkErrorHandler />);
    const event = new Event('unhandledrejection') as PromiseRejectionEvent;
    Object.assign(event, { reason: 'ChunkLoadError: timeout' });
    window.dispatchEvent(event);
    expect(reloadMock).toHaveBeenCalledTimes(1);
  });

  it('ignores unrelated errors', () => {
    render(<ChunkErrorHandler />);
    window.dispatchEvent(new ErrorEvent('error', { error: new Error('some other bug') }));
    expect(reloadMock).not.toHaveBeenCalled();
  });
});
