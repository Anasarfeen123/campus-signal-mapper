const CACHE_NAME = "vit-signal-cache-v2"; // ← bumped from v1 to force fresh install

// Everything needed to load the app offline
const ASSETS_TO_CACHE = [
    "/",
    "/upload",
    "/static/main.js",
    "/static/upload.js",
    "/static/i18n.js",   // ← added
    "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css",
    "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js",
    "https://unpkg.com/leaflet.heat/dist/leaflet-heat.js",
    "https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.6.1/socket.io.min.js",
    "https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"  // ← added
];

// 1. Install & Cache assets
self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(ASSETS_TO_CACHE);
        })
    );
    self.skipWaiting(); // activate immediately, don't wait for old tabs to close
});

// 2. Clean up old caches on update
self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((keys) => Promise.all(
            keys.map((key) => {
                if (key !== CACHE_NAME) return caches.delete(key); // deletes v1
            })
        ))
    );
    self.clients.claim(); // take control of all open tabs immediately
});

// 3. Network-first for HTML pages (always get fresh templates from server)
//    Cache-first for static assets (JS, CSS, map tiles)
self.addEventListener("fetch", (event) => {
    const url = event.request.url;

    // Never intercept API calls or WebSockets
    if (url.includes("/api/") || url.includes("/socket.io/")) return;

    // Network-first for HTML navigation (so updated templates are always seen)
    if (event.request.mode === "navigate") {
        event.respondWith(
            fetch(event.request).catch(() => caches.match(event.request))
        );
        return;
    }

    // Cache-first for static assets
    event.respondWith(
        caches.match(event.request).then((cachedResponse) => {
            if (cachedResponse) return cachedResponse;
            return fetch(event.request).catch(() => undefined);
        })
    );
});