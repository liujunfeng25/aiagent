<template>
  <CockpitPanelBlue title="新发地批发价带状走势" title-en="XFD PRICE BAND">
    <div ref="chartRef" class="chart" />
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
  const days = data.map((r) => String(r.day).slice(0, 10))
  const minP = data.map((r) => Number(r.min_price || 0))
  const maxP = data.map((r) => Number(r.max_price || 0))
  const avgP = data.map((r) => Number(r.avg_price || 0))
  const qty = data.map((r) => Number(r.quantity || 0))

  return {
    grid: { top: 36, right: 48, bottom: 28, left: 52 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(8,12,32,0.94)',
      borderColor: 'rgba(30,144,255,0.4)',
      textStyle: { color: '#e8eef8', fontSize: 12 },
    },
    legend: {
      data: ['最低价', '均价', '最高价', '成交量'],
      textStyle: { color: 'rgba(148,163,184,0.85)', fontSize: 10 },
      top: 0,
    },
    xAxis: {
      type: 'category',
      data: days,
      axisLabel: { color: 'rgba(148,163,184,0.75)', fontSize: 9, rotate: 30 },
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
        name: '量',
        splitLine: { show: false },
        axisLabel: { color: 'rgba(34,211,238,0.65)', fontSize: 10 },
      },
    ],
    series: [
      {
        name: '最低价',
        type: 'line',
        data: minP,
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1, color: 'rgba(34,211,238,0.45)' },
      },
      {
        name: '均价',
        type: 'line',
        data: avgP,
        smooth: true,
        symbol: 'circle',
        symbolSize: 4,
        lineStyle: { width: 2.5, color: '#1e90ff' },
        itemStyle: { color: '#7dd3fc' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(30,144,255,0.25)' },
            { offset: 1, color: 'rgba(30,144,255,0.02)' },
          ]),
        },
      },
      {
        name: '最高价',
        type: 'line',
        data: maxP,
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1, color: 'rgba(250,204,21,0.5)' },
      },
      {
        name: '成交量',
        type: 'bar',
        yAxisIndex: 1,
        data: qty,
        barWidth: '35%',
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(34,211,238,0.55)' },
            { offset: 1, color: 'rgba(34,211,238,0.08)' },
          ]),
        },
      },
    ],
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
  min-height: 220px;
}
</style>
