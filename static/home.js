// SF Pulse home page client behavior
// Wires up tab switching, push subscription UI, and SSE realtime updates.

(function () {
  'use strict'

  // ── Tab switching (panels are sections; nav has data-tab) ────────────────────
  const tabs = document.querySelectorAll('[data-tab]')
  const panels = document.querySelectorAll('.panel')
  const pageEl = document.querySelector('.page')

  function syncTabClass(name) {
    if (!pageEl) return
    pageEl.classList.toggle('eventsActive', name === 'events')
  }

  function showPanel(name) {
    for (const p of panels) {
      const isMatch = p.id === name
      if (isMatch) p.removeAttribute('hidden')
      else p.setAttribute('hidden', '')
    }
    for (const t of tabs) {
      t.classList.toggle('tabActive', t.dataset.tab === name)
    }
    syncTabClass(name)
    if (name === 'events') prepareEventDescriptions()
  }

  function activatePanelFromHash() {
    const hash = (window.location.hash || '#restaurants').replace('#', '')
    showPanel(['restaurants', 'events', 'diagram'].includes(hash) ? hash : 'restaurants')
  }

  for (const t of tabs) {
    t.addEventListener('click', (e) => {
      e.preventDefault()
      const target = t.dataset.tab
      if (!target) return
      history.replaceState(null, '', '#' + target)
      showPanel(target)
    })
  }
  window.addEventListener('hashchange', activatePanelFromHash)
  activatePanelFromHash()

  // ── Event description expand/collapse ─────────────────────────────────────────
  // Use double-rAF so layout has been computed AFTER the panel becomes visible:
  // the outer rAF lets the browser paint, the inner rAF measures scrollHeight
  // after layout. Batch reads then writes to avoid layout thrashing.
  let eventDescPrepared = false
  function prepareEventDescriptions() {
    if (eventDescPrepared) return
    const wrappers = document.querySelectorAll('.eventDescription')
    if (!wrappers.length) {
      eventDescPrepared = true
      return
    }
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const measurements = []
        for (const wrap of wrappers) {
          const inner = wrap.querySelector('.eventDescriptionText')
          if (!inner) continue
          const fullHeight = inner.scrollHeight
          measurements.push({ wrap, inner, fullHeight })
        }
        for (const { wrap, fullHeight } of measurements) {
          const collapsed = Math.min(fullHeight, 60)
          wrap.style.setProperty('--event-description-collapsed-height', collapsed + 'px')
          wrap.style.setProperty('--event-description-expanded-height', fullHeight + 'px')
          wrap.dataset.clampReady = 'true'
          if (fullHeight > collapsed + 4) {
            wrap.dataset.expanded = 'false'
            const btn = document.createElement('button')
            btn.type = 'button'
            btn.className = 'eventDescriptionToggle'
            btn.textContent = 'Show more'
            btn.addEventListener('click', () => {
              const expanded = wrap.dataset.expanded === 'true'
              wrap.dataset.expanded = expanded ? 'false' : 'true'
              btn.textContent = expanded ? 'Show more' : 'Show less'
            })
            wrap.appendChild(btn)
          }
        }
        eventDescPrepared = true
      })
    })
  }

  // ── Diagram iframe auto-sizing ───────────────────────────────────────────────
  window.addEventListener('message', (event) => {
    if (!event.data || event.data.type !== 'sf-pulse-diagram-resize') return
    const frame = document.querySelector('.diagramFrame')
    if (!frame) return
    const height = Number(event.data.height)
    if (!Number.isFinite(height) || height <= 0) return
    frame.style.height = height + 'px'
  })

  // ── SSE realtime updates ─────────────────────────────────────────────────────
  let source
  function connectSSE() {
    if (typeof EventSource === 'undefined') return
    source = new EventSource('/api/events-stream')
    source.addEventListener('restaurants', (ev) => onCollectionUpdate('restaurants', ev))
    source.addEventListener('events', (ev) => onCollectionUpdate('events', ev))
    source.addEventListener('error', () => {
      // Browser auto-reconnects; nothing to do.
    })
  }

  function onCollectionUpdate(kind, ev) {
    try {
      const data = JSON.parse(ev.data)
      if (data.summary) flashUpdate(data.summary)
      // Soft-refresh: reload page to pick up server-rendered table changes.
      // (A future enhancement could splice rows in place.)
      window.setTimeout(() => window.location.reload(), 800)
    } catch (err) {
      console.warn('[sse] parse error', err)
    }
  }

  function flashUpdate(message) {
    let banner = document.querySelector('[data-update-banner]')
    if (!banner) {
      banner = document.createElement('div')
      banner.setAttribute('data-update-banner', '')
      banner.className = 'updateBanner'
      document.body.appendChild(banner)
    }
    banner.textContent = message
    banner.classList.add('updateBannerShow')
    window.setTimeout(() => banner.classList.remove('updateBannerShow'), 3000)
  }

  connectSSE()

  // ── Push subscription button ─────────────────────────────────────────────────
  const pushBtn = document.querySelector('[data-push-button]')
  if (pushBtn && 'serviceWorker' in navigator && 'PushManager' in window) {
    pushBtn.removeAttribute('hidden')
    pushBtn.addEventListener('click', subscribeOrUnsubscribe)
    refreshPushButtonState()
  }

  async function refreshPushButtonState() {
    try {
      const reg = await navigator.serviceWorker.getRegistration()
      const sub = await reg?.pushManager.getSubscription()
      pushBtn.dataset.subscribed = sub ? 'true' : 'false'
      pushBtn.setAttribute(
        'aria-label',
        sub ? 'Disable push notifications' : 'Enable push notifications'
      )
    } catch (err) {
      console.warn('[push] state check failed', err)
    }
  }

  async function subscribeOrUnsubscribe() {
    try {
      const reg =
        (await navigator.serviceWorker.getRegistration()) ||
        (await navigator.serviceWorker.register('/static/service-worker.js'))
      const existing = await reg.pushManager.getSubscription()
      if (existing) {
        await fetch('/api/push/unsubscribe', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ endpoint: existing.endpoint }),
        })
        await existing.unsubscribe()
      } else {
        const { key } = await fetch('/api/push/vapid-key').then((r) => r.json())
        const sub = await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(key),
        })
        const json = sub.toJSON()
        await fetch('/api/push/subscribe', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ endpoint: json.endpoint, keys: json.keys }),
        })
      }
      refreshPushButtonState()
    } catch (err) {
      console.warn('[push] toggle failed', err)
    }
  }

  function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
    const raw = atob(base64)
    const buffer = new Uint8Array(raw.length)
    for (let i = 0; i < raw.length; i += 1) buffer[i] = raw.charCodeAt(i)
    return buffer
  }
})()
