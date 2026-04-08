/**
 * 冷链车辆大屏模拟数据。后续替换为真实接口时：
 * - 批量位置：建议后端提供 GET /api/logistics/cockpit/snapshot
 * - 或前端轮询 GET /api/logistics/vehicles + 各车 GET .../location（注意并发与限流）
 *
 * 演示坐标须落在北京市行政界内：使用 public/geo 下北京市+区县 GeoJSON（GCJ-02）+
 * 纯算法 pointInPolygon（不依赖高德 JS）。
 */
import { BEIJING_BOUNDS_SW, BEIJING_BOUNDS_NE } from '../utils/beijingDistricts.js'
import { pointInBeijingFeatureCollection } from '../utils/pointInPolygon.js'

const STATUSES = ['running', 'parking', 'alarm']

function rnd(min, max) {
  return min + Math.random() * (max - min)
}

function pickStatus() {
  const r = Math.random()
  if (r < 0.65) return 'running'
  if (r < 0.88) return 'parking'
  return 'alarm'
}

/** 在矩形内随机一点（仅作无市界数据时的兜底，角点可能落在邻省） */
function randomPointInBBox() {
  const [swLng, swLat] = BEIJING_BOUNDS_SW
  const [neLng, neLat] = BEIJING_BOUNDS_NE
  return [rnd(swLng, neLng), rnd(swLat, neLat)]
}

function tempForStatus(status) {
  if (status === 'alarm') return rnd(12, 18) // 演示：异常偏高
  if (status === 'parking') return rnd(-2, 6)
  return rnd(-5, 8)
}

function formatNow() {
  const d = new Date()
  const z = (n) => (n < 10 ? `0${n}` : `${n}`)
  return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())} ${z(d.getHours())}:${z(d.getMinutes())}:${z(d.getSeconds())}`
}

function visitCoords(cb, coords) {
  if (!coords) return
  if (typeof coords[0][0] === 'number') {
    coords.forEach((pt) => cb(pt[0], pt[1]))
    return
  }
  coords.forEach((c) => visitCoords(cb, c))
}

/** 自 FeatureCollection 计算外包矩形（用于拒绝采样范围） */
function envelopeFromFeatureCollection(fc) {
  let minLng = Infinity
  let maxLng = -Infinity
  let minLat = Infinity
  let maxLat = -Infinity
  const feats = fc?.features
  if (!feats?.length) return null
  feats.forEach((f) => {
    const g = f?.geometry
    if (!g) return
    visitCoords((lng, lat) => {
      if (!Number.isFinite(lng) || !Number.isFinite(lat)) return
      minLng = Math.min(minLng, lng)
      maxLng = Math.max(maxLng, lng)
      minLat = Math.min(minLat, lat)
      maxLat = Math.max(maxLat, lat)
    }, g.coordinates)
  })
  if (!Number.isFinite(minLng)) return null
  return { minLng, maxLng, minLat, maxLat }
}

/**
 * 在北京市界内随机撒点（拒绝采样）。
 * @param {number} count
 * @param {object} beijingGeoJson FeatureCollection，与 `/geo/beijing_110000_full.json` 同结构
 */
export function generateMockVehiclesInBeijing(count = 32, beijingGeoJson) {
  const list = []
  if (!beijingGeoJson?.features?.length) {
    console.warn('[cockpit] 缺少北京市 GeoJSON，无法保证点在市境内')
    return list
  }
  const env = envelopeFromFeatureCollection(beijingGeoJson)
  if (!env) {
    console.warn('[cockpit] 无法从 GeoJSON 计算外包矩形')
    return list
  }
  let guard = 0
  const maxGuard = Math.max(count * 200, 2000)
  while (list.length < count && guard < maxGuard) {
    guard += 1
    const lng = rnd(env.minLng, env.maxLng)
    const lat = rnd(env.minLat, env.maxLat)
    if (!pointInBeijingFeatureCollection(lng, lat, beijingGeoJson)) continue
    const status = pickStatus()
    list.push({
      id: list.length + 1,
      lng,
      lat,
      plateno: `京A·${String(10000 + list.length * 137).slice(-5)}`,
      cabinTemp: Math.round(tempForStatus(status) * 10) / 10,
      status,
      lastTime: formatNow(),
    })
  }
  if (list.length < count) {
    console.warn(`[cockpit] 北京市境内仅生成 ${list.length}/${count} 个演示点（可提高 maxGuard）`)
  }
  return list
}

/**
 * @deprecated 仅用于无地图上下文时的兜底；矩形范围不等于行政界，可能包含邻省角落。
 */
export function generateMockVehicles(count = 32) {
  const list = []
  for (let i = 1; i <= count; i += 1) {
    const status = pickStatus()
    const [lng, lat] = randomPointInBBox()
    list.push({
      id: i,
      lng,
      lat,
      plateno: `京A·${String(10000 + i * 137).slice(-5)}`,
      cabinTemp: Math.round(tempForStatus(status) * 10) / 10,
      status,
      lastTime: formatNow(),
    })
  }
  return list
}

/**
 * 由车辆列表推导顶部统计（规则与演示数据一致，可随业务调整）
 */
export function summarizeVehicles(vehicles) {
  const total = vehicles.length
  const online = vehicles.filter((v) => v.status === 'running' || v.status === 'parking').length
  const alarm = vehicles.filter((v) => v.status === 'alarm').length
  const tempBad = vehicles.filter((v) => v.cabinTemp > 8 || v.cabinTemp < -18).length
  return { total, online, alarm, tempBad }
}
