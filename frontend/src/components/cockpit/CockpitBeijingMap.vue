<template>
  <div class="ai-map">
    <div class="ai-map__grid" aria-hidden="true" />
    <div ref="chartRef" class="ai-map__chart" />
    <div v-if="loadError" class="ai-map__err">{{ loadError }}</div>
    <button
      v-if="!loadError && drillAdcode"
      type="button"
      class="ai-map__back"
      @click="emit('back')"
    >
      ← 返回全市
    </button>
    <div v-if="!loadError" class="ai-map__legend">
      <span class="ai-map__legend-item"><i class="ai-map__dot ai-map__dot--run" />运行</span>
      <span class="ai-map__legend-item"><i class="ai-map__dot ai-map__dot--park" />停车</span>
      <span class="ai-map__legend-item"><i class="ai-map__dot ai-map__dot--alarm" />告警</span>
      <span class="ai-map__hint">演示点位 · GCJ-02</span>
    </div>
  </div>
</template>

<script setup>
/**
 * 智能驾驶舱 2D 态势地图：ECharts geo + effectScatter（脉冲光晕），贴合 CockpitPanel 青霓虹 AI 风格。
 * 无 echarts-gl；GeoJSON 与 /geo/beijing_110000_full.json 一致。
 */
import { ref, watch, onMounted, onUnmounted, shallowRef } from 'vue'
import * as echarts from 'echarts'

const GEO_URL = '/geo/beijing_110000_full.json'
const MAP_NAME = 'beijing_cockpit_ai'

const STATUS = {
  running: { color: '#34d399', label: '运行' },
  parking: { color: '#38bdf8', label: '停车' },
  alarm: { color: '#f87171', label: '告警' },
}

const props = defineProps({
  vehicles: { type: Array, default: () => [] },
  drillAdcode: { type: String, default: '' },
})

const emit = defineEmits(['drill', 'back'])

const chartRef = ref(null)
const chart = shallowRef(null)
const fullGeoRef = shallowRef(null)
const loadError = ref('')

function filterByAdcode(fc, adcode) {
  if (!adcode || !fc?.features?.length) return fc
  const t = String(adcode)
  const features = fc.features.filter((f) => String(f.properties?.adcode) === t)
  return { type: 'FeatureCollection', features }
}

function vehicleRows() {
  return (props.vehicles || []).map((v) => {
    const st = STATUS[v.status] || STATUS.running
    const alarm = v.status === 'alarm'
    return {
      name: v.plateno || `车辆${v.id}`,
      value: [v.lng, v.lat],
      status: v.status,
      itemStyle: {
        color: st.color,
        shadowBlur: alarm ? 16 : 8,
        shadowColor: st.color,
      },
      symbolSize: alarm ? 12 : 7,
    }
  })
}

function baseOption() {
  const drilled = Boolean(props.drillAdcode?.length)
  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      borderWidth: 1,
      borderColor: 'rgba(34, 211, 238, 0.45)',
      backgroundColor: 'rgba(2, 6, 23, 0.94)',
      textStyle: { color: '#e2e8f0', fontSize: 12 },
      formatter(p) {
        if (p.seriesType === 'effectScatter' && p.data) {
          const d = p.data
          const st = STATUS[d.status] || STATUS.running
          return `<div style="font-weight:600;margin-bottom:4px">${d.name || '车辆'}</div>`
            + `<div style="opacity:0.9">状态：<span style="color:${st.color}">${st.label}</span></div>`
        }
        if ((p.componentType === 'geo' || p.seriesType === 'map') && p.name) {
          return `${p.name}<div style="opacity:0.75;font-size:11px;margin-top:4px">${drilled ? '' : '单击下钻区县'}</div>`
        }
        return p.name || ''
      },
    },
    geo: {
      map: MAP_NAME,
      roam: true,
      zoom: drilled ? 1.15 : 1.05,
      scaleLimit: { min: 0.65, max: 8 },
      layoutCenter: ['50%', '50%'],
      layoutSize: drilled ? '88%' : '92%',
      itemStyle: {
        areaColor: new echarts.graphic.RadialGradient(0.5, 0.55, 0.95, [
          { offset: 0, color: 'rgba(30, 58, 138, 0.55)' },
          { offset: 0.72, color: 'rgba(15, 23, 42, 0.88)' },
          { offset: 1, color: 'rgba(8, 15, 35, 0.95)' },
        ]),
        borderColor: 'rgba(56, 232, 255, 0.55)',
        borderWidth: 1.25,
        shadowColor: 'rgba(34, 211, 238, 0.22)',
        shadowBlur: 14,
      },
      emphasis: {
        disabled: false,
        focus: 'self',
        itemStyle: {
          areaColor: 'rgba(51, 92, 173, 0.75)',
          borderColor: 'rgba(129, 230, 254, 0.95)',
          borderWidth: 2,
          shadowBlur: 22,
          shadowColor: 'rgba(56, 189, 248, 0.35)',
        },
        label: {
          show: true,
          color: '#f1f5f9',
          fontSize: 11,
          fontWeight: 600,
        },
      },
      label: {
        show: !drilled,
        color: 'rgba(148, 163, 184, 0.88)',
        fontSize: 10,
        textBorderColor: 'rgba(2, 6, 23, 0.65)',
        textBorderWidth: 1,
      },
      silent: false,
    },
    series: [
      {
        type: 'map',
        map: MAP_NAME,
        geoIndex: 0,
        zlevel: 1,
        silent: false,
        label: { show: false },
        itemStyle: {
          areaColor: 'rgba(0,0,0,0)',
          borderWidth: 0,
        },
        emphasis: { disabled: true },
        data: [],
      },
      {
        type: 'effectScatter',
        coordinateSystem: 'geo',
        zlevel: 2,
        rippleEffect: {
          brushType: 'stroke',
          number: 2,
          scale: 3.2,
          period: 2.6,
        },
        label: { show: false },
        data: vehicleRows(),
      },
    ],
  }
}

function bindClick() {
  const c = chart.value
  if (!c) return
  c.off('click')
  c.on('click', (p) => {
    if (props.drillAdcode?.length) return
    if (p.seriesType === 'effectScatter') return
    if (!p.name) return
    const isGeo = p.componentType === 'geo' || p.componentSubType === 'geo'
    const isMap = p.seriesType === 'map'
    if (!isGeo && !isMap) return
    const full = fullGeoRef.value
    const feat = full?.features?.find((f) => f.properties?.name === p.name)
    const adcode = feat?.properties?.adcode
    emit('drill', {
      level: 'district',
      name: p.name,
      adcode: adcode != null ? String(adcode) : undefined,
    })
  })
}

function applyChart(geoJson) {
  if (!chart.value || !geoJson) return
  echarts.registerMap(MAP_NAME, geoJson)
  chart.value.setOption(baseOption(), true)
  bindClick()
}

let mapResizeObs = null
let onWinResize = null

onMounted(async () => {
  let geoJson
  try {
    const res = await fetch(GEO_URL)
    if (!res.ok) throw new Error(res.statusText)
    geoJson = await res.json()
  } catch (e) {
    console.error('[CockpitBeijingMap] GeoJSON', e)
    loadError.value = '地图数据加载失败'
    return
  }
  fullGeoRef.value = geoJson
  const el = chartRef.value
  if (!el) return
  chart.value = echarts.init(el, null, { renderer: 'canvas' })
  const active = props.drillAdcode?.length ? filterByAdcode(geoJson, props.drillAdcode) : geoJson
  applyChart(active)

  if (typeof ResizeObserver !== 'undefined') {
    mapResizeObs = new ResizeObserver(() => chart.value?.resize())
    mapResizeObs.observe(el)
  }
  onWinResize = () => chart.value?.resize()
  window.addEventListener('resize', onWinResize)
})

onUnmounted(() => {
  mapResizeObs?.disconnect()
  mapResizeObs = null
  if (onWinResize) window.removeEventListener('resize', onWinResize)
  onWinResize = null
  chart.value?.dispose()
  chart.value = null
})

watch(
  () => [props.drillAdcode, props.vehicles],
  () => {
    const full = fullGeoRef.value
    const c = chart.value
    if (!full || !c) return
    const active = props.drillAdcode?.length ? filterByAdcode(full, props.drillAdcode) : full
    applyChart(active)
  },
  { deep: true },
)
</script>

<style scoped>
.ai-map {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 220px;
  border-radius: inherit;
  overflow: hidden;
  background:
    radial-gradient(ellipse 80% 65% at 50% 100%, rgba(34, 211, 238, 0.06), transparent 55%),
    radial-gradient(ellipse 55% 45% at 15% 25%, rgba(56, 189, 248, 0.04), transparent 45%),
    linear-gradient(165deg, rgba(8, 15, 35, 0.5) 0%, rgba(4, 10, 28, 0.35) 100%);
}

.ai-map__grid {
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: 0.35;
  background-image:
    linear-gradient(rgba(34, 211, 238, 0.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(34, 211, 238, 0.05) 1px, transparent 1px);
  background-size: 36px 36px;
  mask-image: radial-gradient(ellipse 75% 70% at 50% 45%, black 20%, transparent 75%);
}

.ai-map__chart {
  position: absolute;
  inset: 0;
}

.ai-map__err {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  color: rgba(248, 113, 113, 0.9);
}

.ai-map__back {
  position: absolute;
  top: 10px;
  left: 10px;
  z-index: 4;
  margin: 0;
  padding: 8px 14px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: #e0f2fe;
  cursor: pointer;
  border-radius: 4px;
  border: 1px solid rgba(34, 211, 238, 0.55);
  background: linear-gradient(165deg, rgba(8, 51, 68, 0.92), rgba(15, 23, 42, 0.88));
  box-shadow:
    0 0 14px rgba(34, 211, 238, 0.2),
    inset 0 1px 0 rgba(255, 255, 255, 0.06);
  transition: border-color 0.2s, box-shadow 0.2s;
}
.ai-map__back:hover {
  border-color: rgba(56, 232, 255, 0.85);
  box-shadow: 0 0 18px rgba(34, 211, 238, 0.35);
}

.ai-map__legend {
  position: absolute;
  left: 10px;
  bottom: 8px;
  z-index: 3;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  padding: 6px 10px;
  font-size: 10px;
  color: rgba(203, 213, 225, 0.85);
  letter-spacing: 0.04em;
  pointer-events: none;
  background: linear-gradient(90deg, rgba(2, 6, 23, 0.75), rgba(2, 6, 23, 0.35));
  border: 1px solid rgba(34, 211, 238, 0.2);
  border-radius: 4px;
}

.ai-map__legend-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.ai-map__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  box-shadow: 0 0 8px currentColor;
}
.ai-map__dot--run { background: #34d399; color: #34d399; }
.ai-map__dot--park { background: #38bdf8; color: #38bdf8; }
.ai-map__dot--alarm { background: #f87171; color: #f87171; }

.ai-map__hint {
  margin-left: 4px;
  opacity: 0.55;
  font-size: 9px;
  letter-spacing: 0.12em;
}
</style>
