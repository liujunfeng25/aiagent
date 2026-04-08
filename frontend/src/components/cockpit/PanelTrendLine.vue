<template>
  <CockpitPanel title="GMV 走势" title-en="GMV TREND LINE">
    <div ref="chartRef" class="line-chart" />
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
    grid: { top: 20, right: 14, bottom: 24, left: 52 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(2,6,23,0.92)',
      borderColor: 'rgba(250,204,21,0.3)',
      textStyle: { color: '#e2e8f0', fontSize: 12 },
      formatter(params) {
        const p = params[0]
        return `${p.name}<br/>GMV: ¥${Number(p.value).toLocaleString()}`
      },
    },
    xAxis: {
      type: 'category',
      data: data.map((r) => r.day),
      boundaryGap: false,
      axisLabel: { color: 'rgba(148,163,184,0.7)', fontSize: 9, rotate: 35 },
      axisLine: { lineStyle: { color: 'rgba(250,204,21,0.12)' } },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: 'rgba(250,204,21,0.06)' } },
      axisLabel: { color: 'rgba(148,163,184,0.7)', fontSize: 10, formatter: (v) => v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v },
    },
    series: [{
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 5,
      lineStyle: { color: '#f0c040', width: 2 },
      itemStyle: { color: '#f0c040', borderColor: '#0a0f23', borderWidth: 2 },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(240,192,64,0.35)' },
          { offset: 1, color: 'rgba(240,192,64,0.02)' },
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
