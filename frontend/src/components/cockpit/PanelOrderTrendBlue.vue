<template>
  <CockpitPanelBlue title="产业架构优化预测" title-en="INDUSTRY FORECAST">
    <div ref="chartRef" class="trend-chart-blue" />
  </CockpitPanelBlue>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, shallowRef } from 'vue'
import * as echarts from 'echarts'
import CockpitPanelBlue from './CockpitPanelBlue.vue'

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
      backgroundColor: 'rgba(5,15,50,0.94)',
      borderColor: 'rgba(30,144,255,0.3)',
      textStyle: { color: '#e8eef8', fontSize: 12 },
    },
    xAxis: {
      type: 'category',
      data: data.map((r) => r.day),
      axisLabel: { color: 'rgba(140,170,220,0.7)', fontSize: 9, rotate: 35 },
      axisLine: { lineStyle: { color: 'rgba(30,144,255,0.18)' } },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: 'rgba(30,144,255,0.06)' } },
      axisLabel: { color: 'rgba(140,170,220,0.7)', fontSize: 10 },
    },
    series: [{
      type: 'bar',
      data: data.map((r) => r.order_count),
      barWidth: '50%',
      itemStyle: {
        borderRadius: [3, 3, 0, 0],
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(30,144,255,0.85)' },
          { offset: 1, color: 'rgba(30,144,255,0.15)' },
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
.trend-chart-blue { width: 100%; height: 100%; min-height: 160px; }
</style>
