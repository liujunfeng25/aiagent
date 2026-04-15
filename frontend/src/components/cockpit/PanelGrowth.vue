<template>
  <CockpitPanel
    title="增长指标"
    title-en="GROWTH INDEX"
    hint="今日相对昨日（日环比）；与顶栏统计区间口径不同"
  >
    <div class="growth-grid">
      <div v-for="item in items" :key="item.key" class="growth-item">
        <div class="growth-item__value" :class="item.trendClass">
          <span v-if="item.arrow" class="growth-item__arrow">{{ item.arrow }}</span>
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
  /** 来自 DataCockpit：今日 vs 昨日 kpi-summary 计算的环比与退货率百分点差 */
  metrics: {
    type: Object,
    default: () => ({
      orderMomPct: null,
      gmvMomPct: null,
      buyerMomPct: null,
      returnDeltaPp: null,
    }),
  },
})

function fmtMom(v) {
  if (v == null || Number.isNaN(v)) return '--'
  if (v === 0) return '0.0%'
  return `${v > 0 ? '+' : ''}${v.toFixed(1)}%`
}

function momTrendClass(v) {
  if (v == null || Number.isNaN(v)) return 'flat'
  if (v > 0) return 'up'
  if (v < 0) return 'down'
  return 'flat'
}

function momArrow(v) {
  if (v == null || Number.isNaN(v) || v === 0) return ''
  return v > 0 ? '▲' : '▼'
}

/** 昨日% − 今日%，正数表示退货率下降（利好） */
function fmtReturnDelta(pp) {
  if (pp == null || Number.isNaN(pp)) return '--'
  if (pp === 0) return '0.00%'
  return `${pp > 0 ? '+' : ''}${pp.toFixed(2)}%`
}

function returnTrendClass(pp) {
  if (pp == null || Number.isNaN(pp)) return 'flat'
  if (pp > 0) return 'good'
  if (pp < 0) return 'bad'
  return 'flat'
}

function returnArrow(pp) {
  if (pp == null || Number.isNaN(pp) || pp === 0) return ''
  return pp > 0 ? '▼' : '▲'
}

const items = computed(() => {
  const m = props.metrics || {}
  return [
    {
      key: 'orderMom',
      label: '订单日环比',
      display: fmtMom(m.orderMomPct),
      trendClass: momTrendClass(m.orderMomPct),
      arrow: momArrow(m.orderMomPct),
    },
    {
      key: 'gmvMom',
      label: 'GMV 日环比',
      display: fmtMom(m.gmvMomPct),
      trendClass: momTrendClass(m.gmvMomPct),
      arrow: momArrow(m.gmvMomPct),
    },
    {
      key: 'buyerMom',
      label: '下单会员日环比',
      display: fmtMom(m.buyerMomPct),
      trendClass: momTrendClass(m.buyerMomPct),
      arrow: momArrow(m.buyerMomPct),
    },
    {
      key: 'returnDelta',
      label: '退货率较昨日',
      display: fmtReturnDelta(m.returnDeltaPp),
      trendClass: returnTrendClass(m.returnDeltaPp),
      arrow: returnArrow(m.returnDeltaPp),
    },
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

/* 退货率下降（百分点为正） */
.growth-item__value.good {
  color: var(--sx-success);
  text-shadow: 0 0 10px rgba(52, 211, 153, 0.4);
}

/* 退货率上升 */
.growth-item__value.bad {
  color: var(--sx-danger);
  text-shadow: 0 0 10px rgba(248, 113, 113, 0.4);
}

.growth-item__value.flat {
  color: var(--sx-text-muted);
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
