<template>
  <CockpitPanel title="订单排名" title-en="ORDER RANKING" :hint="hint">
    <div ref="chartRef" class="rank-chart" />
  </CockpitPanel>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, shallowRef } from 'vue'
import * as echarts from 'echarts'
import CockpitPanel from './CockpitPanel.vue'
import { sxTooltip, sxAxisX, sxAxisY, sxGrid, sxGlow, sxAnimation } from '../../utils/echartTheme.js'

const props = defineProps({
  data: { type: Array, default: () => [] },
  hint: { type: String, default: '' },
})

const chartRef = ref(null)
const chart = shallowRef(null)

function buildOption(data) {
  const sorted = [...data].sort((a, b) => a.gmv - b.gmv)
  return {
    ...sxAnimation,
    grid: sxGrid({ top: 8, right: 16, bottom: 18, left: 90 }),
    tooltip: sxTooltip({
      formatter(params) {
        const p = params[0]
        return `${p.name}<br/>GMV: ¥${Number(p.value).toLocaleString()}`
      },
    }),
    xAxis: {
      ...sxAxisY({
        splitLine: { lineStyle: { color: 'rgba(250,204,21,0.06)' } },
        axisLabel: { formatter: (v) => v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v },
      }),
      type: 'value',
    },
    yAxis: {
      type: 'category',
      data: sorted.map((r) => r.member_name),
      axisLabel: {
        color: '#e2e8f0',
        fontSize: 11,
        width: 80,
        overflow: 'truncate',
        textShadowBlur: 4,
        textShadowColor: 'rgba(0,0,0,0.5)',
      },
      axisLine: {
        lineStyle: {
          color: 'rgba(250,204,21,0.12)',
          shadowBlur: 6,
          shadowColor: 'rgba(34,211,238,0.18)',
        },
      },
    },
    series: [{
      type: 'bar',
      data: sorted.map((r) => r.gmv),
      barWidth: '55%',
      itemStyle: {
        borderRadius: [0, 3, 3, 0],
        borderColor: 'rgba(255,255,255,0.15)',
        borderWidth: 1,
        color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
          { offset: 0, color: 'rgba(34, 211, 238, 0.9)' },
          { offset: 0.5, color: 'rgba(56, 189, 248, 0.82)' },
          { offset: 1, color: 'rgba(250, 204, 21, 0.95)' },
        ]),
        ...sxGlow('rgba(34,211,238,0.35)', 6),
      },
      label: {
        show: true,
        position: 'right',
        color: 'rgba(226,232,240,0.92)',
        fontSize: 10,
        textShadowBlur: 4,
        textShadowColor: 'rgba(0,0,0,0.5)',
        formatter: (p) => `¥${Number(p.value).toLocaleString()}`,
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
