'use client';

import { useEffect } from 'react';

/**
 * Registers the service worker in production and reloads once when an updated
 * worker takes control — guarantees the page's HTML matches the chunk set the
 * new worker was built for. First installs (no existing controller) do not
 * reload.
 */
export default function ServiceWorkerRegister() {
  useEffect(() => {
    if (process.env.NODE_ENV !== 'production') return;
    if (!navigator.serviceWorker) return;

    const hadController = Boolean(navigator.serviceWorker.controller);
    let reloading = false;
    const onControllerChange = () => {
      if (reloading) return;
      reloading = true;
      window.location.reload();
    };

    navigator.serviceWorker.register('/sw.js').catch(() => {
      // Registration failure must never break the page.
    });
    if (hadController) {
      navigator.serviceWorker.addEventListener('controllerchange', onControllerChange);
    }
    return () => {
      navigator.serviceWorker.removeEventListener('controllerchange', onControllerChange);
    };
  }, []);

  return null;
}
