// SF Pulse neighborhood map page — minimal placeholder.
// Renders a simple list of items grouped by neighborhood, fetched from /api.

(async function () {
  const mount = document.getElementById('mapMount')
  if (!mount) return
  try {
    const [restaurants, events] = await Promise.all([
      fetch('/api/restaurants').then((r) => r.json()),
      fetch('/api/events').then((r) => r.json()),
    ])
    const groups = {}
    for (const r of restaurants) {
      const key = r.neighborhood || 'Other SF'
      ;(groups[key] = groups[key] || { restaurants: [], events: [] }).restaurants.push(r)
    }
    for (const e of events) {
      const key = 'Other SF' // simplified — full version derives from location
      ;(groups[key] = groups[key] || { restaurants: [], events: [] }).events.push(e)
    }
    const sections = Object.entries(groups)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(
        ([name, g]) => `
        <section class="mapGroup">
          <h2>${escape(name)}</h2>
          <p>${g.restaurants.length} restaurants · ${g.events.length} events</p>
        </section>
      `
      )
      .join('')
    mount.innerHTML = sections || '<p>No data yet.</p>'
  } catch (err) {
    mount.innerHTML = '<p>Failed to load map data.</p>'
    console.error(err)
  }

  function escape(value) {
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;')
  }
})()
