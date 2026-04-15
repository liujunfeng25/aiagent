<template>
  <div class="smart-side-stack" :class="{ 'smart-side-stack--embed': embedded }">
    <CockpitPanel
      class="smart-side-stack__panel"
      title="重点区域"
      title-en="TOP DISTRICTS · RANGE"
      :hint="hint"
    >
      <div class="kf-body">
        <div v-if="!keyRows.length" class="kf-empty">暂无区县聚合数据</div>
        <div
          v-for="(row, i) in keyRows"
          v-else
          :key="row.district_name + i"
          class="kf-row"
          :class="{ 'kf-row--top': i === 0 }"
        >
          <span class="kf-name">{{ row.district_name }}</span>
          <span class="kf-gmv" :class="{ 'kf-gmv--top': i === 0 }">{{ formatWan(row.gmv) }}</span>
          <span
            v-if="row.mom_pct != null && Number.isFinite(Number(row.mom_pct))"
            class="kf-mom"
            :class="momClass(row.mom_pct)"
          >
            {{ formatMom(row.mom_pct) }}
          </span>
          <span v-else class="kf-mom kf-mom--na">—</span>
        </div>
        <p v-if="footerLine" class="kf-foot">
          共覆盖 <strong>{{ districtCover }}</strong> 个区县，活跃落点 <strong>{{ activePoints }}</strong> 个
        </p>
      </div>
    </CockpitPanel>

    <CockpitPanel
      class="smart-side-stack__panel smart-side-stack__panel--ticket"
      title="客单价分布"
      title-en="AOV BUCKETS"
    >
      <div class="ticket-wrap">
        <div ref="ticketRef" class="ticket-chart" />
      </div>
    </CockpitPanel>
  </div>
</template>

<script setup>
import { ref, watch, computed, onMounted, onUnmounted, shallowRef } from 'vue'
import * as echarts from 'echarts'
import CockpitPanel from './CockpitPanel.vue'
import { sxAnimation } from '../../utils/echartTheme.js'

const BUCKET_COLORS = ['#14532d', '#22c55e', '#38bdf8', '#eab308']

const props = defineProps({
  /** cockpit-smart-side-insights 响应体 */
  payload: { type: Object, default: null },
  hint: { type: String, default: '' },
  /** 嵌入订单分布地图右侧窄栏：紧凑排版 */
  embedded: { type: Boolean, default: false },
})

const ticketRef = ref(null)
const ticketChart = shallowRef(null)

const keyRows = computed(() => {
  const rows = props.payload?.key_districts
  return Array.isArray(rows) ? rows : []
})

const districtCover = computed(() => Number(props.payload?.district_cover_count) || 0)
const activePoints = computed(() => Number(props.payload?.active_points) || 0)
const footerLine = computed(() => districtCover.value > 0 || activePoints.value > 0)

function formatWan(gmv) {
  const n = Number(gmv) || 0
  if (n <= 0) return '¥0万'
  return `¥${(n / 10000).toFixed(1)}万`
}

function formatMom(p) {
  const x = Number(p)
  if (!Number.isFinite(x)) return '—'
  const sign = x > 0 ? '+' : ''
  return `${sign}${x}%`
}

function momClass(p) {
  const x = Number(p)
  if (!Number.isFinite(x) || x === 0) return 'kf-mom--flat'
  return x > 0 ? 'kf-mom--up' : 'kf-mom--down'
}

function buildTicketOption() {
  const em = props.embedded
  const buckets = props.payload?.ticket_buckets
  if (!Array.isArray(buckets) || !buckets.length) {
    return {
      ...sxAnimation,
      graphic: {
        type: 'text',
        left: 'center',
        top: 'middle',
        style: { text: '暂无订单', fill: 'rgba(148,163,184,0.75)', fontSize: em ? 10 : 12 },
      },
    }
  }
  const labels = buckets.map((b) => b.label || '')
  const counts = buckets.map((b) => Number(b.count) || 0)
  const maxC = Math.max(1, ...counts)
  const ax = em ? 9 : 10
  return {
    ...sxAnimation,
    grid: em
      ? { left: 2, right: 2, top: 4, bottom: 20 }
      : { left: 8, right: 8, top: 10, bottom: 28 },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: 'rgba(2, 6, 23, 0.94)',
      borderColor: 'rgba(34, 211, 238, 0.35)',
      textStyle: { color: '#e2e8f0', fontSize: em ? 11 : 12 },
      formatter(params) {
        const p = params[0]
        return `${p.name}<br/>订单数：${p.value}`
      },
    },
    xAxis: {
      type: 'category',
      data: labels,
      axisLine: { lineStyle: { color: 'rgba(148,163,184,0.25)' } },
      axisLabel: { color: 'rgba(203,213,225,0.85)', fontSize: ax },
    },
    yAxis: {
      type: 'value',
      max: maxC,
      splitLine: { lineStyle: { color: 'rgba(250,204,21,0.06)' } },
      axisLabel: { color: 'rgba(148,163,184,0.65)', fontSize: ax },
    },
    series: [{
      type: 'bar',
      data: counts.map((c, i) => ({
        value: c,
        itemStyle: {
          color: BUCKET_COLORS[i % BUCKET_COLORS.length],
          borderRadius: [4, 4, 0, 0],
        },
      })),
      barWidth: '48%',
    }],
  }
}

function initTicket() {
  if (!ticketRef.value) return
  if (!ticketChart.value) ticketChart.value = echarts.init(ticketRef.value)
  ticketChart.value.setOption(buildTicketOption(), true)
}

let tro = null
onMounted(() => {
  initTicket()
  if (typeof ResizeObserver !== 'undefined' && ticketRef.value) {
    tro = new ResizeObserver(() => ticketChart.value?.resize())
    tro.observe(ticketRef.value)
  }
})

onUnmounted(() => {
  tro?.disconnect()
  ticketChart.value?.dispose()
  ticketChart.value = null
})

watch(() => [props.payload, props.embedded], () => {
  if (ticketChart.value) ticketChart.value.setOption(buildTicketOption(), true)
  else initTicket()
}, { deep: true })
</script>

<style scoped>
.smart-side-stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
  height: 100%;
  min-height: 0;
}

.smart-side-stack__panel {
  flex: 1 1 0;
  min-height: 0;
}

.smart-side-stack__panel--ticket {
  flex: 1.05 1 0;
}

.kf-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 4px 2px 2px;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.kf-empty {
  font-size: 12px;
  color: rgba(148, 163, 184, 0.8);
  padding: 12px 4px;
}

.kf-row {
  display: grid;
  grid-template-columns: 1fr auto auto;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 6px;
  background: rgba(8, 15, 35, 0.45);
  border: 1px solid rgba(34, 211, 238, 0.08);
}

.kf-row--top {
  border-color: rgba(234, 179, 8, 0.22);
  background: linear-gradient(90deg, rgba(234, 179, 8, 0.08), transparent 70%);
}

.kf-name {
  font-size: 12px;
  font-weight: 600;
  color: rgba(226, 232, 240, 0.95);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kf-gmv {
  font-size: 12px;
  font-weight: 700;
  color: rgba(241, 245, 249, 0.95);
  font-variant-numeric: tabular-nums;
}

.kf-gmv--top {
  color: #fbbf24;
  text-shadow: 0 0 12px rgba(251, 191, 36, 0.25);
}

.kf-mom {
  min-width: 52px;
  text-align: center;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 999px;
  font-variant-numeric: tabular-nums;
}

.kf-mom--up {
  color: #ecfdf5;
  background: rgba(22, 163, 74, 0.35);
  border: 1px solid rgba(34, 197, 94, 0.35);
}

.kf-mom--down {
  color: #fef2f2;
  background: rgba(185, 28, 28, 0.35);
  border: 1px solid rgba(248, 113, 113, 0.35);
}

.kf-mom--flat {
  color: rgba(203, 213, 225, 0.85);
  background: rgba(30, 41, 59, 0.5);
  border: 1px solid rgba(148, 163, 184, 0.2);
}

.kf-mom--na {
  color: rgba(148, 163, 184, 0.6);
  background: transparent;
  border: 1px solid rgba(148, 163, 184, 0.15);
}

.kf-foot {
  margin: 8px 4px 0;
  font-size: 11px;
  line-height: 1.45;
  color: rgba(148, 163, 184, 0.88);
}

.kf-foot strong {
  color: #38bdf8;
  font-weight: 700;
}

.ticket-wrap {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

.ticket-chart {
  width: 100%;
  flex: 1;
  min-height: 120px;
}

/* 嵌入地图侧栏 */
.smart-side-stack--embed {
  gap: 6px;
  flex: 1;
  min-height: 0;
  overflow: visible;
}

.smart-side-stack--embed .smart-side-stack__panel {
  flex: 1 1 auto;
  min-height: 0;
}

.smart-side-stack--embed .smart-side-stack__panel--ticket {
  flex: 1 1 42%;
  min-height: 100px;
}

.smart-side-stack--embed :deep(.cp__head) {
  padding: 5px 8px;
}

.smart-side-stack--embed :deep(.cp__title) {
  font-size: 11px;
}

.smart-side-stack--embed :deep(.cp__title-en) {
  display: none;
}

.smart-side-stack--embed :deep(.cp__body) {
  padding: 5px 6px;
}

.smart-side-stack--embed :deep(.cp__hint) {
  font-size: 9px;
  line-height: 1.3;
}

.smart-side-stack--embed .kf-body {
  gap: 4px;
  padding: 2px 0;
}

.smart-side-stack--embed .kf-row {
  padding: 4px 6px;
  gap: 4px;
  grid-template-columns: 1fr auto auto;
}

.smart-side-stack--embed .kf-name {
  font-size: 11px;
}

.smart-side-stack--embed .kf-gmv {
  font-size: 11px;
}

.smart-side-stack--embed .kf-mom {
  min-width: 44px;
  padding: 1px 5px;
  font-size: 10px;
}

.smart-side-stack--embed .kf-foot {
  font-size: 10px;
  margin-top: 4px;
}

.smart-side-stack--embed .ticket-chart {
  min-height: 72px;
}
</style>
