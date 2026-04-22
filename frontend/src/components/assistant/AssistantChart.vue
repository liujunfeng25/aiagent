<template>
  <div class="sx-asst-chart" ref="wrap">
    <div class="sx-asst-chart__inner" ref="el" />
  </div>
</template>

<script setup>
import { onMounted, onBeforeUnmount, ref, watch, nextTick } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  spec: { type: Object, required: true },
})

const wrap = ref(null)
const el = ref(null)
let inst = null
let ro = null

const PALETTE = ['#6366f1', '#8b5cf6', '#22d3ee', '#f472b6', '#34d399', '#fbbf24', '#f87171', '#60a5fa']

function normalizeSeries(spec) {
  const arr = Array.isArray(spec?.series) ? spec.series : []
  return arr
    .map((s) => (s && typeof s === 'object') ? s : null)
    .filter(Boolean)
}

function buildLineOrBar(kind, spec) {
  const x = Array.isArray(spec?.x) ? spec.x : []
  const series = normalizeSeries(spec).map((s, i) => ({
    name: s.name || `系列 ${i + 1}`,
    type: kind,
    smooth: kind === 'line',
    symbol: kind === 'line' ? 'circle' : undefined,
    symbolSize: 6,
    data: Array.isArray(s.data) ? s.data : [],
    itemStyle: { color: PALETTE[i % PALETTE.length] },
    lineStyle: kind === 'line' ? { width: 2.4, color: PALETTE[i % PALETTE.length] } : undefined,
    areaStyle: kind === 'line'
      ? {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: hexA(PALETTE[i % PALETTE.length], 0.32) },
            { offset: 1, color: hexA(PALETTE[i % PALETTE.length], 0.02) },
          ]),
        }
      : undefined,
    barMaxWidth: kind === 'bar' ? 24 : undefined,
    emphasis: { focus: 'series' },
  }))
  return {
    grid: { top: 24, right: 14, bottom: 32, left: 48 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(30, 18, 90, 0.92)',
      borderWidth: 0,
      textStyle: { color: '#f8fafc', fontSize: 12 },
      extraCssText: 'border-radius:8px;box-shadow:0 8px 24px rgba(30,18,90,0.25);',
    },
    legend: series.length > 1 ? {
      top: 4,
      textStyle: { color: '#4f46e5', fontSize: 11 },
      itemWidth: 10,
      itemHeight: 8,
    } : undefined,
    xAxis: {
      type: 'category',
      data: x,
      axisLabel: { color: '#64748b', fontSize: 11 },
      axisLine: { lineStyle: { color: 'rgba(124,91,255,0.25)' } },
    },
    yAxis: {
      type: 'value',
      name: spec?.y_label || '',
      nameTextStyle: { color: '#64748b', fontSize: 11 },
      axisLabel: { color: '#64748b', fontSize: 11 },
      splitLine: { lineStyle: { color: 'rgba(124,91,255,0.12)' } },
    },
    series,
    animationDuration: 600,
    animationEasing: 'cubicOut',
  }
}

function buildPie(spec) {
  let data = []
  const series = normalizeSeries(spec)
  if (series.length && Array.isArray(series[0]?.data)) {
    const first = series[0].data
    const x = Array.isArray(spec?.x) ? spec.x : []
    if (first.length && typeof first[0] === 'object' && 'name' in first[0]) {
      data = first
    } else {
      data = first.map((v, i) => ({ name: x[i] || `类目 ${i + 1}`, value: Number(v) || 0 }))
    }
  }
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: {
      orient: 'vertical',
      right: 8,
      top: 'middle',
      textStyle: { color: '#4f46e5', fontSize: 11 },
      itemWidth: 10,
      itemHeight: 8,
    },
    series: [
      {
        name: spec?.title || '占比',
        type: 'pie',
        radius: ['42%', '68%'],
        center: ['38%', '50%'],
        avoidLabelOverlap: true,
        itemStyle: { borderColor: '#fff', borderWidth: 2 },
        label: { color: '#1f1b4d', fontSize: 11 },
        labelLine: { lineStyle: { color: '#a5b4fc' } },
        data: data.map((d, i) => ({
          ...d,
          itemStyle: { color: PALETTE[i % PALETTE.length] },
        })),
      },
    ],
    color: PALETTE,
    animationDuration: 600,
  }
}

function buildHeatmap(spec) {
  const x = Array.isArray(spec?.x) ? spec.x : []
  const ser = normalizeSeries(spec)
  const data = ser.length && Array.isArray(ser[0]?.data) ? ser[0].data : []
  const values = data.map((v) => Number(v) || 0)
  const max = values.length ? Math.max.apply(null, values) : 1
  const cells = values.map((v, i) => [i, 0, v])
  return {
    tooltip: {
      position: 'top',
      formatter: (p) => `${x[p.data[0]] || ''}<br/>${ser[0]?.name || '值'}: ${p.data[2]}`,
    },
    grid: { top: 24, right: 12, bottom: 36, left: 40 },
    xAxis: {
      type: 'category',
      data: x,
      splitArea: { show: true },
      axisLabel: { color: '#64748b', fontSize: 10 },
    },
    yAxis: {
      type: 'category',
      data: [ser[0]?.name || '值'],
      axisLabel: { color: '#64748b', fontSize: 11 },
    },
    visualMap: {
      min: 0,
      max: max || 1,
      calculable: false,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      inRange: { color: ['#e0e7ff', '#8b5cf6', '#22d3ee'] },
      textStyle: { color: '#64748b', fontSize: 10 },
    },
    series: [
      {
        name: ser[0]?.name || '值',
        type: 'heatmap',
        data: cells,
        label: { show: false },
        itemStyle: { borderColor: '#fff', borderWidth: 1 },
      },
    ],
  }
}

function hexA(hex, alpha) {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex || '')
  if (!m) return hex
  const n = parseInt(m[1], 16)
  const r = (n >> 16) & 255
  const g = (n >> 8) & 255
  const b = n & 255
  return `rgba(${r},${g},${b},${alpha})`
}

function buildOption(spec) {
  const kind = (spec?.kind || 'line').toLowerCase()
  if (kind === 'pie') return buildPie(spec)
  if (kind === 'heatmap') return buildHeatmap(spec)
  if (kind === 'bar') return buildLineOrBar('bar', spec)
  return buildLineOrBar('line', spec)
}

function render() {
  if (!el.value || !props.spec) return
  if (!inst) {
    inst = echarts.init(el.value, null, { renderer: 'canvas' })
    ro = new ResizeObserver(() => inst && inst.resize())
    ro.observe(wrap.value)
  }
  const option = buildOption(props.spec)
  inst.setOption(option, true)
}

onMounted(() => nextTick(render))
watch(() => props.spec, () => nextTick(render), { deep: true })
onBeforeUnmount(() => {
  if (ro) { try { ro.disconnect() } catch (_) { /* ignore */ } ro = null }
  if (inst) { try { inst.dispose() } catch (_) { /* ignore */ } inst = null }
})
</script>

<style scoped>
.sx-asst-chart {
  width: 100%;
  margin-top: 12px;
  padding: 8px 4px 4px;
  border-radius: 10px;
  background: linear-gradient(180deg, #ffffff 0%, #faf9ff 100%);
  border: 1px solid rgba(124, 91, 255, 0.12);
}
.sx-asst-chart__inner {
  width: 100%;
  height: 260px;
}
</style>
