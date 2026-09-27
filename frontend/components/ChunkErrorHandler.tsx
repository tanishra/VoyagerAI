'use client';

import { useEffect } from 'react';

const RELOAD_TS_KEY = 'voyager-chunk-reload-ts';
const MIN_RELOAD_INTERVAL_MS = 60_000;

const CHUNK_ERROR_PATTERNS = [
  'ChunkLoadError',
  'Loading chunk',
  'Failed to fetch dynamically imported module',
  'error loading dynamically imported module',
  'Importing a module script failed',
];

function isChunkError(reason: unknown): boolean {
  const text =
    typeof reason === 'string'
      ? reason
      : reason instanceof Error
        ? `${reason.name} ${reason.message}`
        : String(reason ?? '');
  return CHUNK_ERROR_PATTERNS.some((p) => text.includes(p));
}

/**
 * Self-heal for stale-chunk crashes: after a deploy, a cached document can
 * reference JS chunks that no longer exist. Instead of a dead white screen,
 * reload to pick up fresh HTML. A timestamp guard caps it at one reload per
 * 60s so a persistently broken deploy can't loop.
 */
export default function ChunkErrorHandler() {
  useEffect(() => {
    const maybeReload = (reason: unknown) => {
      if (!isChunkError(reason)) return;
      try {
        const last = Number(sessionStorage.getItem(RELOAD_TS_KEY) ?? 0);
        if (Date.now() - last < MIN_RELOAD_INTERVAL_MS) return;
        sessionStorage.setItem(RELOAD_TS_KEY, String(Date.now()));
      } catch {
        // storage unavailable — still attempt the reload
      }
      window.location.reload();
    };

    const onError = (event: ErrorEvent) => maybeReload(event.error ?? event.message);
    const onRejection = (event: PromiseRejectionEvent) => maybeReload(event.reason);

    window.addEventListener('error', onError);
    window.addEventListener('unhandledrejection', onRejection);
    return () => {
      window.removeEventListener('error', onError);
      window.removeEventListener('unhandledrejection', onRejection);
    };
  }, []);

  return null;
}
