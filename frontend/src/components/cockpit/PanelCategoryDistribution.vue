<template>
  <CockpitPanel title="类别分布" title-en="CATEGORY DISTRIBUTION">
    <div ref="chartRef" class="category-chart" />
  </CockpitPanel>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, shallowRef } from 'vue'
import * as echarts from 'echarts'
import CockpitPanel from './CockpitPanel.vue'
import { sxVar } from '../../utils/sxCss.js'

const props = defineProps({
  data: { type: Array, default: () => [] },
})

const chartRef = ref(null)
const chart = shallowRef(null)

function buildOption(data) {
  const sorted = [...data].sort((a, b) => Number(a.line_gmv || 0) - Number(b.line_gmv || 0))
  const axisBright = 'rgba(226, 232, 240, 0.95)'
  return {
    grid: { top: 8, right: 12, bottom: 18, left: 100 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: sxVar('--sx-chart-tooltip-bg'),
      borderColor: 'rgba(250, 204, 21, 0.35)',
      borderWidth: 1,
      textStyle: { color: '#f8fafc', fontSize: 13 },
      extraCssText: 'box-shadow:0 4px 14px rgba(0,0,0,0.45);',
      formatter(params) {
        const p = params[0]
        if (!p) return ''
        const row = sorted[p.dataIndex]
        const oc = row?.order_count != null ? row.order_count : '—'
        const lc = row?.line_count != null ? row.line_count : '—'
        return `${p.name}<br/>明细金额：${Number(p.value).toFixed(2)} 元<br/>订单数：${oc} · 明细行：${lc}`
      },
    },
    xAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: sxVar('--sx-chart-split-cyan-mid') } },
      axisLabel: { color: sxVar('--sx-chart-axis-muted'), fontSize: 10 },
    },
    yAxis: {
      type: 'category',
      data: sorted.map((r) => r.category_name || '—'),
      axisLabel: {
        color: axisBright,
        fontSize: 11,
        lineHeight: 16,
        width: 118,
        overflow: 'truncate',
      },
      axisLine: { lineStyle: { color: sxVar('--sx-chart-axis-line-cyan-strong') } },
    },
    series: [{
      type: 'bar',
      data: sorted.map((r) => Number(r.line_gmv || 0)),
      barWidth: '55%',
      itemStyle: {
        borderRadius: [0, 3, 3, 0],
        color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
          { offset: 0, color: sxVar('--sx-chart-bar-region-0') },
          { offset: 1, color: sxVar('--sx-chart-bar-region-1') },
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
.category-chart { width: 100%; height: 100%; min-height: 160px; }
</style>
