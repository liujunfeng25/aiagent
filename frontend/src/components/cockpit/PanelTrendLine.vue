<template>
  <CockpitPanel title="GMV 走势" title-en="GMV TREND LINE">
    <div ref="chartRef" class="line-chart" />
  </CockpitPanel>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, shallowRef } from 'vue'
import * as echarts from 'echarts'
import CockpitPanel from './CockpitPanel.vue'
import { sxVar } from '../../utils/sxCss.js'

const props = defineProps({
  data: { type: Array, default: () => [] },
})

const chartRef = ref(null)
const chart = shallowRef(null)

function buildOption(data) {
  return {
    grid: { top: 18, right: 14, bottom: 32, left: 52 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: sxVar('--sx-chart-tooltip-bg'),
      borderColor: 'rgba(250, 204, 21, 0.35)',
      borderWidth: 1,
      textStyle: { color: '#f8fafc', fontSize: 13 },
      formatter(params) {
        const p = params[0]
        return `${p.name}<br/>GMV: ¥${Number(p.value).toLocaleString()}`
      },
    },
    xAxis: {
      type: 'category',
      data: data.map((r) => r.day),
      boundaryGap: false,
      axisLabel: { color: sxVar('--sx-chart-axis-muted'), fontSize: 9, rotate: 35 },
      axisLine: { lineStyle: { color: sxVar('--sx-chart-axis-line-cyan') } },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: sxVar('--sx-chart-split-cyan') } },
      axisLabel: { color: sxVar('--sx-chart-axis-muted'), fontSize: 10, formatter: (v) => v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v },
    },
    series: [{
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 5,
      lineStyle: { color: '#fbbf24', width: 2 },
      itemStyle: { color: '#fbbf24', borderColor: sxVar('--sx-chart-line-point-border'), borderWidth: 2 },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(251, 191, 36, 0.38)' },
          { offset: 1, color: 'rgba(251, 191, 36, 0.02)' },
        ]),
      },
      data: data.map((r) => r.gmv),
    }],
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
  if (typeof ResizeObserver !== 'undefined') {
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
.line-chart { width: 100%; height: 100%; min-height: 140px; }
</style>
