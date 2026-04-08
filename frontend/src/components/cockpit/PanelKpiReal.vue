<template>
  <CockpitPanel title="关键指标（业务库）" title-en="REAL KPI">
    <div class="kpi-real-wrap">
      <p v-if="rangeHint" class="kpi-hint">{{ rangeHint }}</p>
      <div class="kpi-grid">
      <div class="kpi-section">
        <div class="kpi-section__title">所选区间</div>
        <div class="kpi-section__grid">
          <div v-for="item in rangeItems" :key="item.key" class="kpi-item">
            <div class="kpi-item__value" :style="{ color: item.color }">{{ item.display }}</div>
            <div class="kpi-item__label">{{ item.label }}</div>
          </div>
        </div>
      </div>
      <div class="kpi-section">
        <div class="kpi-section__title">今日（上海时区）</div>
        <div class="kpi-section__grid">
          <div v-for="item in todayItems" :key="item.key" class="kpi-item">
            <div class="kpi-item__value" :style="{ color: item.color }">{{ item.display }}</div>
            <div class="kpi-item__label">{{ item.label }}</div>
          </div>
        </div>
      </div>
      </div>
    </div>
  </CockpitPanel>
</template>

<script setup>
import { computed } from 'vue'
import CockpitPanel from './CockpitPanel.vue'

const props = defineProps({
  summaryRange: { type: Object, default: null },
  summaryToday: { type: Object, default: null },
})

const rangeHint = computed(() => {
  const r = props.summaryRange
  if (!r?.start_date || !r?.end_date) return ''
  return `区间 ${r.start_date} ~ ${r.end_date}`
})

function fmtMoney(n) {
  if (n == null || Number.isNaN(n)) return '--'
  return `¥${Number(n).toLocaleString()}`
}

const rangeItems = computed(() => {
  const d = props.summaryRange || {}
  const oc = d.order_count
  return [
    { key: 'roc', label: '订单量', display: oc != null ? String(oc) : '--', color: '#22d3ee' },
    { key: 'rgmv', label: 'GMV', display: d.gmv != null ? fmtMoney(d.gmv) : '--', color: '#fbbf24' },
    { key: 'rat', label: '客单价', display: d.avg_ticket != null ? `¥${d.avg_ticket}` : '--', color: '#38bdf8' },
  ]
})

const todayItems = computed(() => {
  const d = props.summaryToday || {}
  const oc = d.order_count
  return [
    { key: 'toc', label: '订单量', display: oc != null ? String(oc) : '--', color: '#22d3ee' },
    { key: 'tgmv', label: 'GMV', display: d.gmv != null ? fmtMoney(d.gmv) : '--', color: '#fbbf24' },
    { key: 'tat', label: '客单价', display: d.avg_ticket != null ? `¥${d.avg_ticket}` : '--', color: '#38bdf8' },
  ]
})
</script>

<style scoped>
/* 占满面板高度且不裁切底行：可滚动 + 顶对齐（格内原先垂直居中导致上下被 overflow:hidden 切掉） */
.kpi-real-wrap {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow-x: hidden;
  overflow-y: auto;
  padding-bottom: 10px;
  margin: -2px 0 0;
}

.kpi-hint {
  flex-shrink: 0;
  margin: 0 0 6px;
  font-size: 10px;
  color: var(--sx-text-muted);
  letter-spacing: 0.04em;
}

.kpi-grid {
  display: flex;
  flex-direction: column;
  gap: 10px;
  flex: 1;
  min-height: min-content;
  justify-content: flex-start;
}

.kpi-section__title {
  font-size: 9px;
  letter-spacing: 0.16em;
  color: rgba(125, 211, 252, 0.55);
  text-transform: uppercase;
  margin-bottom: 4px;
}

.kpi-section__grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px 10px;
}

.kpi-item { text-align: center; min-width: 0; }

.kpi-item__value {
  font-size: clamp(14px, 1.65vw, 20px);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  text-shadow: 0 0 10px currentColor;
  line-height: 1.12;
  word-break: break-all;
}

.kpi-item__label {
  font-size: 10px;
  color: rgba(203, 213, 225, 0.92);
  margin-top: 2px;
  line-height: 1.25;
}
</style>
