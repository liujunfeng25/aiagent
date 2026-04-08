<template>
  <CockpitPanelBlue title="背单/缺货日趋势" title-en="BACKORDER DAILY">
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
  const cnt = data.map((r) => Number(r.backorder_count || 0))
  const amt = data.map((r) => Number(r.amount_sum || 0))

  return {
    grid: { top: 24, right: 18, bottom: 32, left: 48 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(8,12,32,0.94)',
      borderColor: 'rgba(248,113,113,0.35)',
      textStyle: { color: '#e8eef8', fontSize: 12 },
    },
    legend: {
      data: ['背单笔数', '金额'],
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
        name: '笔数',
        splitLine: { lineStyle: { color: 'rgba(30,144,255,0.06)' } },
        axisLabel: { color: 'rgba(148,163,184,0.75)', fontSize: 10 },
      },
      {
        type: 'value',
        name: '金额',
        splitLine: { show: false },
        axisLabel: { color: 'rgba(251,191,36,0.7)', fontSize: 10 },
      },
    ],
    series: [
      {
        name: '背单笔数',
        type: 'bar',
        data: cnt,
        barWidth: '45%',
        itemStyle: {
          borderRadius: [4, 4, 0, 0],
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(248,113,113,0.85)' },
            { offset: 1, color: 'rgba(127,29,29,0.35)' },
          ]),
        },
      },
      {
        name: '金额',
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        data: amt,
        lineStyle: { color: '#fbbf24', width: 2 },
        itemStyle: { color: '#fbbf24' },
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
  min-height: 180px;
}
</style>
