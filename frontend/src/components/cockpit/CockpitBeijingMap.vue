<template>
  <div class="ai-map">
    <div class="ai-map__grid" aria-hidden="true" />
    <div ref="chartRef" class="ai-map__chart" />
    <div v-if="loadError" class="ai-map__err">{{ loadError }}</div>
    <button
      v-if="!loadError && mapGeo === 'beijing' && drillAdcode"
      type="button"
      class="ai-map__back"
      @click="emit('back')"
    >
      ← 返回全市
    </button>
    <div v-if="!loadError" class="ai-map__legend">
      <template v-if="legendMode === 'choropleth'">
        <span class="ai-map__legend-item">区县订单金额</span>
      </template>
      <template v-else-if="legendMode === 'scatter'">
        <span class="ai-map__legend-item"><i class="ai-map__dot ai-map__dot--order" />订单客户（本区）</span>
        <span class="ai-map__hint">京津冀 · GCJ-02 · 与智能排线同源</span>
      </template>
      <template v-else-if="legendMode === 'vehicle'">
        <span class="ai-map__legend-item"><i class="ai-map__dot ai-map__dot--order" />车辆示意</span>
        <span class="ai-map__hint">GCJ-02</span>
      </template>
      <template v-else>
        <span class="ai-map__legend-item">北京市界</span>
        <span class="ai-map__hint">暂无区内订单落点</span>
      </template>
    </div>
  </div>
</template>

<script setup>
/**
 * 驾驶舱 2D 地图：ECharts geo + effectScatter。
 * mapGeo=china 时使用全国底图（备用）；mapGeo=beijing 为北京区界 + 可选下钻；订单客户绿点与智能排线同源地理编码。
 */
import { ref, watch, onMounted, onUnmounted, shallowRef, computed } from 'vue'
import * as echarts from 'echarts'

const GEO_BEIJING = '/geo/beijing_110000_full.json'
const GEO_CHINA = '/geo/china_100000_full.json'

const STATUS = {
  running: { color: '#34d399', label: '运行' },
  parking: { color: '#38bdf8', label: '停车' },
  alarm: { color: '#f87171', label: '告警' },
}

const ORDER_GREEN = '#34d399'

const props = defineProps({
  /** 订单收货地址落点（智能驾驶舱；是否绘制由 showOrderScatter 控制） */
  orderMarkers: { type: Array, default: () => [] },
  /** 北京区县 choropleth：{ name, value, customer_count, adcode } */
  districtMapData: { type: Array, default: () => [] },
  /** 为 true 且 orderMarkers 非空时绘制 effectScatter（建议仅下钻后、点数较少时） */
  showOrderScatter: { type: Boolean, default: false },
  /** 兼容：模拟车辆 */
  vehicles: { type: Array, default: () => [] },
  drillAdcode: { type: String, default: '' },
  /** china | beijing */
  mapGeo: { type: String, default: 'beijing' },
})

const emit = defineEmits(['drill', 'back', 'marker-click'])

const chartRef = ref(null)
const chart = shallowRef(null)
const fullGeoRef = shallowRef(null)
const loadError = ref('')

const mapGeo = computed(() => (props.mapGeo === 'beijing' ? 'beijing' : 'china'))

const useChoropleth = computed(() => {
  if (mapGeo.value !== 'beijing') return false
  const rows = props.districtMapData
  return Array.isArray(rows) && rows.length > 0 && rows.some((d) => Number(d.value) > 0)
})

const legendMode = computed(() => {
  if (props.showOrderScatter && props.orderMarkers?.length) return 'scatter'
  if (useChoropleth.value) return 'choropleth'
  if (props.vehicles?.length) return 'vehicle'
  return 'none'
})

function mapRegistryName() {
  return mapGeo.value === 'beijing' ? 'beijing_cockpit_ai' : 'china_cockpit_ai'
}

function filterByAdcode(fc, adcode) {
  if (!adcode || !fc?.features?.length) return fc
  const t = String(adcode)
  const features = fc.features.filter((f) => String(f.properties?.adcode) === t)
  return { type: 'FeatureCollection', features }
}

function geoFitFromOrderMarkers(markers) {
  const m = (markers || []).filter(
    (x) => x && Number.isFinite(Number(x.lng)) && Number.isFinite(Number(x.lat)),
  )
  if (!m.length) {
    return { center: [105, 36], zoom: 1.12, layoutSize: '92%' }
  }
  let minLng = 180
  let maxLng = -180
  let minLat = 90
  let maxLat = -90
  for (const p of m) {
    const lng = Number(p.lng)
    const lat = Number(p.lat)
    minLng = Math.min(minLng, lng)
    maxLng = Math.max(maxLng, lng)
    minLat = Math.min(minLat, lat)
    maxLat = Math.max(maxLat, lat)
  }
  const cx = (minLng + maxLng) / 2
  const cy = (minLat + maxLat) / 2
  const span = Math.max(maxLng - minLng, maxLat - minLat, 1.0)
  const zoom = span > 28 ? 0.72 : span > 14 ? 0.9 : span > 6 ? 1.08 : span > 2 ? 1.28 : 1.55
  return { center: [cx, cy], zoom, layoutSize: '90%' }
}

function orderMarkerRows() {
  return (props.orderMarkers || []).map((m) => {
    const rawAddr = (m.address != null && String(m.address).trim()) ? String(m.address).trim() : ''
    const title = rawAddr
      ? (rawAddr.length > 36 ? `${rawAddr.slice(0, 36)}…` : rawAddr)
      : (m.customer_name || '客户')
    return {
    name: title,
    value: [Number(m.lng), Number(m.lat)],
    markerPayload: m,
    itemStyle: {
      color: ORDER_GREEN,
      shadowBlur: 10,
      shadowColor: ORDER_GREEN,
    },
    symbolSize: 9,
  }})
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

function scatterRows() {
  if (props.showOrderScatter && props.orderMarkers?.length) return orderMarkerRows()
  return vehicleRows()
}

function baseOption(mapName) {
  const drilled = Boolean(props.drillAdcode?.length) && mapGeo.value === 'beijing'
  const chinaFit = mapGeo.value === 'china' && props.orderMarkers?.length
  const fit = chinaFit ? geoFitFromOrderMarkers(props.orderMarkers) : null
  const zoom = fit ? fit.zoom : (drilled ? 1.15 : 1.05)
  const center = fit ? fit.center : undefined
  const layoutSize = fit ? fit.layoutSize : (drilled ? '88%' : '92%')

  const choropleth = mapGeo.value === 'beijing'
    && Array.isArray(props.districtMapData)
    && props.districtMapData.length > 0
    && props.districtMapData.some((d) => Number(d.value) > 0)

  const mapSeriesData = choropleth
    ? props.districtMapData.map((d) => ({
        name: d.name,
        value: Number(d.value) || 0,
        order_sum: Number(d.order_sum) || 0,
        customer_count: Number(d.customer_count) || 0,
      }))
    : []

  const vmax = choropleth ? Math.max(1, ...mapSeriesData.map((d) => d.value)) : 1

  const geoBase = {
    map: mapName,
    roam: true,
    zoom,
    center,
    scaleLimit: { min: 0.45, max: 8 },
    layoutCenter: ['50%', '50%'],
    layoutSize,
    itemStyle: choropleth
      ? {
          areaColor: 'rgba(15, 23, 42, 0.96)',
          borderColor: 'rgba(56, 189, 248, 0.28)',
          borderWidth: 1,
          shadowColor: 'rgba(8, 47, 73, 0.45)',
          shadowBlur: 8,
        }
      : {
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
      itemStyle: choropleth
        ? {
            borderColor: 'rgba(129, 230, 254, 0.95)',
            borderWidth: 2,
            shadowBlur: 18,
            shadowColor: 'rgba(56, 189, 248, 0.35)',
          }
        : {
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
      show: mapGeo.value === 'beijing' && !drilled,
      color: 'rgba(241, 245, 249, 0.96)',
      fontSize: 11,
      fontWeight: 600,
      textBorderColor: 'rgba(2, 6, 23, 0.92)',
      textBorderWidth: 2,
    },
    silent: false,
  }

  const mapLayer = choropleth
    ? {
        type: 'map',
        map: mapName,
        geoIndex: 0,
        zlevel: 1,
        silent: false,
        label: { show: false },
        data: mapSeriesData,
        emphasis: {
          disabled: false,
          label: { show: true, color: '#f8fafc', fontSize: 11 },
        },
      }
    : {
        type: 'map',
        map: mapName,
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
      }

  const opt = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      /** 父级 `.ai-map` 为圆角/装饰使用 overflow:hidden，tooltip 挂 body 避免贴边被裁切 */
      appendToBody: true,
      borderWidth: 1,
      borderColor: 'rgba(34, 211, 238, 0.45)',
      backgroundColor: 'rgba(2, 6, 23, 0.94)',
      textStyle: { color: '#e2e8f0', fontSize: 12 },
      extraCssText: 'max-width:min(420px,92vw);box-shadow:0 8px 28px rgba(0,0,0,0.45);z-index:9999;',
      formatter(p) {
        if (p.seriesType === 'effectScatter' && p.data) {
          const d = p.data
          if (d.markerPayload) {
            const addr = (d.markerPayload.address || '').slice(0, 80)
            const oc = d.markerPayload.order_count
            const gm = d.markerPayload.gmv
            const gmvLine = gm != null && Number.isFinite(Number(gm))
              ? `<div style="opacity:0.88">订单金额：${Number(gm).toFixed(2)} 元</div>`
              : ''
            return `<div style="font-weight:600;margin-bottom:4px">${d.name || '客户'}</div>`
              + `<div style="opacity:0.88">订单数：${oc != null ? oc : '—'}</div>`
              + gmvLine
              + (addr ? `<div style="opacity:0.75;font-size:11px;margin-top:4px">${addr}</div>` : '')
          }
          const st = STATUS[d.status] || STATUS.running
          return `<div style="font-weight:600;margin-bottom:4px">${d.name || '车辆'}</div>`
            + `<div style="opacity:0.9">状态：<span style="color:${st.color}">${st.label}</span></div>`
        }
        if (p.seriesType === 'map' && p.data) {
          const gmv = p.data.value
          const oc = p.data.order_sum
          const cc = p.data.customer_count
          const hint = mapGeo.value === 'beijing' && !drilled ? '单击下钻' : ''
          const gmvStr = gmv != null && Number.isFinite(Number(gmv))
            ? `${Number(gmv).toFixed(2)} 元`
            : '—'
          return `<div style="font-weight:600">${p.name || ''}</div>`
            + `<div style="opacity:0.88">订单金额：${gmvStr}</div>`
            + `<div style="opacity:0.82">订单数：${oc != null ? oc : '—'} · 地址落点：${cc != null ? cc : '—'}</div>`
            + (hint ? `<div style="opacity:0.65;font-size:11px;margin-top:4px">${hint}</div>` : '')
        }
        if ((p.componentType === 'geo' || p.seriesType === 'map') && p.name && !p.data) {
          const hint = mapGeo.value === 'beijing' && !drilled ? '单击下钻区县' : ''
          return `${p.name}<div style="opacity:0.75;font-size:11px;margin-top:4px">${hint}</div>`
        }
        return p.name || ''
      },
    },
    geo: geoBase,
    series: [
      mapLayer,
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
        data: scatterRows(),
      },
    ],
  }

  if (choropleth) {
    opt.visualMap = {
      type: 'continuous',
      min: 0,
      max: vmax,
      seriesIndex: 0,
      orient: 'vertical',
      right: 8,
      bottom: 56,
      text: ['高', '低'],
      calculable: false,
      backgroundColor: 'rgba(15, 23, 42, 0.72)',
      borderColor: 'rgba(56, 189, 248, 0.22)',
      borderWidth: 1,
      padding: [4, 6],
      inRange: {
        color: [
          '#0f172a',
          '#1e3a5f',
          '#164e63',
          '#0e7490',
          '#0891b2',
          '#22d3ee',
          '#67e8f9',
          '#fbbf24',
        ],
      },
      textStyle: { color: 'rgba(203, 213, 225, 0.88)', fontSize: 10 },
    }
  }

  return opt
}

function bindClick() {
  const c = chart.value
  if (!c) return
  c.off('click')
  c.on('click', (p) => {
    if (p.seriesType === 'effectScatter' && p.data?.markerPayload) {
      emit('marker-click', p.data.markerPayload)
      return
    }
    if (mapGeo.value !== 'beijing') return
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
  const name = mapRegistryName()
  echarts.registerMap(name, geoJson)
  chart.value.setOption(baseOption(name), true)
  bindClick()
}

let mapResizeObs = null
let onWinResize = null

async function loadGeoJson() {
  const url = mapGeo.value === 'beijing' ? GEO_BEIJING : GEO_CHINA
  const res = await fetch(url)
  if (!res.ok) throw new Error(res.statusText)
  return res.json()
}

onMounted(async () => {
  let geoJson
  try {
    geoJson = await loadGeoJson()
  } catch (e) {
    console.error('[CockpitBeijingMap] GeoJSON', e)
    loadError.value = '地图数据加载失败（请确认 public/geo 下 GeoJSON 可访问）'
    return
  }
  fullGeoRef.value = geoJson
  const el = chartRef.value
  if (!el) return
  chart.value = echarts.init(el, null, { renderer: 'canvas' })
  const active = props.drillAdcode?.length && mapGeo.value === 'beijing'
    ? filterByAdcode(geoJson, props.drillAdcode)
    : geoJson
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
  () => [
    props.drillAdcode,
    props.vehicles,
    props.orderMarkers,
    props.mapGeo,
    props.districtMapData,
    props.showOrderScatter,
  ],
  () => {
    const full = fullGeoRef.value
    const c = chart.value
    if (!full || !c) return
    const active = props.drillAdcode?.length && mapGeo.value === 'beijing'
      ? filterByAdcode(full, props.drillAdcode)
      : full
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
.ai-map__dot--order { background: #34d399; color: #34d399; }

.ai-map__hint {
  margin-left: 4px;
  opacity: 0.55;
  font-size: 9px;
  letter-spacing: 0.12em;
}
</style>
