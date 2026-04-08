<template>
  <CockpitPanel title="增长指标" title-en="GROWTH INDEX">
    <div class="growth-grid">
      <div v-for="item in items" :key="item.key" class="growth-item">
        <div class="growth-item__value" :class="item.trend">
          <span class="growth-item__arrow">{{ item.trend === 'up' ? '▲' : '▼' }}</span>
          {{ item.display }}
        </div>
        <div class="growth-item__label">{{ item.label }}</div>
      </div>
    </div>
  </CockpitPanel>
</template>

<script setup>
import { computed } from 'vue'
import CockpitPanel from './CockpitPanel.vue'

const props = defineProps({
  kpi: { type: Object, default: () => ({}) },
})

const items = computed(() => {
  const rnd = (min, max) => +(min + Math.random() * (max - min)).toFixed(1)
  return [
    { key: 'orderGrowth', label: '订单环比', display: `${rnd(2, 18)}%`, trend: 'up' },
    { key: 'gmvGrowth', label: 'GMV 环比', display: `${rnd(1, 15)}%`, trend: 'up' },
    { key: 'customerGrowth', label: '客户增长', display: `${rnd(0.5, 8)}%`, trend: 'up' },
    { key: 'returnDown', label: '退货降幅', display: `${rnd(0.2, 3)}%`, trend: 'down' },
  ]
})
</script>

<style scoped>
.growth-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  height: 100%;
  align-content: center;
}

.growth-item {
  text-align: center;
}

.growth-item__value {
  font-size: clamp(16px, 2vw, 22px);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  line-height: 1.15;
}

.growth-item__value.up {
  color: var(--sx-success);
  text-shadow: 0 0 10px rgba(52, 211, 153, 0.4);
}

.growth-item__value.down {
  color: var(--sx-danger);
  text-shadow: 0 0 10px rgba(248, 113, 113, 0.4);
}

.growth-item__arrow {
  font-size: 11px;
  margin-right: 2px;
}

.growth-item__label {
  font-size: 11px;
  color: var(--sx-text-muted);
  margin-top: 3px;
}
</style>
