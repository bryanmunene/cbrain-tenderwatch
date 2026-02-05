// TenderWatch Service Worker v2.0
const CACHE_NAME = 'tenderwatch-v2';
const STATIC_CACHE = 'tenderwatch-static-v2';

// Files to cache for offline use
const STATIC_FILES = [
  '/',
  '/static/manifest.json',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png'
];

// Install event - cache static files
self.addEventListener('install', (event) => {
  console.log('[SW] Installing TenderWatch Service Worker...');
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => {
      console.log('[SW] Caching static files');
      return cache.addAll(STATIC_FILES).catch(err => {
        console.log('[SW] Some files failed to cache:', err);
      });
    })
  );
  self.skipWaiting();
});

// Activate event - clean old caches
self.addEventListener('activate', (event) => {
  console.log('[SW] Activating TenderWatch Service Worker...');
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME && cacheName !== STATIC_CACHE) {
            console.log('[SW] Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  self.clients.claim();
});

// Fetch event - network first, then cache
self.addEventListener('fetch', (event) => {
  // Skip non-GET requests
  if (event.request.method !== 'GET') return;
  
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        // Clone and cache successful responses
        if (response.status === 200) {
          const responseClone = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseClone);
          });
        }
        return response;
      })
      .catch(() => {
        // Fallback to cache if offline
        return caches.match(event.request);
      })
  );
});

// Handle push notifications
self.addEventListener('push', (event) => {
  console.log('[SW] Push notification received');
  
  let data = {
    title: 'TenderWatch Alert',
    body: 'New tenders matching your criteria!',
    icon: '/static/icons/icon-192.png',
    badge: '/static/icons/icon-72.png',
    tag: 'tenderwatch-notification',
    requireInteraction: true,
    actions: [
      { action: 'view', title: '👀 View Tenders' },
      { action: 'dismiss', title: '✕ Dismiss' }
    ]
  };
  
  if (event.data) {
    try {
      data = { ...data, ...event.data.json() };
    } catch (e) {
      data.body = event.data.text();
    }
  }
  
  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: data.icon,
      badge: data.badge,
      tag: data.tag,
      requireInteraction: data.requireInteraction,
      actions: data.actions,
      data: data.url || '/'
    })
  );
});

// Handle notification clicks
self.addEventListener('notificationclick', (event) => {
  console.log('[SW] Notification clicked:', event.action);
  event.notification.close();
  
  if (event.action === 'dismiss') return;
  
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      // Focus existing window if open
      for (const client of clientList) {
        if (client.url.includes(self.location.origin) && 'focus' in client) {
          return client.focus();
        }
      }
      // Open new window
      if (clients.openWindow) {
        return clients.openWindow(event.notification.data || '/');
      }
    })
  );
});

// Background sync for scheduled notifications
self.addEventListener('sync', (event) => {
  if (event.tag === 'daily-tender-check') {
    console.log('[SW] Background sync: daily-tender-check');
    event.waitUntil(checkForNewTenders());
  }
});

// Periodic background sync (if supported)
self.addEventListener('periodicsync', (event) => {
  if (event.tag === 'daily-tender-scan') {
    console.log('[SW] Periodic sync: daily-tender-scan');
    event.waitUntil(checkForNewTenders());
  }
});

async function checkForNewTenders() {
  try {
    // Notify user to check for new tenders
    await self.registration.showNotification('TenderWatch Daily Scan', {
      body: 'Time to check for new tender opportunities!',
      icon: '/static/icons/icon-192.png',
      badge: '/static/icons/icon-72.png',
      tag: 'daily-reminder',
      requireInteraction: true,
      actions: [
        { action: 'scan', title: '🔍 Scan Now' },
        { action: 'dismiss', title: '✕ Later' }
      ]
    });
    return true;
  } catch (error) {
    console.error('[SW] Failed to send notification:', error);
    return false;
  }
}
