const CACHE_NAME = 'aura-v1';
const OFFLINE_URL = '/offline';

const urlsToCache = [
    '/static/style.css',
    '/static/manifest.json',
    '/static/icons/icon-192.png',
    '/static/icons/icon-512.png'
];

// ============ INSTALL ============
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            return cache.addAll(urlsToCache).catch(err => {
                console.log('Кэш ошибка:', err);
            });
        })
    );
    self.skipWaiting();
});

// ============ ACTIVATE ============
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(
                keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
            )
        )
    );
    self.clients.claim();
});

// ============ FETCH ============
self.addEventListener('fetch', event => {
    const req = event.request;
    const url = new URL(req.url);

    if (req.method !== 'GET') return;
    if (url.pathname.startsWith('/api/')) return;
    if (url.pathname.startsWith('/login')) return;
    if (url.pathname.startsWith('/2fa')) return;

    // Статика — cache-first
    if (url.pathname.startsWith('/static/')) {
        event.respondWith(
            caches.match(req).then(cached => {
                return cached || fetch(req).then(res => {
                    const clone = res.clone();
                    caches.open(CACHE_NAME).then(c => c.put(req, clone));
                    return res;
                });
            })
        );
        return;
    }

    // HTML — network-first, при офлайне — кэш
    event.respondWith(
        fetch(req)
            .then(res => {
                if (res.status === 200 && res.type === 'basic') {
                    const clone = res.clone();
                    caches.open(CACHE_NAME).then(c => c.put(req, clone));
                }
                return res;
            })
            .catch(() => {
                return caches.match(req).then(cached => {
                    if (cached) return cached;
                    if (req.mode === 'navigate') {
                        return caches.match(OFFLINE_URL);
                    }
                });
            })
    );
});