// ULTRON: let the browser HTTP cache reuse static assets between launches.
// HTML and API responses remain revalidated/no-store by the server.
self.addEventListener("install", event => {
  event.waitUntil(self.skipWaiting());
});
self.addEventListener("activate", event => {
  event.waitUntil(self.clients.claim());
});
self.addEventListener("fetch", event => {
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin || event.request.method !== "GET") return;
  // Static assets carry explicit cache headers; API routes remain no-store.
  event.respondWith(fetch(event.request));
});
