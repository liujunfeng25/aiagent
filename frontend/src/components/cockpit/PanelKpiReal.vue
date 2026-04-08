<template>
  <CockpitPanel title="关键指标（业务库）" title-en="REAL KPI">
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
    { key: 'rgmv', label: 'GMV', display: d.gmv != null ? fmtMoney(d.gmv) : '--', color: '#f0c040' },
    { key: 'rat', label: '客单价', display: d.avg_ticket != null ? `¥${d.avg_ticket}` : '--', color: '#38bdf8' },
  ]
})

const todayItems = computed(() => {
  const d = props.summaryToday || {}
  const oc = d.order_count
  return [
    { key: 'toc', label: '订单量', display: oc != null ? String(oc) : '--', color: '#22d3ee' },
    { key: 'tgmv', label: 'GMV', display: d.gmv != null ? fmtMoney(d.gmv) : '--', color: '#f0c040' },
    { key: 'tat', label: '客单价', display: d.avg_ticket != null ? `¥${d.avg_ticket}` : '--', color: '#38bdf8' },
  ]
})
</script>

<style scoped>
.kpi-hint {
  margin: 0 0 8px;
  font-size: 11px;
  color: rgba(148, 163, 184, 0.85);
  letter-spacing: 0.04em;
}

.kpi-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  justify-content: center;
}

.kpi-section__title {
  font-size: 10px;
  letter-spacing: 0.2em;
  color: rgba(125, 211, 252, 0.55);
  text-transform: uppercase;
  margin-bottom: 6px;
}

.kpi-section__grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px 12px;
}

.kpi-item { text-align: center; }

.kpi-item__value {
  font-size: clamp(15px, 1.8vw, 22px);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  text-shadow: 0 0 10px currentColor;
  line-height: 1.15;
}

.kpi-item__label {
  font-size: 10px;
  color: rgba(148, 163, 184, 0.8);
  margin-top: 2px;
}
</style>
