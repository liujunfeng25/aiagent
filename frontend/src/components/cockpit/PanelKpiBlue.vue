<template>
  <CockpitPanelBlue title="关键指标" title-en="KEY METRICS">
    <div class="kpi-grid-blue">
      <div v-for="item in items" :key="item.key" class="kpi-item-blue">
        <div class="kpi-item-blue__value" :style="{ color: item.color }">{{ item.display }}</div>
        <div class="kpi-item-blue__label">{{ item.label }}</div>
      </div>
    </div>
  </CockpitPanelBlue>
</template>

<script setup>
import { computed } from 'vue'
import CockpitPanelBlue from './CockpitPanelBlue.vue'

const props = defineProps({
  data: { type: Object, default: () => ({}) },
})

const items = computed(() => {
  const d = props.data
  return [
    { key: 'todayOrders', label: '今日订单', display: d.todayOrders ?? '--', color: '#1e90ff' },
    { key: 'todayGmv', label: '今日 GMV', display: d.todayGmv ? `¥${Number(d.todayGmv).toLocaleString()}` : '--', color: '#00c8ff' },
    { key: 'avgOrderAmount', label: '平均客单价', display: d.avgOrderAmount ? `¥${d.avgOrderAmount}` : '--', color: '#4da6ff' },
    { key: 'deliveryRate', label: '配送及时率', display: d.deliveryRate ? `${d.deliveryRate}%` : '--', color: '#22c55e' },
    { key: 'returnRate', label: '退货率', display: d.returnRate ? `${d.returnRate}%` : '--', color: '#ef4444' },
    { key: 'newCustomers', label: '新增客户', display: d.newCustomers ?? '--', color: '#7cb3ff' },
  ]
})
</script>

<style scoped>
.kpi-grid-blue {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px 14px;
  height: 100%;
  align-content: center;
}

.kpi-item-blue { text-align: center; }

.kpi-item-blue__value {
  font-size: clamp(18px, 2.2vw, 26px);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  text-shadow: 0 0 12px currentColor;
  line-height: 1.15;
}

.kpi-item-blue__label {
  font-size: 11px;
  color: rgba(140, 170, 220, 0.8);
  margin-top: 3px;
}
</style>
