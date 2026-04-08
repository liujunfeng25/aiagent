<template>
  <CockpitPanel title="周内成交结构" title-en="WEEKDAY PROFILE">
    <div ref="chartRef" class="wk-chart" />
  </CockpitPanel>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, shallowRef } from 'vue'
import * as echarts from 'echarts'
import CockpitPanel from './CockpitPanel.vue'

const props = defineProps({
  /** orders-daily series: { day, order_count, gmv }[] */
  data: { type: Array, default: () => [] },
})

const chartRef = ref(null)
const chart = shallowRef(null)

const LABELS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

/** 周一=0 … 周日=6 */
function mondayFirstIndex(dateStr) {
  const s = String(dateStr || '').slice(0, 10)
  const d = new Date(`${s}T12:00:00`)
  if (Number.isNaN(d.getTime())) return null
  const sun0 = d.getDay()
  return sun0 === 0 ? 6 : sun0 - 1
}

function aggregate(rows) {
  const orders = [0, 0, 0, 0, 0, 0, 0]
  const gmv = [0, 0, 0, 0, 0, 0, 0]
  for (const r of rows || []) {
    const i = mondayFirstIndex(r.day)
    if (i == null) continue
    orders[i] += Number(r.order_count || 0)
    gmv[i] += Number(r.gmv || 0)
  }
  return { orders, gmv }
}

function buildOption(raw) {
  const { orders, gmv } = aggregate(raw)
  const maxO = Math.max(...orders, 1)

  return {
    grid: { top: 18, right: 12, bottom: 8, left: 44 },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: 'rgba(2,6,23,0.92)',
      borderColor: 'rgba(34,211,238,0.35)',
      textStyle: { color: '#e2e8f0', fontSize: 12 },
      formatter(params) {
        const p = params[0]
        const i = p.dataIndex
        return `${LABELS[i]}<br/>订单: ${orders[i].toLocaleString()}<br/>GMV: ¥${Number(gmv[i]).toLocaleString()}`
      },
    },
    xAxis: {
      type: 'category',
      data: LABELS,
      axisLabel: { color: 'rgba(148,163,184,0.85)', fontSize: 10 },
      axisLine: { lineStyle: { color: 'rgba(34,211,238,0.2)' } },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: 'rgba(34,211,238,0.06)' } },
      axisLabel: {
        color: 'rgba(148,163,184,0.72)',
        fontSize: 10,
      },
    },
    series: [{
      type: 'bar',
      barMaxWidth: 28,
      barGap: '12%',
      data: orders.map((c, i) => {
        const t = maxO > 0 ? c / maxO : 0
        const top = t > 0.85 ? '#22d3ee' : t > 0.5 ? '#38bdf8' : '#0e7490'
        return {
          value: c,
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 1, 0, 0, [
              { offset: 0, color: 'rgba(15,23,42,0.9)' },
              { offset: 1, color: top },
            ]),
            borderRadius: [4, 4, 0, 0],
          },
        }
      }),
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
.wk-chart {
  width: 100%;
  height: 100%;
  min-height: 200px;
}
</style>
