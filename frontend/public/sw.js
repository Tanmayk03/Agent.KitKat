// Agent KitKat service worker.
//
// - Page loads (HTML) are network-first, so a new build is picked up on the next visit;
//   the cached copy is only used when this computer can't be reached.
// - Built assets (/assets/*-<hash>.js|css, fonts, icons) never change under the same name,
//   so they are cache-first.
// - API calls are never cached: job, approval and application data is always live.
//
// Note: browsers only run service workers on https:// or http://localhost. Over plain
// http://<LAN-IP> on an iPhone this file is simply not used (see docs/IPHONE.md).

const VERSION = 'kitkat-v2';
const SHELL = ['./', './index.html', './manifest.json', './icon-192.png', './apple-touch-icon.png'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(VERSION)
      .then((cache) => cache.addAll(SHELL).catch(() => undefined))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.includes('/api/') || url.pathname.startsWith('/screenshots') || url.pathname.startsWith('/docs')) return;

  const isPage = req.mode === 'navigate' || (req.headers.get('accept') || '').includes('text/html');

  if (isPage) {
    event.respondWith(
      fetch(req)
        .then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(VERSION).then((c) => c.put('./index.html', copy));
          }
          return res;
        })
        .catch(() => caches.match('./index.html').then((r) => r || new Response(
          '<h1>Agent KitKat is offline</h1><p>Start Agent KitKat on your computer and reload.</p>',
          { status: 503, headers: { 'Content-Type': 'text/html' } }
        )))
    );
    return;
  }

  if (/\/assets\/|\.(png|svg|woff2?|ico|json)$/.test(url.pathname)) {
    event.respondWith(
      caches.match(req).then((hit) => hit || fetch(req).then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(VERSION).then((c) => c.put(req, copy));
        }
        return res;
      }))
    );
  }
});
