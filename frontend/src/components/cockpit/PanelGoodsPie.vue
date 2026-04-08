<template>
  <CockpitPanel title="单品分布" title-en="PRODUCT DISTRIBUTION">
    <div ref="chartRef" class="goods-chart" />
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

const COLORS = [
  '#22d3ee', '#ff6b6b', '#a78bfa', '#facc15',
  '#34d399', '#fb7185', '#60a5fa', '#f97316',
  '#e879f9', '#84cc16', '#2dd4bf', '#f472b6',
]

function buildOption(data) {
  const rows = [...(data || [])]
    .sort((a, b) => Number(b.total_amount || 0) - Number(a.total_amount || 0))
    .slice(0, 8)

  const names = rows.map((r) => r.goods_name || '—')
  const amounts = rows.map((r) => Number(r.total_amount || 0))

  return {
    grid: {
      left: 4,
      right: 70,
      top: 12,
      bottom: 4,
      containLabel: true,
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: 'rgba(2,6,23,0.92)',
      borderColor: 'rgba(34,211,238,0.3)',
      textStyle: { color: '#e2e8f0', fontSize: 12 },
      formatter(params) {
        const p = params[0]
        const i = p.dataIndex
        const name = names[i] || ''
        const amt = amounts[i]
        const qty = rows[i]?.total_qty
        const qStr = qty != null ? `<br/>数量: ${Number(qty).toLocaleString()}` : ''
        return `${name}<br/>金额: ¥${Number(amt).toLocaleString()}${qStr}`
      },
    },
    xAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: 'rgba(34,211,238,0.06)' } },
      axisLabel: {
        color: 'rgba(148,163,184,0.72)',
        fontSize: 10,
        formatter: (v) => (v >= 10000 ? `${(v / 10000).toFixed(1)}万` : v),
      },
    },
    yAxis: {
      type: 'category',
      data: names,
      inverse: true,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: 'rgba(203,213,225,0.92)',
        fontSize: 9,
        lineHeight: 14,
        width: 108,
        overflow: 'truncate',
        ellipsis: '…',
        margin: 6,
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
        },
      })),
      barMaxWidth: 22,
      label: {
        show: true,
        position: 'right',
        color: 'rgba(226,232,240,0.88)',
        fontSize: 9,
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
