// Obsidian Labs Dashboard - minimal offline app-shell cache.
// Caches the static shell (HTML/CSS/JS/icons) so the dashboard opens instantly and
// works if briefly offline. Does NOT cache API responses from fastapi_backend - live
// data always comes from the network.
const CACHE_NAME = "obsidian-labs-shell-v2";
const SHELL_FILES = [
  "tesla_style_dashboard_v2.html",
  "tesla_style_dashboard_with_chat.html",
  "manifest.json",
  "icon-192.png",
  "icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_FILES))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  // Never cache backend/API calls - always go straight to the network. The backend
  // can be localhost:8502, an ngrok URL, or anything else set in Settings, so the
  // safest check is "not the same origin this dashboard was served from."
  if (url.origin !== self.location.origin || url.pathname.startsWith("/api/")) {
    return;
  }
  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request))
  );
});
