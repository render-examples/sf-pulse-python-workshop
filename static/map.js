// SF Pulse neighborhood map page — minimal placeholder.
// Renders a simple list of items grouped by neighborhood, fetched from /api.

(async function () {
  const mount = document.getElementById('mapMount')
  if (!mount) return
  try {
    const restaurants = await fetch('/api/restaurants').then((r) => r.json())
    const groups = {}
    for (const r of restaurants) {
      const key = r.neighborhood || 'Other SF'
      ;(groups[key] = groups[key] || { restaurants: [] }).restaurants.push(r)
    }
    const sections = Object.entries(groups)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(
        ([name, g]) => `
        <section class="mapGroup">
          <h2>${escape(name)}</h2>
          <p>${g.restaurants.length} restaurants</p>
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
