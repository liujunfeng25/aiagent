<template>
  <CockpitPanel title="单品分布" title-en="PRODUCT DISTRIBUTION">
    <div ref="chartRef" class="pie-chart" />
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
  '#e879f9', '#84cc16',
]

function buildOption(data) {
  return {
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(2,6,23,0.92)',
      borderColor: 'rgba(34,211,238,0.3)',
      textStyle: { color: '#e2e8f0', fontSize: 12 },
      formatter: '{b}: ¥{c} ({d}%)',
    },
    legend: {
      orient: 'vertical',
      right: 6,
      top: 'center',
      textStyle: { color: 'rgba(148,163,184,0.85)', fontSize: 10 },
      itemWidth: 10,
      itemHeight: 10,
    },
    series: [{
      type: 'pie',
      radius: ['40%', '68%'],
      center: ['38%', '50%'],
      avoidLabelOverlap: true,
      label: { show: false },
      emphasis: {
        label: { show: true, color: '#e2e8f0', fontSize: 12 },
        itemStyle: { shadowBlur: 14, shadowColor: 'rgba(34,211,238,0.4)' },
      },
      itemStyle: { borderColor: 'rgba(10,15,35,0.9)', borderWidth: 2 },
      data: data.map((g, i) => ({
        name: g.goods_name,
        value: g.total_amount,
        itemStyle: { color: COLORS[i % COLORS.length] },
      })),
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
.pie-chart { width: 100%; height: 100%; min-height: 160px; }
</style>
