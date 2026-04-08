<template>
  <CockpitPanel title="订单排名" title-en="ORDER RANKING">
    <div ref="chartRef" class="rank-chart" />
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
  const sorted = [...data].sort((a, b) => a.gmv - b.gmv)
  return {
    grid: { top: 8, right: 16, bottom: 18, left: 90 },
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
      type: 'value',
      splitLine: { lineStyle: { color: 'rgba(250,204,21,0.06)' } },
      axisLabel: { color: 'rgba(148,163,184,0.7)', fontSize: 10, formatter: (v) => v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v },
    },
    yAxis: {
      type: 'category',
      data: sorted.map((r) => r.member_name),
      axisLabel: { color: '#e2e8f0', fontSize: 10, width: 80, overflow: 'truncate' },
      axisLine: { lineStyle: { color: 'rgba(250,204,21,0.12)' } },
    },
    series: [{
      type: 'bar',
      data: sorted.map((r) => r.gmv),
      barWidth: '55%',
      itemStyle: {
        borderRadius: [0, 3, 3, 0],
        color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
          { offset: 0, color: 'rgba(250,204,21,0.65)' },
          { offset: 1, color: 'rgba(34,211,238,0.85)' },
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
.rank-chart { width: 100%; height: 100%; min-height: 160px; }
</style>
