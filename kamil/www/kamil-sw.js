// Kamil PWA service worker (root scope). Caches built frontend assets.
const CACHE = 'kamil-assets-v1'

self.addEventListener('install', () => self.skipWaiting())
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()))

self.addEventListener('fetch', (e) => {
  if (e.request.method !== 'GET') return
  const url = new URL(e.request.url)
  // Only handle our own built assets; everything else passes straight through.
  if (url.origin !== self.location.origin) return
  if (!url.pathname.startsWith('/assets/kamil/frontend/')) return
  e.respondWith(
    caches.open(CACHE).then(async (cache) => {
      const hit = await cache.match(e.request)
      if (hit) return hit
      try {
        const res = await fetch(e.request)
        if (res && res.ok) cache.put(e.request, res.clone())
        return res
      } catch (err) {
        return hit || Response.error()
      }
    }),
  )
})
