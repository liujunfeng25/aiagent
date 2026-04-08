/**
 * 数据驾驶舱：高德 2.0 北京市界、区县下钻、视野限制、边界呼吸动画。
 * Key 与 securityJsCode 与智能物流一致，来自 GET /api/logistics/amap-config
 */
import axios from 'axios'
import {
  BEIJING_BOUNDS_SW,
  BEIJING_BOUNDS_NE,
  BEIJING_DISTRICT_ADCODE,
  BEIJING_DISTRICT_NAMES,
  BEIJING_CITY_ADCODE,
  COCKPIT_MAP_ZOOM_MIN,
  COCKPIT_MAP_ZOOM_MAX,
} from '../utils/beijingDistricts.js'

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const base = src.split('&')[0]
    if (document.querySelector(`script[src^="${base}"]`)) {
      resolve()
      return
    }
    const s = document.createElement('script')
    s.src = src
    s.onload = resolve
    s.onerror = reject
    document.head.appendChild(s)
  })
}

/** 从市界折线环计算外包矩形（不依赖 Polygon.getBounds，避免部分环境下返回非 LngLat 导致 NaN） */
function envelopeFromBoundaryRings(boundaries) {
  let minLng = Infinity
  let maxLng = -Infinity
  let minLat = Infinity
  let maxLat = -Infinity
  const rings = boundaries || []
  rings.forEach((ring) => {
    if (!ring || !ring.length) return
    ring.forEach((pt) => {
      const lng = Number(pt?.[0])
      const lat = Number(pt?.[1])
      if (Number.isFinite(lng) && Number.isFinite(lat)) {
        minLng = Math.min(minLng, lng)
        maxLng = Math.max(maxLng, lng)
        minLat = Math.min(minLat, lat)
        maxLat = Math.max(maxLat, lat)
      }
    })
  })
  if (!Number.isFinite(minLng)) return null
  return { minLng, maxLng, minLat, maxLat }
}

function addBoundaryPolygons(AMap, map, boundaries, style) {
  const list = []
  const rings = boundaries || []
  rings.forEach((path) => {
    if (!path || !path.length) return
    const poly = new AMap.Polygon({
      path,
      strokeColor: style.strokeColor,
      strokeWeight: style.strokeWeight,
      strokeOpacity: style.strokeOpacity,
      fillColor: style.fillColor,
      fillOpacity: style.fillOpacity,
      bubble: true,
    })
    poly.setMap(map)
    list.push(poly)
  })
  return list
}

/**
 * @param {HTMLElement} containerEl
 * @param {{ onDrillChange?: (e: { level: 'city'|'district', name?: string, adcode?: string }) => void }} options
 */
export async function createBeijingCockpitMap(containerEl, options = {}) {
  const { onDrillChange } = options
  const { data: wrap } = await axios.get('/api/logistics/amap-config')
  const cfg = wrap.data || wrap
  const key = cfg.key
  const securityJsCode = cfg.securityJsCode
  if (!key) {
    throw new Error('未配置高德 Key')
  }
  window._AMapSecurityConfig = { securityJsCode: securityJsCode || '' }
  await loadScript(`https://webapi.amap.com/maps?v=2.0&key=${key}`)

  const AMap = window.AMap
  const fallbackBounds = new AMap.Bounds(BEIJING_BOUNDS_SW, BEIJING_BOUNDS_NE)

  let cityPolygons = []
  /** 北京市界环（与 DistrictSearch boundaries 一致），供演示点是否在「行政境内」校验 */
  let cityBoundaryPaths = []
  const districtItems = []
  let breathRaf = null

  /** 先查北京市界，再用 mask 初始化地图：只渲染北京市范围内的底图，而不是整幅中国再缩放 */
  const beijingDistrict = await new Promise((resolve, reject) => {
    AMap.plugin(['AMap.DistrictSearch'], () => {
      const ds = new AMap.DistrictSearch({
        extensions: 'all',
        level: 'city',
      })
      const onGot = (result) => {
        if (!result?.districtList?.length) {
          reject(new Error('北京市边界加载失败'))
          return
        }
        resolve(result.districtList[0])
      }
      ds.search(BEIJING_CITY_ADCODE, (status, result) => {
        if (status === 'complete' && result?.districtList?.length) {
          onGot(result)
          return
        }
        ds.search('北京市', (status2, result2) => {
          if (status2 === 'complete' && result2?.districtList?.length) {
            onGot(result2)
          } else {
            reject(new Error('北京市边界加载失败'))
          }
        })
      })
    })
  })

  const rawBounds = beijingDistrict.boundaries
  cityBoundaryPaths = Array.isArray(rawBounds)
    ? rawBounds.map((ring) => (ring ? [...ring] : []))
    : []

  const env = envelopeFromBoundaryRings(rawBounds)
  const pad = 0.02
  let center = [116.407526, 39.90403]
  if (env) {
    center = [(env.minLng + env.maxLng) / 2, (env.minLat + env.maxLat) / 2]
  }
  const ctr = beijingDistrict.center
  if (ctr) {
    if (typeof ctr.getLng === 'function') {
      center = [ctr.getLng(), ctr.getLat()]
    } else if (Array.isArray(ctr) && ctr.length >= 2) {
      center = [Number(ctr[0]), Number(ctr[1])]
    } else if (typeof ctr === 'string' && ctr.includes(',')) {
      const parts = ctr.split(',').map((x) => Number(x.trim()))
      if (parts.length >= 2) center = [parts[0], parts[1]]
    } else if (ctr.lng != null && ctr.lat != null) {
      center = [Number(ctr.lng), Number(ctr.lat)]
    }
  }
  if (!Number.isFinite(center[0]) || !Number.isFinite(center[1])) {
    center = env
      ? [(env.minLng + env.maxLng) / 2, (env.minLat + env.maxLat) / 2]
      : [116.407526, 39.90403]
  }

  /**
   * 区域掩模：官方示例为对每个环包一层数组，只显示 mask 内瓦片。
   * mask: [ [ring1], [ring2], ... ]
   */
  const maskOption =
    Array.isArray(rawBounds) && rawBounds.length
      ? rawBounds.filter((r) => r && r.length).map((ring) => [ring])
      : undefined

  const baseMapOpts = {
    center,
    zoom: 10,
    viewMode: '2D',
    mapStyle: 'amap://styles/darkblue',
    showLabel: true,
    zooms: [COCKPIT_MAP_ZOOM_MIN, COCKPIT_MAP_ZOOM_MAX],
  }
  let map
  try {
    map = new AMap.Map(
      containerEl,
      maskOption && maskOption.length ? { ...baseMapOpts, mask: maskOption } : baseMapOpts,
    )
  } catch (e) {
    console.warn('[cockpit] 带 mask 的地图初始化失败，回退为无掩模', e)
    map = new AMap.Map(containerEl, baseMapOpts)
  }
  if (env) {
    map.setLimitBounds(
      new AMap.Bounds(
        [env.minLng - pad, env.minLat - pad],
        [env.maxLng + pad, env.maxLat + pad],
      ),
    )
  } else {
    map.setLimitBounds(fallbackBounds)
  }
  try {
    map.setMinZoom(COCKPIT_MAP_ZOOM_MIN)
    map.setMaxZoom(COCKPIT_MAP_ZOOM_MAX)
  } catch (_) {
    /* 仅 zooms 生效 */
  }

  cityPolygons = addBoundaryPolygons(AMap, map, rawBounds, {
    strokeColor: '#22d3ee',
    strokeWeight: 2,
    strokeOpacity: 0.95,
    fillColor: '#06b6d4',
    fillOpacity: 0.14,
  })
  if (cityPolygons.length) {
    map.setFitView(cityPolygons, false, [56, 56, 56, 56], 14)
    const z = map.getZoom()
    if (z != null && z < COCKPIT_MAP_ZOOM_MIN) {
      map.setZoom(COCKPIT_MAP_ZOOM_MIN)
    }
  }

  await new Promise((resolve) => {
    AMap.plugin(['AMap.DistrictSearch'], () => {
      let pending = BEIJING_DISTRICT_ADCODE.length
      if (pending === 0) {
        resolve()
        return
      }
      BEIJING_DISTRICT_ADCODE.forEach((adcode, idx) => {
        const ds = new AMap.DistrictSearch({
          extensions: 'all',
          level: 'district',
        })
        ds.search(adcode, (status, result) => {
          pending -= 1
          if (status === 'complete' && result.districtList?.length) {
            const d = result.districtList[0]
            const name = d.name || BEIJING_DISTRICT_NAMES[idx] || adcode
            const polys = addBoundaryPolygons(AMap, map, d.boundaries, {
              strokeColor: '#38bdf8',
              strokeWeight: 1.5,
              strokeOpacity: 0.7,
              fillColor: '#0ea5e9',
              fillOpacity: 0.07,
            })
            const fitPolys = () => {
              if (polys.length) {
                map.setFitView(polys, false, [80, 80, 80, 80], 16)
                const z = map.getZoom()
                if (z != null && z < COCKPIT_MAP_ZOOM_MIN) {
                  map.setZoom(COCKPIT_MAP_ZOOM_MIN)
                }
              }
              onDrillChange?.({ level: 'district', name, adcode })
            }
            polys.forEach((p) => {
              p.on('click', fitPolys)
            })
            districtItems.push({ adcode, name, polygons: polys })
          }
          if (pending <= 0) resolve()
        })
      })
    })
  })

  const districtPolysFlat = districtItems.flatMap((x) => x.polygons)
  let t0 = 0
  function breathTick() {
    t0 += 0.028
    const o = 0.38 + 0.42 * (0.5 + 0.5 * Math.sin(t0))
    const fi = 0.05 + 0.05 * (0.5 + 0.5 * Math.sin(t0 * 0.85))
    districtPolysFlat.forEach((p) => {
      p.setOptions({
        strokeOpacity: Math.min(0.92, o + 0.12),
        fillOpacity: fi,
      })
    })
    breathRaf = requestAnimationFrame(breathTick)
  }
  breathRaf = requestAnimationFrame(breathTick)

  function backToOverview() {
    if (cityPolygons.length) {
      map.setFitView(cityPolygons, false, [56, 56, 56, 56], 14)
    } else {
      map.setZoomAndCenter(10, [116.407526, 39.90403])
    }
    const z = map.getZoom()
    if (z != null && z < COCKPIT_MAP_ZOOM_MIN) {
      map.setZoom(COCKPIT_MAP_ZOOM_MIN)
    }
    onDrillChange?.({ level: 'city' })
  }

  function destroy() {
    if (breathRaf != null) {
      cancelAnimationFrame(breathRaf)
      breathRaf = null
    }
    map.destroy()
  }

  return {
    map,
    AMap,
    backToOverview,
    destroy,
    /** 北京市界路径（GCJ-02），用于演示数据撒点是否在境内 */
    getCityBoundaryPaths: () => cityBoundaryPaths,
  }
}

function sampleQuadraticBezier(p0, p1, p2, segments) {
  const pts = []
  for (let i = 0; i <= segments; i += 1) {
    const t = i / segments
    const u = 1 - t
    const lng = u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0]
    const lat = u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]
    pts.push([lng, lat])
  }
  return pts
}

/**
 * 飞线演示：车辆点对之间的二次贝塞尔折线 + 透明度脉冲（仅用 Polyline，避免额外插件）
 * @returns {function} 清理函数
 */
export function addCockpitFlyLines(map, AMap, vehicles) {
  if (!vehicles || vehicles.length < 4) return () => {}
  const lines = []
  for (let i = 0; i < 3; i += 1) {
    const a = vehicles[i * 2]
    const b = vehicles[i * 2 + 1]
    if (!a || !b) break
    const p0 = [a.lng, a.lat]
    const p2 = [b.lng, b.lat]
    const p1 = [(a.lng + b.lng) / 2 + 0.012, (a.lat + b.lat) / 2 + 0.018]
    const path = sampleQuadraticBezier(p0, p1, p2, 48)
    const line = new AMap.Polyline({
      path,
      strokeColor: '#67e8f9',
      strokeWeight: 2,
      strokeOpacity: 0.55,
      lineJoin: 'round',
    })
    line.setMap(map)
    lines.push(line)
  }
  let pulse = 0
  const timer = setInterval(() => {
    pulse += 1
    const op = 0.35 + 0.35 * (0.5 + 0.5 * Math.sin(pulse * 0.25))
    lines.forEach((c) => c.setOptions({ strokeOpacity: op }))
  }, 120)
  return () => {
    clearInterval(timer)
    lines.forEach((c) => {
      try {
        map.remove(c)
      } catch (_) {
        /* ignore */
      }
    })
  }
}
