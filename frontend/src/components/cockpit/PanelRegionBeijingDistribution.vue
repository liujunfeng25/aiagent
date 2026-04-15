<template>
  <CockpitPanel title="区域分布" title-en="BEIJING · GMV BY DISTRICT">
    <div ref="chartRef" class="region-chart" />
  </CockpitPanel>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, shallowRef } from 'vue'
import * as echarts from 'echarts'
import CockpitPanel from './CockpitPanel.vue'
import {
  sxTooltip,
  sxAxisY,
  sxAnimation,
} from '../../utils/echartTheme.js'

/** { district_name, adcode, gmv, order_count?, customer_count? } */
const props = defineProps({
  data: { type: Array, default: () => [] },
})

const emit = defineEmits(['district-drill'])

const chartRef = ref(null)
const chart = shallowRef(null)

function sortRows(data) {
  return [...data].sort((a, b) => Number(b.gmv || 0) - Number(a.gmv || 0))
}

function gmvToWan(g) {
  return (Number(g) || 0) / 10000
}

function formatWanLabel(v) {
  const n = Number(v) || 0
  if (n <= 0) return '—'
  return `¥${n.toFixed(1)}万`
}

function buildOption(data) {
  const sorted = sortRows(data)
  const names = sorted.map((r) => r.district_name || '—')
  const valuesWan = sorted.map((r) => gmvToWan(r.gmv))
  const maxWan = Math.max(0.0001, ...valuesWan, 0.01)
  const pad = maxWan * 0.06
  const axisMax = maxWan + pad
  const trackData = names.map(() => axisMax)

  return {
    ...sxAnimation,
    grid: {
      top: 8,
      left: 2,
      right: 56,
      bottom: 18,
      containLabel: true,
    },
    tooltip: {
      ...sxTooltip({}),
      appendToBody: true,
      extraCssText:
        'backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);'
        + 'box-shadow:0 0 20px rgba(34,211,238,0.15);border-radius:6px;'
        + 'max-width:min(400px,92vw);z-index:9999;',
      axisPointer: { type: 'shadow' },
      formatter(params) {
        const main = params.find((x) => x.seriesName === 'GMV')
        const p = main || params[0]
        if (!p) return ''
        const row = sorted[p.dataIndex]
        const oc = row?.order_count != null ? row.order_count : '—'
        const cc = row?.customer_count != null ? row.customer_count : '—'
        const w = Number(p.value) || 0
        const yuan = w * 10000
        return `${p.name}<br/>订单金额：¥${yuan.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}（${w.toFixed(2)}万）<br/>订单数：${oc} · 地址落点：${cc}`
      },
    },
    xAxis: {
      ...sxAxisY({
        max: axisMax,
        splitLine: { lineStyle: { color: 'rgba(250,204,21,0.05)' } },
        axisLabel: {
          color: 'rgba(148, 163, 184, 0.82)',
          fontSize: 10,
          formatter: (v) => (Number(v) >= 0 ? `${Number(v).toFixed(1)}万` : v),
        },
      }),
      type: 'value',
    },
    yAxis: {
      type: 'category',
      data: names,
      inverse: true,
      boundaryGap: false,
      axisLabel: {
        color: '#e2e8f0',
        fontSize: 10,
        margin: 2,
        align: 'right',
        textShadowBlur: 4,
        textShadowColor: 'rgba(0,0,0,0.5)',
      },
      axisLine: {
        lineStyle: {
          color: 'rgba(250,204,21,0.12)',
          shadowBlur: 6,
          shadowColor: 'rgba(34,211,238,0.18)',
        },
      },
    },
    series: [
      {
        name: 'track',
        type: 'bar',
        barWidth: '56%',
        barGap: '-100%',
        silent: true,
        z: 1,
        itemStyle: {
          color: 'rgba(15, 25, 48, 0.85)',
          borderRadius: [0, 10, 10, 0],
          borderColor: 'rgba(100, 116, 139, 0.12)',
          borderWidth: 1,
        },
        data: trackData,
      },
      {
        name: 'GMV',
        type: 'bar',
        barWidth: '56%',
        z: 2,
        barCategoryGap: '16%',
        itemStyle: {
          borderRadius: [0, 10, 10, 0],
          borderColor: 'rgba(103, 232, 249, 0.22)',
          borderWidth: 1,
          color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
            { offset: 0, color: '#1e3a5f' },
            { offset: 0.45, color: '#1d4ed8' },
            { offset: 0.78, color: '#0ea5e9' },
            { offset: 1, color: '#22d3ee' },
          ]),
          shadowBlur: 8,
          shadowColor: 'rgba(34, 211, 238, 0.22)',
        },
        label: {
          show: true,
          position: 'right',
          color: 'rgba(226,232,240,0.94)',
          fontSize: 10,
          fontWeight: 600,
          distance: 4,
          overflow: 'none',
          formatter: (p) => formatWanLabel(p.value),
        },
        data: valuesWan,
      },
    ],
  }
}

function bindChartClick() {
  const c = chart.value
  if (!c) return
  c.off('click')
  c.on('click', (params) => {
    if (params.seriesName !== 'GMV') return
    if (params.componentType !== 'series' || params.seriesType !== 'bar') return
    const sorted = sortRows(props.data)
    const row = sorted[params.dataIndex]
    const adcode = row?.adcode ? String(row.adcode) : ''
    if (!adcode) return
    emit('district-drill', {
      name: (row.district_name || params.name || '').trim(),
      adcode,
    })
  })
}

function init() {
  if (!chartRef.value) return
  chart.value = echarts.init(chartRef.value)
  chart.value.setOption(buildOption(props.data))
  bindChartClick()
}

let ro = null
onMounted(() => {
  init()
  if (typeof ResizeObserver !== 'undefined') {
    ro = new ResizeObserver(() => chart.value?.resize())
    ro.observe(chartRef.value)
  }
})
onUnmounted(() => { ro?.disconnect(); chart.value?.dispose() })

watch(() => props.data, (v) => {
  chart.value?.setOption(buildOption(v), true)
  bindChartClick()
}, { deep: true })
</script>

<style scoped>
.region-chart {
  width: 100%;
  height: 100%;
  min-height: 220px;
}
</style>
