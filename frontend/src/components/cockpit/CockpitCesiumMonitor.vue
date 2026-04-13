<template>
  <div class="cesium-monitor">
    <div ref="containerRef" class="cesium-monitor__canvas" />
    <div v-if="loadError" class="cesium-monitor__fallback">
      <span class="cesium-monitor__fallback-icon">🌐</span>
      <span>{{ loadError }}</span>
    </div>
    <p v-else-if="useFallbackImagery" class="cesium-monitor__hint">
      Ion 卫星底图不可用，已切换 OpenStreetMap 街道图（可浏览北京路网；国内网络偶发需重试）
    </p>
  </div>
</template>

<script setup>
/**
 * 物联 3D Tab：Cesium 北京区域实景 + GCJ-02→WGS-84 点位。
 * 必须显式 await createWorldImageryAsync，否则常见「只有星空、无底图」。
 */
import { ref, watch, onMounted, onUnmounted, shallowRef } from 'vue'
import * as Cesium from 'cesium'
import 'cesium/Source/Widgets/widgets.css'
import { gcj02ToWgs84 } from '../../utils/gcj02ToWgs84.js'

const props = defineProps({
  vehicles: { type: Array, default: () => [] },
  warehouses: { type: Array, default: () => [] },
})

const containerRef = ref(null)
const loadError = ref('')
const useFallbackImagery = ref(false)

/** @type {import('vue').ShallowRef<import('cesium').Viewer | null>} */
const viewerRef = shallowRef(null)

const ionToken = (import.meta.env.VITE_CESIUM_ION_TOKEN || '').trim()

/** 北京城区中心附近（WGS-84），与高德 GCJ 中心偏差在演示可接受范围内 */
const BJ_LNG = 116.4074
const BJ_LAT = 39.9042

function viewerUiOptions() {
  return {
    baseLayerPicker: false,
    animation: false,
    timeline: false,
    fullscreenButton: false,
    vrButton: false,
    geocoder: false,
    homeButton: true,
    navigationHelpButton: false,
    sceneModePicker: false,
    infoBox: true,
    selectionIndicator: true,
  }
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

/**
 * 显式挂接底图：Ion 全球影像（卫星+标注）；失败则用 OSM，保证一定能看见「地图」而非星空。
 */
async function attachBaseImagery(viewer) {
  viewer.imageryLayers.removeAll()

  if (ionToken) {
    Cesium.Ion.defaultAccessToken = ionToken
    try {
      const provider = await Cesium.createWorldImageryAsync({
        style: Cesium.IonWorldImageryStyle.AERIAL_WITH_LABELS,
      })
      viewer.imageryLayers.addImageryProvider(provider)
      return
    } catch (e) {
      console.warn('[CockpitCesiumMonitor] Ion 底图失败，回退 OSM', e)
    }
  }

  useFallbackImagery.value = true
  viewer.imageryLayers.addImageryProvider(
    new Cesium.OpenStreetMapImageryProvider({
      url: 'https://tile.openstreetmap.org/',
    }),
  )
}

function buildTerrainOptions() {
  if (ionToken) {
    Cesium.Ion.defaultAccessToken = ionToken
    return { terrain: Cesium.Terrain.fromWorldTerrain() }
  }
  return { terrainProvider: new Cesium.EllipsoidTerrainProvider() }
}

/** 俯视北京：高度与俯角保证看到的是城区地图而非「太空星空」 */
function flyBeijing(viewer) {
  viewer.camera.flyTo({
    destination: Cesium.Cartesian3.fromDegrees(BJ_LNG, BJ_LAT, 16500),
    orientation: {
      heading: Cesium.Math.toRadians(0),
      pitch: Cesium.Math.toRadians(-65),
      roll: 0,
    },
    duration: 2.0,
  })
}

function syncEntities(viewer) {
  viewer.entities.removeAll()

  ;(props.vehicles || []).forEach((v) => {
    const lng = Number(v.lng)
    const lat = Number(v.lat)
    if (!Number.isFinite(lng) || !Number.isFinite(lat)) return
    const [wLng, wLat] = gcj02ToWgs84(lng, lat)
    const color = Cesium.Color.fromCssColorString(statusColor(v.status))
    const plate = v.plateno || v.plateNo || v.plate_no || '未知'
    const temp = v.cabinTemp != null ? `${v.cabinTemp}°C` : (v.temperature != null ? `${v.temperature}°C` : '--')
    const tempColor = (v.cabinTemp || 0) > 8 ? '#f87171' : '#34d399'

    viewer.entities.add({
      position: Cesium.Cartesian3.fromDegrees(wLng, wLat, 45),
      point: {
        pixelSize: v.status === 'alarm' ? 12 : 8,
        color,
        outlineColor: Cesium.Color.WHITE,
        outlineWidth: 2,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
      description:
        `<div style="font-family:system-ui,sans-serif;padding:4px 0;">`
        + `<div style="font-weight:700;color:#60a5fa;margin-bottom:6px;">🚛 ${plate}</div>`
        + `<div>状态：<b style="color:${statusColor(v.status)}">${statusLabel(v.status)}</b></div>`
        + `<div>温度：<b style="color:${tempColor}">${temp}</b></div>`
        + `<div>定位：${v.lastTime || '--'}</div>`
        + `</div>`,
    })
  })

  ;(props.warehouses || []).forEach((w) => {
    const lng = Number(w.lng)
    const lat = Number(w.lat)
    if (!Number.isFinite(lng) || !Number.isFinite(lat)) return
    const [wLng, wLat] = gcj02ToWgs84(lng, lat)
    viewer.entities.add({
      position: Cesium.Cartesian3.fromDegrees(wLng, wLat, 50),
      point: {
        pixelSize: 11,
        color: Cesium.Color.fromCssColorString('#38bdf8'),
        outlineColor: Cesium.Color.WHITE,
        outlineWidth: 2,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
      description:
        `<div style="font-family:system-ui,sans-serif;padding:4px 0;">`
        + `<div style="font-weight:700;color:#38bdf8;margin-bottom:6px;">🏭 ${w.name || '仓库'}</div>`
        + `<div>地址：${w.address || '--'}</div>`
        + `<div>摄像头：${w.cameraCount ?? 0} 个</div>`
        + `</div>`,
    })
  })
}

async function init() {
  const el = containerRef.value
  if (!el) return
  try {
    const viewer = new Cesium.Viewer(el, {
      ...viewerUiOptions(),
      ...buildTerrainOptions(),
      /** 禁止依赖 Viewer 内置默认底图异步（易失败导致纯黑/仅星空） */
      baseLayer: false,
      /** 关闭星空盒，避免「满屏星点、看不见地图」的观感 */
      skyBox: false,
    })

    viewerRef.value = viewer
    viewer.scene.globe.show = true
    viewer.scene.globe.enableLighting = false
    viewer.scene.skyAtmosphere.show = true
    viewer.scene.backgroundColor = Cesium.Color.fromCssColorString('#0b1220')

    await attachBaseImagery(viewer)

    flyBeijing(viewer)
    syncEntities(viewer)
  } catch (e) {
    console.warn('[CockpitCesiumMonitor]', e)
    loadError.value = 'Cesium 初始化失败，请检查控制台与网络'
  }
}

watch(
  () => [props.vehicles, props.warehouses],
  () => {
    const v = viewerRef.value
    if (v) syncEntities(v)
  },
  { deep: true },
)

onMounted(() => {
  void init()
})

onUnmounted(() => {
  const v = viewerRef.value
  viewerRef.value = null
  if (v && !v.isDestroyed()) {
    try {
      v.destroy()
    } catch {
      /* */
    }
  }
})
</script>

<style scoped>
.cesium-monitor {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 260px;
  border-radius: 4px;
  overflow: hidden;
  background: #0b1220;
}

.cesium-monitor__canvas {
  width: 100%;
  height: 100%;
}

.cesium-monitor__canvas :deep(.cesium-viewer) {
  font-family: inherit;
}

.cesium-monitor__fallback {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: rgba(140, 170, 220, 0.75);
  font-size: 13px;
  z-index: 2;
  background: linear-gradient(180deg, #040c28 0%, #0d1b3e 100%);
}

.cesium-monitor__fallback-icon {
  font-size: 36px;
  opacity: 0.45;
}

.cesium-monitor__hint {
  position: absolute;
  bottom: 6px;
  left: 50%;
  transform: translateX(-50%);
  margin: 0;
  padding: 4px 10px;
  max-width: 96%;
  text-align: center;
  font-size: 10px;
  line-height: 1.35;
  color: rgba(148, 163, 184, 0.88);
  z-index: 2;
  pointer-events: none;
}
</style>
