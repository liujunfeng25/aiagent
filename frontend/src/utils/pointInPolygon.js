/**
 * 射线法判断点是否在环内（lng/lat，闭合环首尾可重复）。
 * 与北斗/高德接口字段一致时为 GCJ-02。
 */
export function pointInRing(lng, lat, ring) {
  if (!ring || ring.length < 3) return false
  let inside = false
  const n = ring.length
  for (let i = 0, j = n - 1; i < n; j = i, i += 1) {
    const xi = ring[i][0]
    const yi = ring[i][1]
    const xj = ring[j][0]
    const yj = ring[j][1]
    const intersect =
      yi > lat !== yj > lat && lng < ((xj - xi) * (lat - yi)) / (yj - yi + 1e-12) + xi
    if (intersect) inside = !inside
  }
  return inside
}

/** GeoJSON Polygon coordinates: [outer, ...holes] */
export function pointInPolygonCoords(lng, lat, polygonCoords) {
  if (!polygonCoords?.length) return false
  const outer = polygonCoords[0]
  if (!pointInRing(lng, lat, outer)) return false
  for (let h = 1; h < polygonCoords.length; h += 1) {
    const hole = polygonCoords[h]
    if (hole?.length && pointInRing(lng, lat, hole)) return false
  }
  return true
}

/** MultiPolygon coordinates: polygon[][] */
export function pointInMultiPolygonCoords(lng, lat, multiCoords) {
  if (!multiCoords?.length) return false
  for (let p = 0; p < multiCoords.length; p += 1) {
    if (pointInPolygonCoords(lng, lat, multiCoords[p])) return true
  }
  return false
}

/** 单个 GeoJSON Feature（Polygon 或 MultiPolygon） */
export function pointInFeature(lng, lat, feature) {
  const g = feature?.geometry
  if (!g) return false
  if (g.type === 'Polygon') return pointInPolygonCoords(lng, lat, g.coordinates)
  if (g.type === 'MultiPolygon') {
    const polys = g.coordinates
    for (let i = 0; i < polys.length; i += 1) {
      if (pointInPolygonCoords(lng, lat, polys[i])) return true
    }
  }
  return false
}

/**
 * 点是否在北京市任一区县面内（110000_full 为区县拼合，与市界等价）。
 */
export function pointInBeijingFeatureCollection(lng, lat, featureCollection) {
  const features = featureCollection?.features
  if (!features?.length) return false
  for (let i = 0; i < features.length; i += 1) {
    if (pointInFeature(lng, lat, features[i])) return true
  }
  return false
}
