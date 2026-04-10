<template>
  <CockpitPanel title="GMV 走势" title-en="GMV TREND LINE">
    <div ref="chartRef" class="line-chart" />
  </CockpitPanel>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, shallowRef } from 'vue'
import * as echarts from 'echarts'
import CockpitPanel from './CockpitPanel.vue'
import { sxTooltip, sxAxisX, sxAxisY, sxGrid, sxGlow, sxAnimation } from '../../utils/echartTheme.js'

const props = defineProps({
  data: { type: Array, default: () => [] },
})

const chartRef = ref(null)
const chart = shallowRef(null)

function buildOption(data) {
  return {
    ...sxAnimation,
    grid: sxGrid(),
    tooltip: sxTooltip({
      formatter(params) {
        const p = params[0]
        return `${p.name}<br/>GMV: ¥${Number(p.value).toLocaleString()}`
      },
    }),
    xAxis: {
      ...sxAxisX({ axisLabel: { fontSize: 10, rotate: 35 } }),
      type: 'category',
      data: data.map((r) => r.day),
      boundaryGap: false,
    },
    yAxis: {
      ...sxAxisY({
        axisLabel: { formatter: (v) => v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v },
      }),
      type: 'value',
    },
    series: [{
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      lineStyle: {
        color: '#fbbf24',
        width: 2.5,
        ...sxGlow('rgba(251,191,36,0.4)', 8),
      },
      itemStyle: {
        color: '#fbbf24',
        borderColor: '#0a0f23',
        borderWidth: 2,
        shadowBlur: 12,
        shadowColor: 'rgba(251,191,36,0.45)',
      },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(251, 191, 36, 0.50)' },
          { offset: 0.45, color: 'rgba(34, 211, 238, 0.12)' },
          { offset: 1, color: 'rgba(251, 191, 36, 0.02)' },
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
