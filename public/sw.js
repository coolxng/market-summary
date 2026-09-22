// The Daily Tape service worker.
//
// Freshness beats offline reading for market data, so this worker:
// - never caches HTML pages or JSON snapshots; navigations always go to the
//   network, and only fall back to a static "you're offline" page;
// - caches only content-hashed build assets and brand icons, which never
//   change under the same URL.
const VERSION = "daily-tape-v2";
const SCOPE = new URL(self.registration.scope).pathname;
const OFFLINE_URL = `${SCOPE}offline.html`;
const PRECACHE = [OFFLINE_URL, `${SCOPE}icon-192.png`, `${SCOPE}logo.png`];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(VERSION).then((cache) => cache.addAll(PRECACHE)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  // Removes v1, which cached full pages and could show stale market data offline.
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== VERSION).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

function isImmutableAsset(url) {
  return url.pathname.startsWith(`${SCOPE}_next/static/`) || /\/(icon-\d+|icon-maskable-\d+|logo|favicon-[\w-]+|apple-touch-icon)\.(png|svg)$/.test(url.pathname);
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === "navigate") {
    // Revalidate every page view so a newly published issue shows at once.
    event.respondWith(fetch(request, { cache: "no-cache" }).catch(() => caches.match(OFFLINE_URL)));
    return;
  }

  if (isImmutableAsset(url)) {
    event.respondWith(
      caches.match(request).then((cached) => cached || fetch(request).then((response) => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(VERSION).then((cache) => cache.put(request, copy));
        }
        return response;
      })),
    );
  }
  // Everything else (report JSON, feeds, pages' data) goes straight to the network.
});
