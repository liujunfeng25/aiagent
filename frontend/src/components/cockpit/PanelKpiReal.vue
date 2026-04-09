<template>
  <CockpitPanel title="今日实时指标" title-en="TODAY KPI">
    <div class="kpi-real-wrap">
      <div class="kpi-today-grid">
        <div v-for="item in todayItems" :key="item.key" class="kpi-today-item">
          <div class="kpi-today-item__value" :style="{ color: item.color }">{{ item.display }}</div>
          <div class="kpi-today-item__label">{{ item.label }}</div>
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
  liveTodayPatch: { type: Object, default: null },
})

function fmtMoney(n) {
  if (n == null || Number.isNaN(n)) return '--'
  return `¥${Number(n).toLocaleString()}`
}

const todayItems = computed(() => {
  const raw = props.summaryToday || {}
  const L = props.liveTodayPatch
  const d = L && typeof L === 'object'
    ? {
        order_count: L.order_count != null ? L.order_count : raw.order_count,
        gmv: L.gmv != null ? L.gmv : raw.gmv,
        avg_ticket: L.avg_ticket != null ? L.avg_ticket : raw.avg_ticket,
      }
    : raw
  const oc = d.order_count
  return [
    { key: 'toc', label: '今日订单量', display: oc != null ? String(oc) : '--', color: '#22d3ee' },
    { key: 'tgmv', label: '今日 GMV', display: d.gmv != null ? fmtMoney(d.gmv) : '--', color: '#fbbf24' },
    { key: 'tat', label: '客单价', display: d.avg_ticket != null ? `¥${d.avg_ticket}` : '--', color: '#38bdf8' },
  ]
})
</script>

<style scoped>
.kpi-real-wrap {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 10px 8px;
}

.kpi-today-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px 24px;
  width: 100%;
  max-width: 560px;
}

.kpi-today-item {
  text-align: center;
  min-width: 0;
}

.kpi-today-item__value {
  font-size: clamp(20px, 2.8vw, 32px);
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  text-shadow: 0 0 14px currentColor;
  line-height: 1.15;
  word-break: break-all;
}

.kpi-today-item__label {
  font-size: 11px;
  color: rgba(203, 213, 225, 0.92);
  margin-top: 4px;
  line-height: 1.25;
  letter-spacing: 0.08em;
}
</style>
