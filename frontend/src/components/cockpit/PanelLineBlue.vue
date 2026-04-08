<template>
  <CockpitPanelBlue title="程序探究" title-en="PROGRAM ANALYTICS">
    <div ref="chartRef" class="line2-chart-blue" />
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
    grid: { top: 16, right: 14, bottom: 24, left: 44 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(5,15,50,0.94)',
      borderColor: 'rgba(0,200,255,0.3)',
      textStyle: { color: '#e8eef8', fontSize: 12 },
    },
    xAxis: {
      type: 'category',
      data: data.map((r) => r.day),
      boundaryGap: false,
      axisLabel: { color: 'rgba(140,170,220,0.7)', fontSize: 9, rotate: 35 },
      axisLine: { lineStyle: { color: 'rgba(0,200,255,0.12)' } },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: 'rgba(0,200,255,0.06)' } },
      axisLabel: { color: 'rgba(140,170,220,0.7)', fontSize: 10 },
    },
    series: [{
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 4,
      lineStyle: { color: '#00c8ff', width: 2 },
      itemStyle: { color: '#00c8ff', borderColor: '#050d2e', borderWidth: 2 },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(0,200,255,0.25)' },
          { offset: 1, color: 'rgba(0,200,255,0.01)' },
        ]),
      },
      data: data.map((r) => r.order_count),
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
.line2-chart-blue { width: 100%; height: 100%; min-height: 140px; }
</style>
