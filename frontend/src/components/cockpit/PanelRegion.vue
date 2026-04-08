<template>
  <CockpitPanel title="区域分布" title-en="REGION DISTRIBUTION">
    <div ref="chartRef" class="region-chart" />
  </CockpitPanel>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, shallowRef } from 'vue'
import * as echarts from 'echarts'
import CockpitPanel from './CockpitPanel.vue'

const props = defineProps({
  data: { type: Array, default: () => [] },
})

const chartRef = ref(null)
const chart = shallowRef(null)

function buildOption(data) {
  const sorted = [...data].sort((a, b) => a.order_count - b.order_count)
  return {
    grid: { top: 8, right: 16, bottom: 18, left: 72 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(2,6,23,0.92)',
      borderColor: 'rgba(34,211,238,0.3)',
      textStyle: { color: '#e2e8f0', fontSize: 12 },
    },
    xAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: 'rgba(34,211,238,0.08)' } },
      axisLabel: { color: 'rgba(148,163,184,0.7)', fontSize: 10 },
    },
    yAxis: {
      type: 'category',
      data: sorted.map((r) => r.region_name),
      axisLabel: { color: '#e2e8f0', fontSize: 11 },
      axisLine: { lineStyle: { color: 'rgba(34,211,238,0.15)' } },
    },
    series: [{
      type: 'bar',
      data: sorted.map((r) => r.order_count),
      barWidth: '55%',
      itemStyle: {
        borderRadius: [0, 3, 3, 0],
        color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
          { offset: 0, color: 'rgba(34,211,238,0.7)' },
          { offset: 1, color: 'rgba(250,204,21,0.85)' },
        ]),
      },
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
.region-chart { width: 100%; height: 100%; min-height: 160px; }
</style>
