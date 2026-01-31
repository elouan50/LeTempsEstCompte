const CACHE_NAME = 'letempsestcompte-v3';
const ASSETS = [
    '/static/style.css',
    '/static/script.js',
    '/static/favicon.svg'
];

// Force immediate update
self.addEventListener('install', (event) => {
    self.skipWaiting();
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(ASSETS);
        })
    );
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        Promise.all([
            // Claim immediate control
            clients.claim(),
            // Clear old caches
            caches.keys().then((cacheNames) => {
                return Promise.all(
                    cacheNames.map((cacheName) => {
                        if (cacheName !== CACHE_NAME) {
                            return caches.delete(cacheName);
                        }
                    })
                );
            })
        ])
    );
});

self.addEventListener('fetch', (event) => {
    if (event.request.method !== 'GET') return;

    const url = new URL(event.request.url);

    // CRITICAL: Bypass cache for the root/metrics page entirely to fix language switching
    if (url.pathname === '/' || url.pathname === '/index') {
        event.respondWith(fetch(event.request));
        return;
    }

    // Cache-first for static assets
    event.respondWith(
        caches.match(event.request).then((response) => {
            if (response) return response;

            return fetch(event.request).then((fetchResponse) => {
                // Cache static folder contents
                if (url.pathname.startsWith('/static/') && fetchResponse.status === 200) {
                    const copy = fetchResponse.clone();
                    caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
                }
                return fetchResponse;
            });
        })
    );
});
