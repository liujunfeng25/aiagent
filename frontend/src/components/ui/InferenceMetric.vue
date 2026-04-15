<template>
  <div class="im">
    <span class="im__label">{{ label }}</span>
    <strong class="im__value">{{ value }}</strong>
    <span
      v-if="showTrend && hasTrend"
      :class="['im__trend', trendClass]"
      :title="trendHint || undefined"
    >{{ trendArrow }} {{ trendAbs }}%</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  label: { type: String, default: '' },
  value: { type: [String, Number], default: '--' },
  /** 后端计算的环比（%）；为 null/undefined 时不展示，避免假数据 */
  trend: { type: Number, default: null },
  /** 鼠标悬停说明口径 */
  trendHint: { type: String, default: '' },
  /** 是否展示环比百分比（仅影响展示，不影响主数值） */
  showTrend: { type: Boolean, default: true },
})

const hasTrend = computed(() => {
  const n = Number(props.trend)
  return props.trend !== null && props.trend !== undefined && !Number.isNaN(n)
})

const trendClass = computed(() => {
  const n = Number(props.trend)
  if (!Number.isFinite(n) || n === 0) return 'flat'
  return n > 0 ? 'up' : 'down'
})

const trendArrow = computed(() => {
  const n = Number(props.trend)
  if (!Number.isFinite(n) || n === 0) return '—'
  return n > 0 ? '▲' : '▼'
})

const trendAbs = computed(() => {
  const n = Number(props.trend)
  if (!Number.isFinite(n)) return '0'
  return Math.abs(Math.round(n * 10) / 10)
})
</script>

<style scoped>
.im {
  border: 1px solid var(--sx-glass-border);
  border-radius: 10px;
  padding: 10px 12px;
  background: var(--sx-metric-bg);
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.im__label { font-size: 12px; color: var(--sx-text-muted); }
.im__value { color: var(--sx-text-title); font-size: 22px; line-height: 1.2; }
.im__trend { font-size: 12px; cursor: help; }
.im__trend.up { color: var(--sx-success); }
.im__trend.down { color: var(--sx-danger); }
.im__trend.flat { color: rgba(148, 163, 184, 0.95); }
</style>
