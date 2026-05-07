// Web Push service worker.
// Receives push events and shows notifications.

self.addEventListener('install', () => {
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim())
})

self.addEventListener('push', (event) => {
  let payload = { title: 'SF Pulse', body: 'New update', url: '/' }
  if (event.data) {
    try {
      payload = { ...payload, ...event.data.json() }
    } catch {
      payload.body = event.data.text() || payload.body
    }
  }
  event.waitUntil(
    self.registration.showNotification(payload.title, {
      body: payload.body,
      icon: '/static/icons/icon-192.png',
      badge: '/static/icons/icon-192.png',
      data: { url: payload.url },
    })
  )
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const url = event.notification.data?.url || '/'
  event.waitUntil(
    self.clients.matchAll({ type: 'window' }).then((clients) => {
      for (const c of clients) {
        if (c.url.includes(url) && 'focus' in c) return c.focus()
      }
      return self.clients.openWindow(url)
    })
  )
})
