<template>
  <CockpitPanel title="日内成交结构" title-en="INTRADAY PROFILE">
    <div ref="chartRef" class="intra-chart" />
  </CockpitPanel>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, shallowRef } from 'vue'
import * as echarts from 'echarts'
import CockpitPanel from './CockpitPanel.vue'

const props = defineProps({
  /** 原始分钟桶 [minute_start_ts_sec, bucket_gmv][] */
  rawBuckets: { type: Array, default: () => [] },
  /** 今日零点 UNIX 秒 */
  axisDayStartTs: { type: Number, default: 0 },
  /** 保留旧 prop 以免智能驾驶舱 tab 报错 */
  data: { type: Array, default: () => [] },
})

const chartRef = ref(null)
const chart = shallowRef(null)

const LABELS = ['00-03', '03-06', '06-09', '09-12', '12-15', '15-18', '18-21', '21-24']
const SLOT_SECS = 3 * 3600

function aggregate(buckets, t0) {
  const gmv = new Array(8).fill(0)
  const orders = new Array(8).fill(0)
  if (!t0) return { gmv, orders }
  for (const [ts, val] of buckets) {
    const offset = Number(ts) - t0
    if (offset < 0 || offset >= 86400) continue
    const idx = Math.min(Math.floor(offset / SLOT_SECS), 7)
    gmv[idx] += Number(val) || 0
    orders[idx] += 1
  }
  return { gmv, orders }
}

function buildOption(buckets, t0) {
  const { gmv } = aggregate(buckets, t0)
  const maxG = Math.max(...gmv, 1)

  return {
    grid: { top: 18, right: 12, bottom: 8, left: 50 },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: 'rgba(2,6,23,0.92)',
      borderColor: 'rgba(250,204,21,0.35)',
      textStyle: { color: '#e2e8f0', fontSize: 12 },
      formatter(params) {
        const p = params[0]
        const i = p.dataIndex
        return `${LABELS[i]}<br/>GMV: ¥${Number(gmv[i]).toLocaleString()}`
      },
    },
    xAxis: {
      type: 'category',
      data: LABELS,
      axisLabel: { color: 'rgba(148,163,184,0.85)', fontSize: 10 },
      axisLine: { lineStyle: { color: 'rgba(250,204,21,0.2)' } },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: 'rgba(250,204,21,0.06)' } },
      axisLabel: {
        color: 'rgba(148,163,184,0.72)',
        fontSize: 10,
        formatter: (v) => (v >= 1000 ? `${(v / 1000).toFixed(1)}k` : v),
      },
    },
    series: [{
      type: 'bar',
      barMaxWidth: 48,
      barMinWidth: 14,
      barCategoryGap: '32%',
      data: gmv.map((c) => {
        const t = maxG > 0 ? c / maxG : 0
        const top = t > 0.85 ? '#fbbf24' : t > 0.5 ? '#f59e0b' : '#92400e'
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
  chart.value.setOption(buildOption(props.rawBuckets, props.axisDayStartTs))
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

watch(
  () => [props.rawBuckets, props.axisDayStartTs],
  () => {
    chart.value?.setOption(buildOption(props.rawBuckets, props.axisDayStartTs), true)
  },
  { deep: true },
)
</script>

<style scoped>
.intra-chart {
  width: 100%;
  height: 100%;
  min-height: 160px;
}
</style>
