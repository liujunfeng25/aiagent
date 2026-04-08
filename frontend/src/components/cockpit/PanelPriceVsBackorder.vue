<template>
  <CockpitPanelBlue title="批发均价 × 背单压力（同日对齐）" title-en="PRICE VS RISK">
    <div ref="chartRef" class="chart" />
  </CockpitPanelBlue>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, shallowRef, computed } from 'vue'
import * as echarts from 'echarts'
import CockpitPanelBlue from './CockpitPanelBlue.vue'

const props = defineProps({
  xinfadiSeries: { type: Array, default: () => [] },
  backorderSeries: { type: Array, default: () => [] },
})

const chartRef = ref(null)
const chart = shallowRef(null)

const merged = computed(() => {
  const m = new Map()
  for (const r of props.xinfadiSeries || []) {
    const d = String(r.day).slice(0, 10)
    m.set(d, { day: d, avg_price: Number(r.avg_price || 0), backorder_count: null })
  }
  for (const r of props.backorderSeries || []) {
    const d = String(r.day).slice(0, 10)
    const cur = m.get(d) || { day: d, avg_price: null, backorder_count: null }
    cur.backorder_count = Number(r.backorder_count || 0)
    m.set(d, cur)
  }
  return [...m.values()].sort((a, b) => a.day.localeCompare(b.day))
})

function buildOption(rows) {
  const days = rows.map((r) => r.day)
  const prices = rows.map((r) => (r.avg_price != null ? r.avg_price : null))
  const backs = rows.map((r) => (r.backorder_count != null ? r.backorder_count : null))

  return {
    grid: { top: 28, right: 52, bottom: 30, left: 52 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(8,12,32,0.94)',
      borderColor: 'rgba(30,144,255,0.4)',
      textStyle: { color: '#e8eef8', fontSize: 12 },
    },
    legend: {
      data: ['批发均价', '背单笔数'],
      textStyle: { color: 'rgba(148,163,184,0.85)', fontSize: 10 },
      top: 0,
    },
    xAxis: {
      type: 'category',
      data: days,
      axisLabel: { color: 'rgba(148,163,184,0.75)', fontSize: 9, rotate: 28 },
      axisLine: { lineStyle: { color: 'rgba(30,144,255,0.2)' } },
    },
    yAxis: [
      {
        type: 'value',
        name: '元',
        splitLine: { lineStyle: { color: 'rgba(30,144,255,0.06)' } },
        axisLabel: { color: 'rgba(148,163,184,0.75)', fontSize: 10 },
      },
      {
        type: 'value',
        name: '笔',
        splitLine: { show: false },
        axisLabel: { color: 'rgba(248,113,113,0.75)', fontSize: 10 },
      },
    ],
    series: [
      {
        name: '批发均价',
        type: 'line',
        smooth: true,
        yAxisIndex: 0,
        data: prices,
        lineStyle: { width: 2, color: '#38bdf8' },
        itemStyle: { color: '#7dd3fc' },
        connectNulls: true,
      },
      {
        name: '背单笔数',
        type: 'line',
        smooth: true,
        yAxisIndex: 1,
        data: backs,
        lineStyle: { width: 2, color: '#f87171' },
        itemStyle: { color: '#fca5a5' },
        areaStyle: { color: 'rgba(248,113,113,0.12)' },
        connectNulls: true,
      },
    ],
  }
}

function init() {
  if (!chartRef.value) return
  chart.value = echarts.init(chartRef.value)
  chart.value.setOption(buildOption(merged.value))
}

let ro = null
onMounted(() => {
  init()
  if (typeof ResizeObserver !== 'undefined' && chartRef.value) {
    ro = new ResizeObserver(() => chart.value?.resize())
    ro.observe(chartRef.value)
  }
})
onUnmounted(() => { ro?.disconnect(); chart.value?.dispose() })

watch(merged, (v) => {
  chart.value?.setOption(buildOption(v), true)
}, { deep: true })
</script>

<style scoped>
.chart {
  width: 100%;
  height: 100%;
  min-height: 200px;
}
</style>
