const CACHE_NAME = "vit-signal-cache-v1";

// Everything needed to load the app offline
const ASSETS_TO_CACHE = [
    "/",
    "/upload",
    "/static/main.js",
    "/static/upload.js",
    "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css",
    "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js",
    "https://unpkg.com/leaflet.heat/dist/leaflet-heat.js",
    "https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.6.1/socket.io.min.js"
];

// 1. Install & Cache assets
self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(ASSETS_TO_CACHE);
        })
    );
    self.skipWaiting();
});

// 2. Clean up old caches on update
self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((keys) => Promise.all(
            keys.map((key) => {
                if (key !== CACHE_NAME) return caches.delete(key);
            })
        ))
    );
    self.clients.claim();
});

// 3. Intercept requests and serve from Cache first, then Network
self.addEventListener("fetch", (event) => {
    const url = event.request.url;

    // Do NOT cache API calls or WebSockets — let them fail so your upload.js offline queue takes over
    if (url.includes("/api/") || url.includes("/socket.io/")) return;

    event.respondWith(
        caches.match(event.request).then((cachedResponse) => {
            // Return the cached asset if we have it
            if (cachedResponse) return cachedResponse;

            // Otherwise, try fetching from the network
            return fetch(event.request).catch(() => {
                // If the network is totally dead and they asked for a page, route them to /upload
                if (event.request.mode === "navigate") {
                    return caches.match("/upload");
                }
            });
        })
    );
});