/**
 * 北京区县 GeoJSON：点落区（GCJ-02 与区界一致）+ 按区聚合订单地址落点。
 */

function pointInRing(lng, lat, ring) {
  let inside = false
  const n = ring.length
  if (n < 3) return false
  for (let i = 0, j = n - 1; i < n; j = i++) {
    const xi = ring[i][0]
    const yi = ring[i][1]
    const xj = ring[j][0]
    const yj = ring[j][1]
    const cross = (yi > lat) !== (yj > lat)
      && lng < (xj - xi) * (lat - yi) / (yj - yi || 1e-12) + xi
    if (cross) inside = !inside
  }
  return inside
}

/** GeoJSON Polygon / MultiPolygon */
export function pointInGeometry(lng, lat, geometry) {
  if (!geometry || lng == null || lat == null) return false
  const { type, coordinates } = geometry
  if (type === 'Polygon') {
    if (!coordinates?.[0] || !pointInRing(lng, lat, coordinates[0])) return false
    for (let i = 1; i < coordinates.length; i++) {
      if (pointInRing(lng, lat, coordinates[i])) return false
    }
    return true
  }
  if (type === 'MultiPolygon') {
    for (const poly of coordinates || []) {
      if (!poly?.[0] || !pointInRing(lng, lat, poly[0])) continue
      let inHole = false
      for (let i = 1; i < poly.length; i++) {
        if (pointInRing(lng, lat, poly[i])) {
          inHole = true
          break
        }
      }
      if (!inHole) return true
    }
    return false
  }
  return false
}

export function findDistrictForLngLat(lng, lat, featureCollection) {
  const feats = featureCollection?.features
  if (!feats?.length) return null
  for (const f of feats) {
    if (pointInGeometry(lng, lat, f.geometry)) {
      const p = f.properties || {}
      const ad = p.adcode
      return {
        adcode: ad != null ? String(ad) : '',
        name: p.name || '',
      }
    }
  }
  return null
}

/** @param {Array<{lng:number,lat:number,order_count?:number}>} markers */
export function enrichMarkersWithDistrict(markers, featureCollection) {
  if (!Array.isArray(markers) || !featureCollection?.features?.length) {
    return markers.map((m) => ({
      ...m,
      district_adcode: '',
      district_name: '',
    }))
  }
  return markers.map((m) => {
    const lng = Number(m.lng)
    const lat = Number(m.lat)
    if (!Number.isFinite(lng) || !Number.isFinite(lat)) {
      return { ...m, district_adcode: '', district_name: '' }
    }
    const d = findDistrictForLngLat(lng, lat, featureCollection)
    return {
      ...m,
      district_adcode: d?.adcode || '',
      district_name: d?.name || '',
    }
  })
}

/**
 * 生成 ECharts map series 数据：各区订单金额合计 value=GMV（name 与 GeoJSON 一致）
 */
export function districtChoroplethFromMarkers(featureCollection, enrichedMarkers) {
  const byName = new Map()
  for (const m of enrichedMarkers || []) {
    const n = (m.district_name || '').trim()
    if (!n) continue
    const gmv = Number(m.gmv) || 0
    const oc = Number(m.order_count) || 0
    const prev = byName.get(n) || {
      value: 0,
      order_sum: 0,
      customer_count: 0,
      adcode: m.district_adcode || '',
    }
    prev.value += gmv
    prev.order_sum += oc
    prev.customer_count += 1
    if (!prev.adcode && m.district_adcode) prev.adcode = m.district_adcode
    byName.set(n, prev)
  }
  const feats = featureCollection?.features || []
  return feats.map((f) => {
    const name = f.properties?.name || ''
    const row = byName.get(name)
    const ad = f.properties?.adcode
    return {
      name,
      value: row ? row.value : 0,
      order_sum: row ? row.order_sum : 0,
      customer_count: row ? row.customer_count : 0,
      adcode: ad != null ? String(ad) : (row?.adcode || ''),
    }
  })
}
