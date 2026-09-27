// VoyagerAI service worker — hand-maintained.
// next-pwa (workbox) does not run under Next.js Turbopack builds, so this file
// is written manually instead of being generated.
//
// Strategy:
//  - install/activate: claim clients immediately and DELETE every stale cache
//    left by older workers (this is what un-breaks devices pinned to the old
//    generated sw.js from Aug-2026 builds).
//  - fetch: cache-first ONLY for immutable same-origin static assets
//    (/_next/static chunks are content-hashed, plus icons/manifest/images).
//    Pages, RSC payloads and API calls are NEVER cached — they always hit the
//    network, so a deploy can never serve HTML referencing deleted chunks.
const ASSET_CACHE = 'voyager-assets-v1';
const CACHEABLE_PATH = /^\/(_next\/static|destinations)\/|^\/(icon-\d+\.png|manifest\.json|favicon\.ico)$/;

self.addEventListener('install', () => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== ASSET_CACHE).map((k) => caches.delete(k)))
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (!CACHEABLE_PATH.test(url.pathname)) return;

  event.respondWith(
    caches.match(req).then(
      (hit) =>
        hit ||
        fetch(req).then((res) => {
          if (res.ok) {
            const clone = res.clone();
            caches.open(ASSET_CACHE).then((cache) => cache.put(req, clone));
          }
          return res;
        })
    )
  );
});
