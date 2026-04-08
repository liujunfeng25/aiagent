<template>
  <div ref="rootRef" :class="['beijing-map3d', { 'beijing-map3d--blue': theme === 'blue' }]" />
</template>

<script setup>
/**
 * 数据驾驶舱 3D 地图：ECharts + echarts-gl，GCJ-02 与北斗/接口字段一致。
 * 不加载高德 JS；GeoJSON 来自 /geo/beijing_110000_full.json。
 */
import { ref, watch, onMounted, onUnmounted, shallowRef } from 'vue'
import * as echarts from 'echarts'
import 'echarts-gl'

const GEO_URL = '/geo/beijing_110000_full.json'
const MAP_NAME = 'beijing_cockpit'

const STATUS_META = {
  running: { label: '正常运行', color: '#22c55e' },
  parking: { label: '停车待机', color: '#3b82f6' },
  alarm: { label: '告警/异常', color: '#ef4444' },
}

const props = defineProps({
  vehicles: { type: Array, default: () => [] },
  /** 下钻中的区县 adcode，如 '110105'；空字符串表示全市 */
  drillAdcode: { type: String, default: '' },
  theme: { type: String, default: 'default' },
})

const isBlue = () => props.theme === 'blue'

const emit = defineEmits(['drill'])

const rootRef = ref(null)
const chartRef = shallowRef(null)
const fullGeoJsonRef = shallowRef(null)

function filterByAdcode(fc, adcode) {
  if (!adcode || !fc?.features?.length) return fc
  const t = String(adcode)
  const features = fc.features.filter((f) => String(f.properties?.adcode) === t)
  return { type: 'FeatureCollection', features }
}

function sampleQuadraticBezier(p0, p1, p2, segments) {
  const pts = []
  for (let i = 0; i <= segments; i += 1) {
    const t = i / segments
    const u = 1 - t
    const lng = u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0]
    const lat = u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]
    pts.push([lng, lat, 2.5])
  }
  return pts
}

function buildFlyLines3D(vehicles) {
  if (!vehicles || vehicles.length < 4) return []
  const lines = []
  for (let i = 0; i < 3; i += 1) {
    const a = vehicles[i * 2]
    const b = vehicles[i * 2 + 1]
    if (!a || !b) break
    const p0 = [a.lng, a.lat]
    const p2 = [b.lng, b.lat]
    const p1 = [(a.lng + b.lng) / 2 + 0.012, (a.lat + b.lat) / 2 + 0.018]
    lines.push({
      coords: sampleQuadraticBezier(p0, p1, p2, 40),
    })
  }
  return lines
}

function buildPillarLines(vehicles) {
  const h = 8.5
  const base = 0.35
  return vehicles.map((v) => ({
    coords: [
      [v.lng, v.lat, base],
      [v.lng, v.lat, h],
    ],
  }))
}

function baseOption() {
  const flyData = buildFlyLines3D(props.vehicles)
  const pillarLines = buildPillarLines(props.vehicles)

  const blue = isBlue()
  const blockColor = blue ? '#0e2d6a' : '#081420'
  const borderClr = blue ? 'rgba(40, 160, 255, 0.95)' : 'rgba(0, 200, 255, 1)'
  const emphColor = blue ? '#1a4890' : '#0f2847'
  const emphBorder = blue ? 'rgba(100, 180, 255, 0.8)' : 'rgba(253, 224, 71, 0.75)'
  const flyClr = blue ? 'rgba(80, 160, 255, 0.9)' : 'rgba(103, 232, 249, 0.9)'
  const pillarClr = blue ? 'rgba(40, 160, 255, 0.92)' : 'rgba(45, 212, 191, 0.92)'
  const tooltipBorder = blue ? 'rgba(30, 144, 255, 0.45)' : 'rgba(234, 179, 8, 0.45)'
  const envColor = blue ? '#040c28' : '#050a18'

  return {
    backgroundColor: 'transparent',
    tooltip: {
      show: true,
      backgroundColor: 'rgba(2, 6, 23, 0.94)',
      borderWidth: 1,
      borderColor: tooltipBorder,
      textStyle: { color: '#e2e8f0', fontSize: 13 },
      formatter(params) {
        if (params.seriesType === 'map3D' && params.name) {
          return `<div style="padding:4px">${params.name}</div><div style="font-size:12px;opacity:0.85">点击下钻到该区县</div>`
        }
        return ''
      },
    },
    geo3D: {
      map: MAP_NAME,
      roam: true,
      boxWidth: 100,
      boxHeight: 15,
      boxDepth: 'auto',
      regionHeight: 6,
      shading: 'realistic',
      realisticMaterial: {
        roughness: 0.38,
        metalness: 0.2,
      },
      environment: envColor,
      groundPlane: {
        show: false,
      },
      light: {
        main: {
          intensity: 1.7,
          shadow: true,
          alpha: 42,
          beta: 28,
        },
        ambient: {
          intensity: blue ? 0.55 : 0.42,
        },
      },
      viewControl: {
        projection: 'perspective',
        autoRotate: false,
        autoRotateSpeed: 0,
        autoRotateAfterStill: 99999,
        distance: props.drillAdcode ? 72 : 96,
        alpha: 42,
        beta: 2,
        minAlpha: 8,
        maxAlpha: 78,
        minBeta: -75,
        maxBeta: 75,
        animation: true,
        animationDurationUpdate: 800,
      },
      postEffect: {
        enable: true,
        bloom: {
          enable: true,
          intensity: blue ? 0.6 : 0.4,
          threshold: blue ? 0.2 : 0.28,
        },
        SSAO: {
          enable: true,
          quality: 'medium',
          radius: 2,
        },
      },
      itemStyle: {
        color: blockColor,
        borderWidth: 1.5,
        borderColor: borderClr,
        opacity: 1,
      },
      emphasis: {
        itemStyle: {
          color: emphColor,
          borderWidth: 2,
          borderColor: emphBorder,
        },
        label: {
          show: true,
          textStyle: {
            color: '#e0f2fe',
            fontSize: 12,
            backgroundColor: 'rgba(15, 23, 42, 0.75)',
            padding: [4, 6],
            borderRadius: 4,
          },
        },
      },
      label: {
        show: !props.drillAdcode?.length,
        textStyle: {
          color: '#94a3b8',
          fontSize: 11,
          backgroundColor: 'rgba(15, 23, 42, 0.55)',
          padding: [2, 4],
          borderRadius: 3,
        },
      },
    },
    series: [
      {
        type: 'map3D',
        map: MAP_NAME,
        coordinateSystem: 'geo3D',
        regionHeight: 6,
        shading: 'realistic',
        realisticMaterial: {
          roughness: 0.35,
          metalness: 0.18,
        },
        itemStyle: {
          color: blockColor,
          borderWidth: 1.5,
          borderColor: borderClr,
        },
        emphasis: {
          itemStyle: {
            color: emphColor,
            borderColor: emphBorder,
          },
        },
        silent: false,
      },
      ...(flyData.length
        ? [
            {
              type: 'lines3D',
              coordinateSystem: 'geo3D',
              geo3DIndex: 0,
              polyline: true,
              blendMode: 'lighter',
              effect: {
                show: true,
                period: 5,
                trailLength: 0.25,
                trailWidth: 3,
                spotIntensity: 5,
              },
              lineStyle: {
                width: 2,
                color: flyClr,
                opacity: 0.82,
              },
              data: flyData,
              zlevel: 10,
            },
          ]
        : []),
      {
        type: 'lines3D',
        coordinateSystem: 'geo3D',
        geo3DIndex: 0,
        polyline: true,
        silent: true,
        blendMode: 'lighter',
        effect: {
          show: true,
          period: 2.2,
          trailLength: 0.8,
          trailWidth: 5,
          spotIntensity: 12,
        },
        lineStyle: {
          width: 4.5,
          color: pillarClr,
          opacity: 1,
        },
        data: pillarLines,
        zlevel: 8,
      },
    ],
  }
}

function applyGeoAndOption(chart, geoJson) {
  echarts.registerMap(MAP_NAME, geoJson)
  chart.setOption(baseOption(), true)
}

let resizeObs = null
let onResize = null

onMounted(async () => {
  const el = rootRef.value
  if (!el) return
  let geoJson
  try {
    const res = await fetch(GEO_URL)
    if (!res.ok) throw new Error(res.statusText)
    geoJson = await res.json()
  } catch (e) {
    console.error('[BeijingMap3D] GeoJSON 加载失败', e)
    return
  }
  fullGeoJsonRef.value = geoJson

  const chart = echarts.init(el, null, { renderer: 'canvas' })
  chartRef.value = chart

  const activeGeo = props.drillAdcode?.length ? filterByAdcode(geoJson, props.drillAdcode) : geoJson
  applyGeoAndOption(chart, activeGeo)

  chart.on('click', (p) => {
    if (p.seriesType !== 'map3D' || !p.name) return
    if (props.drillAdcode?.length) return
    const feat = geoJson.features?.find((f) => f.properties?.name === p.name)
    const adcode = feat?.properties?.adcode
    emit('drill', {
      level: 'district',
      name: p.name,
      adcode: adcode != null ? String(adcode) : undefined,
    })
  })

  onResize = () => chart.resize()
  window.addEventListener('resize', onResize)
  if (typeof ResizeObserver !== 'undefined') {
    resizeObs = new ResizeObserver(() => chart.resize())
    resizeObs.observe(el)
  }
})

onUnmounted(() => {
  if (onResize) window.removeEventListener('resize', onResize)
  resizeObs?.disconnect()
  chartRef.value?.dispose()
  chartRef.value = null
})

watch(
  () => [props.drillAdcode, props.vehicles, props.theme],
  () => {
    const chart = chartRef.value
    const full = fullGeoJsonRef.value
    if (!chart || !full) return
    const activeGeo = props.drillAdcode?.length ? filterByAdcode(full, props.drillAdcode) : full
    applyGeoAndOption(chart, activeGeo)
  },
  { deep: true },
)
</script>

<style scoped>
.beijing-map3d {
  width: 100%;
  height: 100%;
  min-height: 200px;
  border-radius: inherit;
  background:
    radial-gradient(ellipse 85% 65% at 50% 115%, rgba(8, 47, 73, 0.55), transparent 52%),
    radial-gradient(ellipse 50% 40% at 80% 20%, rgba(234, 179, 8, 0.06), transparent 55%),
    linear-gradient(180deg, #010409 0%, #0c1220 48%, #020617 100%);
}

.beijing-map3d--blue {
  background:
    radial-gradient(ellipse 90% 70% at 50% 100%, rgba(20, 60, 140, 0.5), transparent 55%),
    radial-gradient(ellipse 60% 45% at 50% 30%, rgba(30, 144, 255, 0.10), transparent 50%),
    linear-gradient(180deg, #040c28 0%, #0a2050 48%, #061440 100%);
}
</style>
