<template>
  <div class="blue-shell">
    <div class="blue-shell__bg" aria-hidden="true" />
    <div class="blue-shell__scan" aria-hidden="true" />

    <header class="blue-top">
      <div class="blue-top__side blue-top__side--left">
        <span class="blue-top__tag">{{ clockText }}</span>
      </div>
      <div class="blue-top__center">
        <div class="blue-top__title-line" />
        <h1 class="blue-top__title">经济数据可视化驾驶舱大屏</h1>
        <div class="blue-top__title-line blue-top__title-line--short" />
      </div>
      <div class="blue-top__side blue-top__side--right">
        <span class="blue-top__tag-right">VISUALIZATION</span>
      </div>
    </header>

    <!-- KPI Summary Bar -->
    <div class="blue-kpi-bar">
      <div v-for="item in kpiBarItems" :key="item.key" class="blue-kpi-bar__item">
        <span class="blue-kpi-bar__label">{{ item.label }}</span>
        <span class="blue-kpi-bar__value">{{ item.value }}</span>
      </div>
    </div>

    <div v-if="loadError" class="blue-shell__err">{{ loadError }}</div>

    <!-- 3x3 Grid -->
    <div class="blue-grid">
      <div class="blue-grid__cell blue-grid__cell--r1c1">
        <PanelDonutBlue :data="goodsData" :kpi="kpiData" />
      </div>
      <div class="blue-grid__cell blue-grid__cell--map">
        <CockpitPanelBlue title="北京市区域分布" title-en="BEIJING REGION MAP">
          <BeijingMap3D :vehicles="vehicles" :drill-adcode="drillAdcode" theme="blue" @drill="$emit('drill', $event)" />
        </CockpitPanelBlue>
      </div>
      <div class="blue-grid__cell blue-grid__cell--r1c3">
        <PanelRingGauge :data="kpiData" />
      </div>

      <div class="blue-grid__cell blue-grid__cell--r2c1">
        <PanelRegionBlue :data="regionData" />
      </div>
      <div class="blue-grid__cell blue-grid__cell--r2c3">
        <PanelTrendLineBlue :data="orderTrendData" />
      </div>

      <div class="blue-grid__cell blue-grid__cell--r3c1">
        <PanelOrderTrendBlue :data="orderTrendData" />
      </div>
      <div class="blue-grid__cell blue-grid__cell--r3c2">
        <PanelKpiBlue :data="kpiData" />
      </div>
      <div class="blue-grid__cell blue-grid__cell--r3c3">
        <PanelLineBlue :data="orderTrendData" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import CockpitPanelBlue from './CockpitPanelBlue.vue'
import BeijingMap3D from './BeijingMap3D.vue'
import PanelDonutBlue from './PanelDonutBlue.vue'
import PanelRingGauge from './PanelRingGauge.vue'
import PanelRegionBlue from './PanelRegionBlue.vue'
import PanelOrderTrendBlue from './PanelOrderTrendBlue.vue'
import PanelTrendLineBlue from './PanelTrendLineBlue.vue'
import PanelLineBlue from './PanelLineBlue.vue'
import PanelKpiBlue from './PanelKpiBlue.vue'

const props = defineProps({
  vehicles: { type: Array, default: () => [] },
  orderTrendData: { type: Array, default: () => [] },
  orderRankData: { type: Array, default: () => [] },
  goodsData: { type: Array, default: () => [] },
  regionData: { type: Array, default: () => [] },
  kpiData: { type: Object, default: () => ({}) },
  clockText: { type: String, default: '' },
  drillAdcode: { type: String, default: '' },
  loadError: { type: String, default: '' },
})

defineEmits(['drill'])

const kpiBarItems = computed(() => {
  const d = props.kpiData
  return [
    { key: 'orders', label: '今日订单总量', value: d.todayOrders ?? '--' },
    { key: 'gmv', label: '今日 GMV', value: d.todayGmv ? `¥${Number(d.todayGmv).toLocaleString()}` : '--' },
    { key: 'customers', label: '注册客户数', value: d.newCustomers ? `${d.newCustomers}+` : '--' },
  ]
})
</script>

<style scoped>
.blue-shell {
  position: relative;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  height: 100%;
  padding: 10px 12px 12px;
  color: #e8eef8;
  overflow: hidden;
}

.blue-shell__bg {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  background:
    radial-gradient(ellipse 100% 80% at 50% -30%, rgba(30, 144, 255, 0.12), transparent 45%),
    radial-gradient(ellipse 70% 50% at 100% 50%, rgba(0, 200, 255, 0.04), transparent 50%),
    radial-gradient(ellipse 70% 50% at 0% 50%, rgba(30, 144, 255, 0.06), transparent 50%),
    linear-gradient(180deg, #050d2e 0%, #081838 38%, #050d2e 100%);
}

.blue-shell__bg::after {
  content: '';
  position: absolute;
  inset: 0;
  opacity: 0.18;
  background-image:
    linear-gradient(rgba(30, 144, 255, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(30, 144, 255, 0.04) 1px, transparent 1px);
  background-size: 48px 48px;
}

.blue-shell__scan {
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  background: linear-gradient(180deg, transparent 0%, rgba(30, 144, 255, 0.03) 48%, rgba(0, 200, 255, 0.02) 49%, transparent 52%);
  background-size: 100% 240%;
  animation: blue-scan 10s linear infinite;
  opacity: 0.5;
}

@keyframes blue-scan {
  0% { background-position: 0% 0%; }
  100% { background-position: 0% 100%; }
}

/* Header */
.blue-top {
  position: relative;
  z-index: 2;
  display: grid;
  grid-template-columns: 1fr minmax(200px, 480px) 1fr;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
  padding: 2px 0 4px;
}

.blue-top__side { display: flex; align-items: center; min-height: 32px; }
.blue-top__side--left { justify-content: flex-start; }
.blue-top__side--right { justify-content: flex-end; }

.blue-top__tag, .blue-top__tag-right {
  font-family: ui-monospace, 'SF Mono', Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  color: rgba(140, 170, 220, 0.7);
  letter-spacing: 0.06em;
}

.blue-top__center { text-align: center; }

.blue-top__title-line {
  height: 2px;
  width: min(80%, 280px);
  margin: 0 auto 6px;
  background: linear-gradient(90deg, transparent, rgba(30, 144, 255, 0.7), rgba(0, 200, 255, 0.8), rgba(30, 144, 255, 0.7), transparent);
  box-shadow: 0 0 12px rgba(30, 144, 255, 0.5);
  border-radius: 2px;
}

.blue-top__title-line--short {
  width: min(40%, 140px);
  margin: 6px auto 0;
  opacity: 0.6;
}

.blue-top__title {
  font-size: clamp(18px, 2.4vw, 26px);
  font-weight: 700;
  letter-spacing: 0.22em;
  color: #f0f4ff;
  text-shadow: 0 0 20px rgba(30, 144, 255, 0.5), 0 0 40px rgba(30, 144, 255, 0.2);
  margin: 0;
  line-height: 1.2;
}

/* KPI Bar */
.blue-kpi-bar {
  position: relative;
  z-index: 2;
  display: flex;
  justify-content: center;
  gap: 40px;
  padding: 6px 0 8px;
  flex-shrink: 0;
}

.blue-kpi-bar__item {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.blue-kpi-bar__label {
  font-size: 12px;
  color: rgba(140, 170, 220, 0.7);
}

.blue-kpi-bar__value {
  font-size: 20px;
  font-weight: 700;
  color: #e8eef8;
  font-variant-numeric: tabular-nums;
  text-shadow: 0 0 10px rgba(30, 144, 255, 0.5);
}

.blue-shell__err {
  position: relative;
  z-index: 2;
  padding: 8px 12px;
  margin-bottom: 6px;
  border-radius: 6px;
  background: rgba(80, 20, 20, 0.4);
  border: 1px solid rgba(248, 113, 113, 0.4);
  color: #fecaca;
  font-size: 13px;
}

/* Grid */
.blue-grid {
  position: relative;
  z-index: 2;
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 1fr 1.4fr 1fr;
  grid-template-rows: 1fr 1fr 0.85fr;
  gap: 8px;
}

.blue-grid__cell {
  min-height: 0;
  min-width: 0;
  overflow: hidden;
  display: flex;
}

.blue-grid__cell > * { flex: 1; min-height: 0; }

.blue-grid__cell--r1c1 { grid-column: 1; grid-row: 1; }
.blue-grid__cell--map  { grid-column: 2; grid-row: 1 / 3; overflow: visible; }
.blue-grid__cell--r1c3 { grid-column: 3; grid-row: 1; }
.blue-grid__cell--r2c1 { grid-column: 1; grid-row: 2; }
.blue-grid__cell--r2c3 { grid-column: 3; grid-row: 2; }
.blue-grid__cell--r3c1 { grid-column: 1; grid-row: 3; }
.blue-grid__cell--r3c2 { grid-column: 2; grid-row: 3; }
.blue-grid__cell--r3c3 { grid-column: 3; grid-row: 3; }

@media (max-width: 900px) {
  .blue-grid {
    grid-template-columns: 1fr;
    grid-template-rows: auto;
  }
  .blue-grid__cell--map { grid-column: 1; grid-row: auto; min-height: 360px; }
  .blue-grid__cell--r1c1,
  .blue-grid__cell--r1c3,
  .blue-grid__cell--r2c1,
  .blue-grid__cell--r2c3,
  .blue-grid__cell--r3c1,
  .blue-grid__cell--r3c2,
  .blue-grid__cell--r3c3 {
    grid-column: 1;
    grid-row: auto;
    min-height: 200px;
  }
  .blue-top { grid-template-columns: 1fr; text-align: center; }
  .blue-kpi-bar { flex-wrap: wrap; gap: 16px; }
}
</style>
