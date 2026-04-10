<template>
  <CockpitPanel title="单品分布" title-en="PRODUCT DISTRIBUTION" :hint="hint">
    <div ref="chartRef" class="goods-chart" />
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

const COLORS = [
  '#56c8d8', '#e06b75', '#9b7fd4', '#d4b856',
  '#4db89a', '#d46a7e', '#5b9bd5', '#cf7a3a',
  '#c275d4', '#7ab33e', '#42b5a8', '#c96d9a',
]

function buildOption(data) {
  const rows = [...(data || [])]
    .sort((a, b) => Number(b.total_amount || 0) - Number(a.total_amount || 0))
    .slice(0, 8)

  const names = rows.map((r) => r.goods_name || '—')
  const amounts = rows.map((r) => Number(r.total_amount || 0))

  return {
    ...sxAnimation,
    grid: sxGrid({ left: 4, right: 70, top: 12, bottom: 4, containLabel: true }),
    tooltip: sxTooltip({
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter(params) {
        const p = params[0]
        const i = p.dataIndex
        const name = names[i] || ''
        const amt = amounts[i]
        const qty = rows[i]?.total_qty
        const qStr = qty != null ? `<br/>数量: ${Number(qty).toLocaleString()}` : ''
        return `${name}<br/>金额: ¥${Number(amt).toLocaleString()}${qStr}`
      },
    }),
    xAxis: {
      ...sxAxisY({
        splitLine: { lineStyle: { color: 'rgba(34,211,238,0.06)' } },
        axisLabel: {
          formatter: (v) => (v >= 10000 ? `${(v / 10000).toFixed(1)}万` : v),
        },
      }),
      type: 'value',
    },
    yAxis: {
      type: 'category',
      data: names,
      inverse: true,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: 'rgba(203,213,225,0.92)',
        fontSize: 10,
        lineHeight: 14,
        width: 108,
        overflow: 'truncate',
        ellipsis: '…',
        margin: 6,
        textShadowBlur: 4,
        textShadowColor: 'rgba(0,0,0,0.5)',
      },
    },
    series: [{
      type: 'bar',
      barCategoryGap: '32%',
      data: amounts.map((v, i) => ({
        value: v,
        itemStyle: {
          color: COLORS[i % COLORS.length],
          borderRadius: [0, 4, 4, 0],
          ...sxGlow(COLORS[i % COLORS.length] + '66', 4),
        },
      })),
      barMaxWidth: 22,
      label: {
        show: true,
        position: 'right',
        color: 'rgba(226,232,240,0.92)',
        fontSize: 10,
        textShadowBlur: 4,
        textShadowColor: 'rgba(0,0,0,0.5)',
        formatter(p) {
          const n = p.value
          return n >= 10000 ? `${(n / 10000).toFixed(1)}万` : `${Math.round(n)}`
        },
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
.goods-chart {
  width: 100%;
  height: 100%;
  min-height: 160px;
}
</style>
