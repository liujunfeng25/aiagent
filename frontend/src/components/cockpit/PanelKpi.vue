<template>
  <CockpitPanel title="关键指标" title-en="KEY METRICS">
    <div class="kpi-grid">
      <div v-for="item in items" :key="item.key" class="kpi-item">
        <div class="kpi-item__value" :style="{ color: item.color }">{{ item.display }}</div>
        <div class="kpi-item__label">{{ item.label }}</div>
      </div>
    </div>
  </CockpitPanel>
</template>

<script setup>
import { computed } from 'vue'
import CockpitPanel from './CockpitPanel.vue'

const props = defineProps({
  data: { type: Object, default: () => ({}) },
})

function fmtCurrency(v) {
  if (v == null || v === '' || Number.isNaN(Number(v))) return '--'
  return `¥${Number(v).toLocaleString()}`
}

function fmtPct(v) {
  if (v == null || v === '' || Number.isNaN(Number(v))) return '--'
  return `${Number(v).toFixed(2)}%`
}

const items = computed(() => {
  const d = props.data
  return [
    { key: 'todayOrders', label: '今日订单', display: d.todayOrders ?? '--', color: '#22d3ee' },
    { key: 'todayGmv', label: '今日 GMV', display: fmtCurrency(d.todayGmv), color: '#fbbf24' },
    { key: 'avgOrderAmount', label: '平均客单价', display: d.avgOrderAmount != null && d.avgOrderAmount !== '' ? `¥${d.avgOrderAmount}` : '--', color: '#38bdf8' },
    {
      key: 'distinctBuyers',
      label: '今日下单会员',
      display: d.distinctBuyers ?? '--',
      color: '#22c55e',
    },
    {
      key: 'returnRateByAmount',
      label: '退货金额占GMV',
      display: fmtPct(d.returnRateByAmount),
      color: '#ef4444',
    },
    {
      key: 'reportUploadRate',
      label: '报告上传率',
      display: '98%',
      color: '#a78bfa',
    },
  ]
})
</script>

<style scoped>
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: clamp(6px, 1.2vw, 10px) clamp(10px, 1.5vw, 14px);
  align-content: start;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding-bottom: 6px;
  -webkit-overflow-scrolling: touch;
}

.kpi-item {
  text-align: center;
}

.kpi-item__value {
  font-size: clamp(18px, 2.2vw, 26px);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  text-shadow: 0 0 12px currentColor;
  line-height: 1.15;
}

.kpi-item__label {
  font-size: 11px;
  color: var(--sx-text-muted);
  margin-top: 3px;
}
</style>
