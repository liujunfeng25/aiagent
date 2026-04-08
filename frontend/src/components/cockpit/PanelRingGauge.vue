<template>
  <CockpitPanelBlue title="目标完成情况" title-en="TARGET COMPLETION">
    <div class="ring-gauge-wrap">
      <GlowRing :size="ringSize" />
      <div ref="chartRef" class="ring-gauge-chart" />
    </div>
  </CockpitPanelBlue>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, shallowRef } from 'vue'
import * as echarts from 'echarts'
import CockpitPanelBlue from './CockpitPanelBlue.vue'
import GlowRing from './GlowRing.vue'

const props = defineProps({
  data: { type: Object, default: () => ({}) },
})

const chartRef = ref(null)
const chart = shallowRef(null)
const ringSize = ref(130)

function buildOption(kpi) {
  const deliveryRate = kpi.deliveryRate ?? 96
  const satisfactionRate = 100 - (kpi.returnRate ?? 2)
  return {
    series: [
      {
        type: 'gauge',
        startAngle: 180,
        endAngle: 0,
        radius: '90%',
        center: ['50%', '65%'],
        min: 0,
        max: 100,
        pointer: { show: false },
        progress: {
          show: true,
          overlap: false,
          roundCap: true,
          clip: false,
          itemStyle: { color: '#1e90ff', shadowBlur: 10, shadowColor: 'rgba(30,144,255,0.6)' },
        },
        axisLine: { lineStyle: { width: 14, color: [[1, 'rgba(30,144,255,0.12)']] } },
        splitLine: {
          show: true,
          distance: -14,
          length: 8,
          lineStyle: { width: 2, color: 'rgba(30,144,255,0.25)' },
        },
        axisTick: {
          show: true,
          distance: -14,
          length: 4,
          splitNumber: 3,
          lineStyle: { width: 1, color: 'rgba(30,144,255,0.15)' },
        },
        axisLabel: { show: false },
        title: { fontSize: 11, color: 'rgba(140,170,220,0.8)', offsetCenter: [0, '35%'] },
        detail: {
          fontSize: 22,
          fontWeight: 700,
          color: '#e8eef8',
          offsetCenter: [0, '10%'],
          formatter: '{value}%',
          textShadowColor: 'rgba(30,144,255,0.5)',
          textShadowBlur: 12,
        },
        data: [{ value: deliveryRate, name: '配送及时率' }],
      },
      {
        type: 'gauge',
        startAngle: 180,
        endAngle: 0,
        radius: '68%',
        center: ['50%', '65%'],
        min: 0,
        max: 100,
        pointer: { show: false },
        progress: {
          show: true,
          overlap: false,
          roundCap: true,
          clip: false,
          itemStyle: { color: '#00c8ff', shadowBlur: 6, shadowColor: 'rgba(0,200,255,0.4)' },
        },
        axisLine: { lineStyle: { width: 10, color: [[1, 'rgba(0,200,255,0.10)']] } },
        splitLine: { show: false },
        axisTick: { show: false },
        axisLabel: { show: false },
        title: { fontSize: 10, color: 'rgba(140,170,220,0.6)', offsetCenter: [0, '35%'] },
        detail: {
          fontSize: 14,
          fontWeight: 600,
          color: 'rgba(200,230,255,0.85)',
          offsetCenter: [0, '12%'],
          formatter: '{value}%',
        },
        data: [{ value: satisfactionRate, name: '客户满意度' }],
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
  if (typeof ResizeObserver !== 'undefined') {
    ro = new ResizeObserver((entries) => {
      chart.value?.resize()
      const rect = entries[0]?.contentRect
      if (rect) {
        const dim = Math.min(rect.width, rect.height)
        ringSize.value = Math.max(dim * 0.85, 80)
      }
    })
    ro.observe(chartRef.value)
  }
})
onUnmounted(() => { ro?.disconnect(); chart.value?.dispose() })

watch(() => props.data, (v) => {
  chart.value?.setOption(buildOption(v), true)
}, { deep: true })
</script>

<style scoped>
.ring-gauge-wrap {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 160px;
}

.ring-gauge-chart {
  width: 100%;
  height: 100%;
  position: relative;
  z-index: 1;
}
</style>
