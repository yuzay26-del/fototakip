/* FotoTakip service worker: uygulama kabuğunu ve son verileri önbellekte tutar.
   Yalnızca güvenli bağlamda (https veya localhost) çalışır. */
const VERSION = 'ft-0.2.0';
const TILES = 'ft-tiles';
const TILE_LIMIT = 800; // yaklaşık 15-20 MB
const SHELL = ['/', '/app.js', '/styles.css', '/manifest.webmanifest', '/icon.svg', '/vendor/leaflet/leaflet.js', '/vendor/leaflet/leaflet.css'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(VERSION).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== VERSION && k !== TILES).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});

const networkFirst = async req => {
  const cache = await caches.open(VERSION);
  try {
    const res = await fetch(req);
    if (res.ok) cache.put(req, res.clone());
    return res;
  } catch (err) {
    const hit = await cache.match(req, { ignoreSearch: req.mode === 'navigate' });
    if (hit) return hit;
    if (req.mode === 'navigate') return cache.match('/');
    throw err;
  }
};

const cacheFirst = async req => {
  const cache = await caches.open(VERSION);
  const hit = await cache.match(req);
  if (hit) return hit;
  const res = await fetch(req);
  if (res.ok) cache.put(req, res.clone());
  return res;
};

/* Harita karoları: bakılan bölgeler önbellekte kalır, internet yokken de görünür.
   OpenStreetMap kurallarına uygun olarak toplu indirme yapılmaz; yalnızca görüntülenen karolar saklanır. */
const tile = async req => {
  const cache = await caches.open(TILES);
  const hit = await cache.match(req);
  if (hit) return hit;
  const res = await fetch(req);
  if (res.ok || res.type === 'opaque') {
    await cache.put(req, res.clone());
    const keys = await cache.keys();
    for (let i = 0; i < keys.length - TILE_LIMIT; i++) await cache.delete(keys[i]);
  }
  return res;
};

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.hostname === 'tile.openstreetmap.org') { e.respondWith(tile(req)); return; }
  if (url.origin !== location.origin) return;
  if (url.pathname === '/api/events' || url.pathname === '/api/backup') return;
  if (url.pathname.startsWith('/files/') && !url.pathname.startsWith('/files/signature/')) { e.respondWith(cacheFirst(req)); return; }
  if (url.pathname === '/api/bootstrap' || req.mode === 'navigate' || SHELL.includes(url.pathname)) { e.respondWith(networkFirst(req)); return; }
});
