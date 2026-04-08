<template>
  <CockpitPanelBlue title="年度经济增长点" title-en="ANNUAL GROWTH">
    <div class="donut-wrap">
      <div class="donut-chart-area">
        <GlowRing :size="ringSize" />
        <div ref="chartRef" class="donut-chart" />
      </div>
      <div class="donut-stats">
        <div v-for="item in statItems" :key="item.label" class="donut-stat">
          <span class="donut-stat__val">{{ item.value }}</span>
          <span class="donut-stat__label">{{ item.label }}</span>
        </div>
      </div>
    </div>
  </CockpitPanelBlue>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, shallowRef } from 'vue'
import * as echarts from 'echarts'
import CockpitPanelBlue from './CockpitPanelBlue.vue'
import GlowRing from './GlowRing.vue'

const props = defineProps({
  data: { type: Array, default: () => [] },
  kpi: { type: Object, default: () => ({}) },
})

const chartRef = ref(null)
const chart = shallowRef(null)
const ringSize = ref(130)

const COLORS = [
  '#1e90ff', '#00c8ff', '#4da6ff', '#0070cc',
  '#66b3ff', '#0099e6', '#3385cc', '#1aa3ff',
  '#007acc', '#005999',
]

const statItems = computed(() => {
  const d = props.kpi
  return [
    { label: '今日订单', value: d.todayOrders ?? '--' },
    { label: '新增客户', value: d.newCustomers ?? '--' },
    { label: '客单价', value: d.avgOrderAmount ? `¥${d.avgOrderAmount}` : '--' },
  ]
})

function buildOption(data) {
  const total = data.reduce((s, g) => s + (g.total_amount || 0), 0)
  return {
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(5,15,50,0.94)',
      borderColor: 'rgba(30,144,255,0.3)',
      textStyle: { color: '#e8eef8', fontSize: 12 },
      formatter: '{b}: ¥{c} ({d}%)',
    },
    series: [{
      type: 'pie',
      radius: ['48%', '72%'],
      center: ['50%', '50%'],
      avoidLabelOverlap: true,
      label: { show: false },
      emphasis: {
        label: { show: true, color: '#e8eef8', fontSize: 12 },
        itemStyle: { shadowBlur: 14, shadowColor: 'rgba(30,144,255,0.5)' },
      },
      itemStyle: { borderColor: 'rgba(5,15,50,0.9)', borderWidth: 2 },
      data: data.slice(0, 6).map((g, i) => ({
        name: g.goods_name,
        value: g.total_amount,
        itemStyle: { color: COLORS[i % COLORS.length] },
      })),
    }],
    graphic: [{
      type: 'text',
      left: 'center',
      top: '44%',
      style: {
        text: `¥${(total / 1000).toFixed(0)}k`,
        textAlign: 'center',
        fill: '#e8eef8',
        fontSize: 16,
        fontWeight: 700,
        textShadowColor: 'rgba(30,144,255,0.4)',
        textShadowBlur: 8,
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
.donut-wrap {
  display: flex;
  width: 100%;
  height: 100%;
  min-height: 160px;
}

.donut-chart-area {
  position: relative;
  flex: 1;
  min-width: 0;
  perspective: 500px;
}

.donut-chart {
  width: 100%;
  height: 100%;
  position: relative;
  z-index: 1;
  transform: rotateX(30deg) scale(1.05);
  transform-origin: center 60%;
}

.donut-stats {
  width: 70px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 12px;
  flex-shrink: 0;
}

.donut-stat {
  text-align: center;
}

.donut-stat__val {
  display: block;
  font-size: 16px;
  font-weight: 700;
  color: #e8eef8;
  text-shadow: 0 0 8px rgba(30, 144, 255, 0.4);
  font-variant-numeric: tabular-nums;
}

.donut-stat__label {
  display: block;
  font-size: 10px;
  color: rgba(140, 170, 220, 0.7);
  margin-top: 2px;
}
</style>
