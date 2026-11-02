// ULTRON V7.0: do not cache the live assistant interface.
// The previous service worker cached the old mobile GUI and kept serving it
// after the HTML/CSS/JS had been updated.
self.addEventListener("install", event => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", event => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.map(key => caches.delete(key)));
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", event => {
  // Always fetch the current UI and API from the local ULTRON server.
  // Do not intercept or serve stale cached files.
  if (new URL(event.request.url).origin === self.location.origin) {
    event.respondWith(fetch(event.request, { cache: "no-store" }));
  }
});
