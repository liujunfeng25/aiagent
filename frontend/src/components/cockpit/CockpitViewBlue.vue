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
        <h1 class="blue-top__title">批发价格 · 供需风险</h1>
        <p v-if="rangeHint" class="blue-top__sub">{{ rangeHint }}</p>
        <div class="blue-top__title-line blue-top__title-line--short" />
      </div>
      <div class="blue-top__side blue-top__side--right">
        <span class="blue-top__tag-right">AI PRICE RADAR</span>
      </div>
    </header>

    <div class="blue-kpi-bar">
      <div class="blue-kpi-bar__item">
        <span class="blue-kpi-bar__label">区间背单笔数</span>
        <span class="blue-kpi-bar__value">{{ riskKpis.backCnt }}</span>
      </div>
      <div class="blue-kpi-bar__item">
        <span class="blue-kpi-bar__label">区间背单金额</span>
        <span class="blue-kpi-bar__value">{{ riskKpis.backAmtFmt }}</span>
      </div>
      <div class="blue-kpi-bar__item">
        <span class="blue-kpi-bar__label">最新日均批发价</span>
        <span class="blue-kpi-bar__value">{{ riskKpis.lastAvg }}</span>
      </div>
    </div>

    <div v-if="loadError" class="blue-shell__err">
      {{ loadError }}
      <el-button type="primary" size="small" class="blue-retry" @click="emit('retry')">重试</el-button>
    </div>

    <div class="blue-grid">
      <div class="blue-grid__cell blue-grid__cell--r1">
        <PanelXinfadiBand :data="xinfadiSeries" />
      </div>
      <div class="blue-grid__cell blue-grid__cell--r2a">
        <PanelBackorderBar :data="backorderSeries" />
      </div>
      <div class="blue-grid__cell blue-grid__cell--r2b">
        <PanelPriceVsBackorder
          :xinfadi-series="xinfadiSeries"
          :backorder-series="backorderSeries"
        />
      </div>
      <div class="blue-grid__cell blue-grid__cell--r3a">
        <PanelBackorderHeatmap :data="backorderSeries" />
      </div>
      <div class="blue-grid__cell blue-grid__cell--r3b">
        <PanelPriceSpreadHeatmap :data="xinfadiSeries" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import PanelXinfadiBand from './PanelXinfadiBand.vue'
import PanelBackorderBar from './PanelBackorderBar.vue'
import PanelPriceVsBackorder from './PanelPriceVsBackorder.vue'
import PanelBackorderHeatmap from './PanelBackorderHeatmap.vue'
import PanelPriceSpreadHeatmap from './PanelPriceSpreadHeatmap.vue'

const props = defineProps({
  xinfadiSeries: { type: Array, default: () => [] },
  backorderSeries: { type: Array, default: () => [] },
  loadError: { type: String, default: '' },
  clockText: { type: String, default: '' },
  rangeHint: { type: String, default: '' },
})

const emit = defineEmits(['retry'])

const riskKpis = computed(() => {
  const bo = props.backorderSeries || []
  let cnt = 0
  let amt = 0
  for (const r of bo) {
    cnt += Number(r.backorder_count || 0)
    amt += Number(r.amount_sum || 0)
  }
  const xf = props.xinfadiSeries || []
  const last = xf.length ? xf[xf.length - 1] : null
  const la = last != null && last.avg_price != null
    ? Number(last.avg_price).toFixed(2)
    : '--'
  return {
    backCnt: cnt,
    backAmtFmt: amt > 0 ? `¥${Number(amt).toLocaleString()}` : '¥0',
    lastAvg: la === '--' ? '--' : `¥${la}`,
  }
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

.blue-top__sub {
  margin: 6px 0 0;
  font-size: 11px;
  color: rgba(148, 163, 184, 0.85);
  letter-spacing: 0.04em;
}

.blue-kpi-bar {
  position: relative;
  z-index: 2;
  display: flex;
  justify-content: center;
  gap: 40px;
  padding: 6px 0 8px;
  flex-shrink: 0;
  flex-wrap: wrap;
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
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  padding: 8px 12px;
  margin-bottom: 6px;
  border-radius: 6px;
  background: rgba(80, 20, 20, 0.4);
  border: 1px solid rgba(248, 113, 113, 0.4);
  color: #fecaca;
  font-size: 13px;
}

.blue-retry { flex-shrink: 0; }

.blue-grid {
  position: relative;
  z-index: 2;
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  grid-template-rows: 1.15fr 0.95fr 0.9fr;
  gap: 8px;
}

.blue-grid__cell {
  min-height: 0;
  min-width: 0;
  overflow: hidden;
  display: flex;
}

.blue-grid__cell > * { flex: 1; min-height: 0; }

.blue-grid__cell--r1 { grid-column: 1 / 4; grid-row: 1; }
.blue-grid__cell--r2a { grid-column: 1; grid-row: 2; }
.blue-grid__cell--r2b { grid-column: 2 / 4; grid-row: 2; }
.blue-grid__cell--r3a { grid-column: 1; grid-row: 3; }
.blue-grid__cell--r3b { grid-column: 2 / 4; grid-row: 3; }

@media (max-width: 900px) {
  .blue-grid {
    grid-template-columns: 1fr;
    grid-template-rows: auto;
  }
  .blue-grid__cell--r1,
  .blue-grid__cell--r2a,
  .blue-grid__cell--r2b,
  .blue-grid__cell--r3a,
  .blue-grid__cell--r3b {
    grid-column: 1;
    grid-row: auto;
    min-height: 200px;
  }
  .blue-top { grid-template-columns: 1fr; text-align: center; }
}
</style>
