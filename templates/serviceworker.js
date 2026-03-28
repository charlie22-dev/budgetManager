const CACHE_NAME = 'budget-planner-v8';
const STATIC_ASSETS = [
    '/static/css/style.css?v=7'
];

self.addEventListener('install', event => {
    self.skipWaiting();
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS))
    );
});

self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cacheName => {
                    if (cacheName !== CACHE_NAME) {
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
});

self.addEventListener('fetch', event => {
    // Only handle GET requests
    if (event.request.method !== 'GET') return;

    // For navigation requests (HTML pages), hit the network first so data is dynamic
    if (event.request.mode === 'navigate') {
        event.respondWith(
            fetch(event.request).catch(() => {
                return caches.match(event.request).then(cachedResponse => {
                    if (cachedResponse) {
                        return cachedResponse;
                    }
                    return new Response('You are offline. Please reconnect to access TipidTracker.', {
                        status: 503,
                        statusText: 'Service Unavailable',
                        headers: new Headers({ 'Content-Type': 'text/plain' })
                    });
                });
            })
        );
    } else {
        // Cache-first for other assets
        event.respondWith(
            caches.match(event.request).then(response => {
                return response || fetch(event.request).catch(() => {
                    // Fail gracefully by returning a generic placeholder response instead of null
                    return new Response('', { 
                        status: 408, 
                        statusText: 'Request Timeout' 
                    });
                });
            })
        );
    }
});
