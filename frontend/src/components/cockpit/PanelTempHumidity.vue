<template>
  <CockpitPanelBlue title="温湿度监控" title-en="TEMP & HUMIDITY">
    <div ref="chartRef" class="th-chart" />
  </CockpitPanelBlue>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, shallowRef } from 'vue'
import * as echarts from 'echarts'
import CockpitPanelBlue from './CockpitPanelBlue.vue'

const props = defineProps({
  data: { type: Array, default: () => [] },
  threshold: { type: Number, default: 8 },
})

const chartRef = ref(null)
const chart = shallowRef(null)
let ro = null

function buildOption() {
  const hours = props.data.map((d) => d.hour)
  const temps = props.data.map((d) => d.temperature)
  const hums = props.data.map((d) => d.humidity)
  return {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(5,15,50,0.92)',
      borderColor: 'rgba(30,144,255,0.3)',
      textStyle: { color: '#e8eef8', fontSize: 11 },
    },
    legend: {
      data: ['温度 (°C)', '湿度 (%)'],
      textStyle: { color: 'rgba(140,170,220,0.7)', fontSize: 10 },
      top: 0,
      right: 0,
      itemWidth: 12,
      itemHeight: 8,
    },
    grid: { top: 28, left: 36, right: 36, bottom: 20 },
    xAxis: {
      type: 'category',
      data: hours,
      axisLabel: { color: 'rgba(140,170,220,0.6)', fontSize: 9, interval: 3 },
      axisLine: { lineStyle: { color: 'rgba(30,144,255,0.15)' } },
      axisTick: { show: false },
    },
    yAxis: [
      {
        type: 'value',
        name: '°C',
        nameTextStyle: { color: 'rgba(140,170,220,0.5)', fontSize: 9 },
        axisLabel: { color: 'rgba(140,170,220,0.6)', fontSize: 9 },
        splitLine: { lineStyle: { color: 'rgba(30,144,255,0.08)' } },
      },
      {
        type: 'value',
        name: '%',
        nameTextStyle: { color: 'rgba(140,170,220,0.5)', fontSize: 9 },
        axisLabel: { color: 'rgba(140,170,220,0.6)', fontSize: 9 },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: '温度 (°C)',
        type: 'line',
        data: temps,
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#1e90ff', width: 2 },
        areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(30,144,255,0.25)' },
          { offset: 1, color: 'rgba(30,144,255,0.02)' },
        ]) },
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { color: '#f87171', type: 'dashed', width: 1 },
          label: { formatter: `阈值 ${props.threshold}°C`, color: '#fca5a5', fontSize: 9 },
          data: [{ yAxis: props.threshold }],
        },
      },
      {
        name: '湿度 (%)',
        type: 'line',
        yAxisIndex: 1,
        data: hums,
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#22d3ee', width: 2 },
        areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(34,211,238,0.18)' },
          { offset: 1, color: 'rgba(34,211,238,0.01)' },
        ]) },
      },
    ],
  }
}

onMounted(() => {
  if (!chartRef.value) return
  chart.value = echarts.init(chartRef.value, null, { renderer: 'canvas' })
  chart.value.setOption(buildOption())
  ro = new ResizeObserver(() => chart.value?.resize())
  ro.observe(chartRef.value)
})

watch(() => props.data, () => {
  chart.value?.setOption(buildOption(), true)
}, { deep: true })

onUnmounted(() => {
  ro?.disconnect()
  chart.value?.dispose()
})
</script>

<style scoped>
.th-chart { width: 100%; height: 100%; min-height: 80px; }
</style>
