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
      const key = deriveEventNeighborhood(e.location)
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

  // Mirror app/shared/catalog.py's derive_event_neighborhood.
  function deriveEventNeighborhood(location) {
    const text = String(location || '').toLowerCase()
    const aliases = [
      ['Mission', /\bmission\b|dolores park|mission st/],
      ['SoMa', /\bsoma\b|south of market/],
      ['Potrero Hill', /potrero hill|vermont & 20th/],
      ['Golden Gate Park', /golden gate park|hippie hill/],
      ['Financial District', /financial district|main to great highway/],
      ['Civic Center', /civic center|main public library/],
      ['Marina', /marina|fort mason/],
      ['Yerba Buena', /yerba buena/],
      ['Haight', /\bhaight\b/],
      ['Sunset', /sunset/],
      ['Richmond', /richmond/],
      ['Castro', /castro/],
    ]
    for (const [label, re] of aliases) {
      if (re.test(text)) return label
    }
    return 'Other SF'
  }
})()
