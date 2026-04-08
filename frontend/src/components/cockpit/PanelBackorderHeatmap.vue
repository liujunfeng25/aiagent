<template>
  <CockpitPanelBlue title="背单强度日历" title-en="BACKORDER HEAT">
    <div ref="chartRef" class="chart" />
  </CockpitPanelBlue>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, shallowRef } from 'vue'
import * as echarts from 'echarts'
import CockpitPanelBlue from './CockpitPanelBlue.vue'

const props = defineProps({
  /** { day, backorder_count }[] */
  data: { type: Array, default: () => [] },
})

const chartRef = ref(null)
const chart = shallowRef(null)

function buildOption(rows) {
  const cells = rows.map((r) => ({
    date: String(r.day).slice(0, 10),
    v: Number(r.backorder_count || 0),
  }))
  const dates = cells.map((c) => c.date).filter(Boolean).sort()
  const calRange = dates.length ? [dates[0], dates[dates.length - 1]] : ['2020-01-01', '2020-01-01']
  const data = cells.map((c) => [c.date, c.v])
  const vals = cells.map((c) => c.v).filter((v) => v > 0)
  const vmax = vals.length ? Math.max(...vals) : 1
  const vmin = vals.length ? Math.min(...vals) : 0

  return {
    tooltip: {
      position: 'top',
      backgroundColor: 'rgba(8,12,32,0.94)',
      borderColor: 'rgba(248,113,113,0.35)',
      textStyle: { color: '#e8eef8', fontSize: 12 },
      formatter(p) {
        return `${p.value[0]}<br/>背单: ${p.value[1]}`
      },
    },
    visualMap: {
      min: vmin,
      max: vmax || 1,
      calculable: false,
      orient: 'horizontal',
      left: 'center',
      bottom: 2,
      inRange: { color: ['#1e1b4b', '#7f1d1d', '#ef4444', '#fca5a5'] },
      textStyle: { color: '#94a3b8', fontSize: 10 },
    },
    calendar: {
      range: calRange,
      cellSize: [11, 11],
      splitLine: { lineStyle: { color: 'rgba(30,144,255,0.12)' } },
      itemStyle: { borderWidth: 1, borderColor: 'rgba(15,23,42,0.95)' },
      dayLabel: { firstDay: 1, color: 'rgba(148,163,184,0.65)', fontSize: 9 },
      monthLabel: { color: 'rgba(148,163,184,0.75)', fontSize: 9 },
      yearLabel: { show: false },
    },
    series: [{ type: 'heatmap', coordinateSystem: 'calendar', data }],
  }
}

function init() {
  if (!chartRef.value) return
  chart.value = echarts.init(chartRef.value)
  chart.value.setOption(buildOption(props.data))
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

watch(() => props.data, (v) => {
  chart.value?.setOption(buildOption(v), true)
}, { deep: true })
</script>

<style scoped>
.chart {
  width: 100%;
  height: 100%;
  min-height: 180px;
}
</style>
