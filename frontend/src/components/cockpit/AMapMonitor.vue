<template>
  <div class="amap-monitor">
    <div ref="mapContainer" class="amap-monitor__map" />
    <div v-if="loadFailed" class="amap-monitor__fallback">
      <span class="amap-monitor__fallback-icon">🗺</span>
      <span>{{ failMsg }}</span>
      <span class="amap-monitor__fallback-hint">{{ failHint }}</span>
    </div>
    <div v-if="tileWarning && !loadFailed" class="amap-monitor__tile-warn">
      ⚠ 地图瓦片加载缓慢，请检查网络/VPN 设置
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import axios from 'axios'

/** 北京市中心（GCJ-02），与智能驾驶舱一致 */
const BJ_CENTER = [116.407526, 39.90403]
/** 北京市域大致范围，限制拖拽不漂到河北/天津（略留边） */
const BJ_BOUNDS_SW = [115.42, 39.44]
const BJ_BOUNDS_NE = [117.52, 41.06]

const props = defineProps({
  vehicles: { type: Array, default: () => [] },
  warehouses: { type: Array, default: () => [] },
  /** `2d`：物联监控 Tab；`cockpit3d`：3D 物联 Tab，深色矢量 + 俯仰 + 楼块（非卫星） */
  variant: {
    type: String,
    default: '2d',
    validator: (v) => v === '2d' || v === 'cockpit3d',
  },
})

const mapContainer = ref(null)
const loadFailed = ref(false)
const failMsg = ref('高德地图加载失败')
const failHint = ref('请检查 AMAP_JSAPI_KEY 配置')
const tileWarning = ref(false)

let map = null
let AMap = null
let vehicleMarkers = []
let warehouseMarkers = []
let infoWindow = null

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const base = src.split('&')[0]
    if (document.querySelector(`script[src^="${base}"]`)) { resolve(); return }
    const s = document.createElement('script')
    s.src = src
    s.onload = resolve
    s.onerror = reject
    document.head.appendChild(s)
  })
}

function statusColor(status) {
  if (status === 'running') return '#34d399'
  if (status === 'alarm') return '#f87171'
  return '#60a5fa'
}

function statusLabel(status) {
  if (status === 'running') return '运行中'
  if (status === 'alarm') return '告警'
  return '停车'
}

function createDotContent(color, status) {
  const pulse = status === 'alarm' ? 'animation:amap-pulse 1.5s ease-in-out infinite;' : ''
  return `<div style="width:10px;height:10px;border-radius:50%;background:${color};border:2px solid rgba(255,255,255,0.85);box-shadow:0 0 6px ${color}, 0 0 12px ${color}40;${pulse}"></div>`
}

function createWarehouseContent() {
  return `<div style="width:16px;height:16px;border-radius:3px;background:linear-gradient(135deg,#1e90ff,#00c8ff);border:2px solid rgba(255,255,255,0.85);box-shadow:0 0 8px rgba(30,144,255,0.6);display:flex;align-items:center;justify-content:center;font-size:9px;">🏭</div>`
}

function clearMarkers(list) {
  list.forEach((m) => { try { map?.remove(m) } catch (_) { /* */ } })
  list.length = 0
}

function renderVehicles() {
  if (!map || !AMap) return
  clearMarkers(vehicleMarkers)
  props.vehicles.forEach((v) => {
    const color = statusColor(v.status)
    const marker = new AMap.Marker({
      position: [v.lng, v.lat],
      content: createDotContent(color, v.status),
      offset: new AMap.Pixel(-7, -7),
      zIndex: v.status === 'alarm' ? 120 : 100,
    })
    marker.on('click', () => {
      if (!infoWindow) {
        infoWindow = new AMap.InfoWindow({ isCustom: true, offset: new AMap.Pixel(0, -20) })
      }
      const plate = v.plateno || v.plateNo || v.plate_no || '未知'
      const temp = v.cabinTemp != null ? `${v.cabinTemp}°C` : (v.temperature != null ? `${v.temperature}°C` : '--')
      const tempColor = (v.cabinTemp || 0) > 8 ? '#f87171' : '#34d399'
      infoWindow.setContent(`
        <div style="background:rgba(8,20,60,0.96);border:1px solid rgba(30,144,255,0.5);border-radius:8px;padding:12px 16px;color:#e8eef8;font-size:12px;min-width:180px;box-shadow:0 4px 24px rgba(0,0,0,0.6),0 0 20px rgba(30,144,255,0.15);">
          <div style="font-weight:700;font-size:15px;color:#60a5fa;margin-bottom:8px;border-bottom:1px solid rgba(30,144,255,0.2);padding-bottom:6px;">🚛 ${plate}</div>
          <div style="margin-bottom:4px;">状态：<span style="color:${color};font-weight:600;">${statusLabel(v.status)}</span></div>
          <div style="margin-bottom:4px;">温度：<span style="color:${tempColor};">${temp}</span></div>
          <div>定位：${v.lastTime || '--'}</div>
        </div>
      `)
      infoWindow.open(map, [v.lng, v.lat])
    })
    marker.setMap(map)
    vehicleMarkers.push(marker)
  })
}

function renderWarehouses() {
  if (!map || !AMap) return
  clearMarkers(warehouseMarkers)
  props.warehouses.forEach((w) => {
    const marker = new AMap.Marker({
      position: [w.lng, w.lat],
      content: createWarehouseContent(),
      offset: new AMap.Pixel(-10, -10),
      zIndex: 90,
    })
    marker.on('click', () => {
      if (!infoWindow) {
        infoWindow = new AMap.InfoWindow({ isCustom: true, offset: new AMap.Pixel(0, -20) })
      }
      infoWindow.setContent(`
        <div style="background:rgba(8,20,60,0.96);border:1px solid rgba(30,144,255,0.5);border-radius:8px;padding:12px 16px;color:#e8eef8;font-size:12px;min-width:180px;box-shadow:0 4px 24px rgba(0,0,0,0.6),0 0 20px rgba(30,144,255,0.15);">
          <div style="font-weight:700;font-size:15px;color:#1e90ff;margin-bottom:8px;border-bottom:1px solid rgba(30,144,255,0.2);padding-bottom:6px;">🏭 ${w.name}</div>
          <div style="margin-bottom:4px;">地址：${w.address || '--'}</div>
          <div>摄像头：${w.cameraCount ?? 0} 个</div>
        </div>
      `)
      infoWindow.open(map, [w.lng, w.lat])
    })
    marker.setMap(map)
    warehouseMarkers.push(marker)
  })
}

function applyDarkStyle() {
  if (!map) return
  try {
    map.setMapStyle('amap://styles/darkblue')
  } catch (_) { /* */ }
}

async function initMap() {
  await nextTick()
  if (!mapContainer.value) return
  try {
    const { data: wrap } = await axios.get('/api/logistics/amap-config')
    const cfg = wrap.data || wrap
    const key = cfg.key
    if (!key) throw new Error('no key')
    window._AMapSecurityConfig = { securityJsCode: cfg.securityJsCode || '' }
    await loadScript(`https://webapi.amap.com/maps?v=2.0&key=${key}`)
  } catch (e) {
    console.warn('[AMapMonitor] 加载高德地图失败:', e)
    loadFailed.value = true
    failMsg.value = '高德地图加载失败'
    failHint.value = '请检查 AMAP_JSAPI_KEY 配置或网络连接'
    return
  }

  AMap = window.AMap
  if (!AMap) { loadFailed.value = true; return }

  const is3d = props.variant === 'cockpit3d'

  const baseOpts = {
    center: BJ_CENTER,
    mapStyle: 'amap://styles/darkblue',
    showLabel: true,
    zooms: [9, 18],
  }

  let mapOpts
  if (is3d) {
    mapOpts = {
      ...baseOpts,
      zoom: 12,
      viewMode: '3D',
      pitch: 58,
      rotation: -12,
      showBuilding: true,
      buildingAnimation: true,
    }
  } else {
    mapOpts = {
      ...baseOpts,
      zoom: 11,
      viewMode: '2D',
    }
  }

  try {
    map = new AMap.Map(mapContainer.value, mapOpts)
  } catch (e) {
    console.warn('[AMapMonitor] 3D 初始化失败，回退 2D', e)
    if (is3d) {
      try {
        map = new AMap.Map(mapContainer.value, {
          ...baseOpts,
          zoom: 11,
          viewMode: '2D',
        })
      } catch (e2) {
        console.warn('[AMapMonitor] 2D 回退失败', e2)
        loadFailed.value = true
        failHint.value = '地图 WebGL 初始化失败，请尝试更新浏览器或关闭硬件加速限制'
        return
      }
    } else {
      loadFailed.value = true
      return
    }
  }

  applyDarkStyle()

  if (is3d && map) {
    try {
      const sw = new AMap.LngLat(BJ_BOUNDS_SW[0], BJ_BOUNDS_SW[1])
      const ne = new AMap.LngLat(BJ_BOUNDS_NE[0], BJ_BOUNDS_NE[1])
      map.setLimitBounds(new AMap.Bounds(sw, ne))
    } catch (e) {
      console.warn('[AMapMonitor] setLimitBounds', e)
    }
  }

  const tileTimer = setTimeout(() => {
    tileWarning.value = true
  }, 8000)

  map.on('complete', () => {
    clearTimeout(tileTimer)
    tileWarning.value = false
    applyDarkStyle()
    if (is3d && map) {
      try {
        map.setPitch(58)
        map.setRotation(-12)
      } catch (_) { /* */ }
    }
    renderVehicles()
    renderWarehouses()
  })

  setTimeout(() => {
    applyDarkStyle()
    if (!vehicleMarkers.length) {
      renderVehicles()
      renderWarehouses()
    }
  }, 3000)
}

watch(() => props.vehicles, renderVehicles, { deep: true })
watch(() => props.warehouses, renderWarehouses, { deep: true })

onMounted(() => { initMap() })

onUnmounted(() => {
  clearMarkers(vehicleMarkers)
  clearMarkers(warehouseMarkers)
  if (map) { try { map.destroy() } catch (_) { /* */ } }
})
</script>

<style scoped>
.amap-monitor {
  position: relative;
  width: 100%;
  height: 100%;
  border-radius: 4px;
  overflow: hidden;
  background: #0d1b3e;
}

.amap-monitor__map {
  width: 100%;
  height: 100%;
}

:deep(.amap-logo),
:deep(.amap-copyright) {
  opacity: 0.3 !important;
}

:deep(.amap-maps) {
  background: #0d1b3e !important;
}

.amap-monitor__fallback {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: rgba(140, 170, 220, 0.6);
  font-size: 14px;
  z-index: 10;
  background: linear-gradient(180deg, #040c28 0%, #0d1b3e 100%);
}

.amap-monitor__fallback-icon { font-size: 40px; opacity: 0.4; }
.amap-monitor__fallback-hint { font-size: 11px; color: rgba(140, 170, 220, 0.4); }

.amap-monitor__tile-warn {
  position: absolute;
  bottom: 28px;
  left: 50%;
  transform: translateX(-50%);
  padding: 4px 12px;
  border-radius: 4px;
  background: rgba(250, 204, 21, 0.15);
  border: 1px solid rgba(250, 204, 21, 0.3);
  color: #fde68a;
  font-size: 11px;
  z-index: 20;
  white-space: nowrap;
}
</style>

<style>
@keyframes amap-pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.4); opacity: 0.7; }
}
</style>
