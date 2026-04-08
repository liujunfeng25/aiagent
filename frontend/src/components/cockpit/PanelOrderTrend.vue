<template>
  <CockpitPanel title="订单趋势" title-en="ORDER TREND">
    <div ref="chartRef" class="trend-chart" />
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
  return {
    grid: { top: 20, right: 14, bottom: 24, left: 44 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(2,6,23,0.92)',
      borderColor: 'rgba(34,211,238,0.3)',
      textStyle: { color: '#e2e8f0', fontSize: 12 },
    },
    xAxis: {
      type: 'category',
      data: data.map((r) => r.day),
      axisLabel: { color: 'rgba(148,163,184,0.7)', fontSize: 9, rotate: 35 },
      axisLine: { lineStyle: { color: 'rgba(34,211,238,0.15)' } },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: 'rgba(34,211,238,0.06)' } },
      axisLabel: { color: 'rgba(148,163,184,0.7)', fontSize: 10 },
    },
    series: [{
      type: 'bar',
      data: data.map((r) => r.order_count),
      barWidth: '50%',
      itemStyle: {
        borderRadius: [3, 3, 0, 0],
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(34,211,238,0.85)' },
          { offset: 1, color: 'rgba(34,211,238,0.18)' },
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
.trend-chart { width: 100%; height: 100%; min-height: 160px; }
</style>
