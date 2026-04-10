<template>
  <div class="iot-shell">
    <div class="iot-shell__bg" aria-hidden="true" />
    <div class="iot-shell__scan" aria-hidden="true" />

    <header class="iot-top">
      <div class="iot-top__side iot-top__side--left">
        <span class="iot-top__tag">IoT · MONITORING</span>
      </div>
      <div class="iot-top__center">
        <div class="iot-top__title-line" />
        <h1 class="iot-top__title">物联数据监控预警平台</h1>
        <div class="iot-top__title-line iot-top__title-line--short" />
      </div>
      <div class="iot-top__side iot-top__side--right">
        <span class="iot-top__clock">{{ clockText }}</span>
      </div>
    </header>

    <div v-if="loadError" class="iot-shell__err">{{ loadError }}</div>

    <div class="iot-grid">
      <!-- Left Column -->
      <div class="iot-grid__cell iot-grid__cell--l1">
        <PanelDeviceStatus :data="deviceStatus" />
      </div>
      <div class="iot-grid__cell iot-grid__cell--l2">
        <PanelAlarmLog :data="allCameras" />
      </div>

      <!-- Center Column -->
      <div class="iot-grid__cell iot-grid__cell--map">
        <CockpitPanelBlue title="实时定位监控" title-en="REAL-TIME TRACKING">
          <AMapMonitor :vehicles="vehicles" :warehouses="warehouses" />
        </CockpitPanelBlue>
      </div>

      <!-- Right Column -->
      <div class="iot-grid__cell iot-grid__cell--r1">
        <PanelCameraFeed :data="cameraList" />
      </div>
      <div class="iot-grid__cell iot-grid__cell--r2">
        <PanelDeviceBinding :data="deviceBindings" />
      </div>
      <div class="iot-grid__cell iot-grid__cell--r3">
        <PanelTempHumidity :data="tempHumidity" :threshold="tempThreshold" />
      </div>
    </div>
  </div>
</template>

<script setup>
import CockpitPanelBlue from './CockpitPanelBlue.vue'
import AMapMonitor from './AMapMonitor.vue'
import PanelDeviceStatus from './PanelDeviceStatus.vue'
import PanelAlarmLog from './PanelAlarmLog.vue'
import PanelCameraFeed from './PanelCameraFeed.vue'
import PanelDeviceBinding from './PanelDeviceBinding.vue'
import PanelTempHumidity from './PanelTempHumidity.vue'

defineProps({
  deviceStatus: { type: Object, default: () => ({}) },
  allCameras: { type: Array, default: () => [] },
  cameraList: { type: Array, default: () => [] },
  deviceBindings: { type: Array, default: () => [] },
  tempHumidity: { type: Array, default: () => [] },
  tempThreshold: { type: Number, default: 8 },
  vehicles: { type: Array, default: () => [] },
  warehouses: { type: Array, default: () => [] },
  clockText: { type: String, default: '' },
  loadError: { type: String, default: '' },
})
</script>

<style scoped>
.iot-shell {
  position: relative;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  height: 100%;
  padding: 14px 16px 16px;
  color: var(--sx-text-title);
  overflow: hidden;
}

.iot-shell__bg {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  background: url('/cockpit-bg.jpg') center / cover no-repeat;
  background-color: #060a14;
}

.iot-shell__bg::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse 90% 60% at 50% 10%, rgba(34, 211, 238, 0.06), transparent 55%),
    linear-gradient(
      180deg,
      rgba(6, 10, 20, 0.84) 0%,
      rgba(6, 10, 20, 0.68) 35%,
      rgba(6, 10, 20, 0.75) 65%,
      rgba(6, 10, 20, 0.88) 100%
    );
}

.iot-shell__bg::after {
  content: '';
  position: absolute;
  inset: 0;
  opacity: 0.06;
  background-image:
    linear-gradient(rgba(34, 211, 238, 0.12) 1px, transparent 1px),
    linear-gradient(90deg, rgba(34, 211, 238, 0.08) 1px, transparent 1px);
  background-size: 96px 96px;
}

.iot-shell__scan {
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  background: linear-gradient(
    180deg,
    transparent 0%,
    rgba(34, 211, 238, 0.018) 47%,
    rgba(56, 189, 248, 0.025) 50%,
    transparent 53%
  );
  background-size: 100% 280%;
  animation: iot-scan 18s linear infinite;
  opacity: 0.4;
}

@keyframes iot-scan {
  0% { background-position: 0% 0%; }
  100% { background-position: 0% 100%; }
}

/* Header */
.iot-top {
  position: relative;
  z-index: 2;
  display: grid;
  grid-template-columns: 1fr minmax(200px, 480px) 1fr;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
  padding: 2px 0 4px;
}

.iot-top__side { display: flex; align-items: center; min-height: 32px; }
.iot-top__side--left { justify-content: flex-start; }
.iot-top__side--right { justify-content: flex-end; }

.iot-top__tag {
  font-family: ui-monospace, 'SF Mono', Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  color: rgba(140, 170, 220, 0.7);
  letter-spacing: 0.08em;
}

.iot-top__center { text-align: center; }

.iot-top__title-line {
  height: 2px;
  width: min(80%, 280px);
  margin: 0 auto 6px;
  background: var(--sx-title-line-gradient);
  box-shadow: 0 0 12px var(--sx-glow-cyan);
  border-radius: 2px;
}

.iot-top__title-line--short {
  width: min(40%, 140px);
  margin: 6px auto 0;
  opacity: 0.6;
}

.iot-top__title {
  font-size: clamp(18px, 2.4vw, 26px);
  font-weight: 700;
  letter-spacing: 0.22em;
  color: var(--sx-text-bright);
  text-shadow: 0 0 20px var(--sx-glow-cyan-soft), 0 0 36px rgba(30, 144, 255, 0.15);
  margin: 0;
  line-height: 1.2;
}

.iot-top__clock {
  font-family: ui-monospace, 'SF Mono', Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
  font-weight: 600;
  color: var(--sx-text-clock);
  text-shadow: 0 0 8px var(--sx-glow-cyan);
  letter-spacing: 0.04em;
}

.iot-shell__err {
  position: relative;
  z-index: 2;
  padding: 8px 12px;
  margin-bottom: 6px;
  border-radius: 6px;
  background: var(--sx-error-bg);
  border: 1px solid var(--sx-error-border);
  color: var(--sx-error-text);
  font-size: 13px;
}

/* 3-column Grid */
.iot-grid {
  position: relative;
  z-index: 2;
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 1fr 2fr 1fr;
  grid-template-rows: 1fr 1fr 1fr;
  gap: 8px;
}

.iot-grid__cell {
  min-height: 0;
  min-width: 0;
  overflow: hidden;
  display: flex;
}

.iot-grid__cell > * { flex: 1; min-height: 0; }

.iot-grid__cell--l1 { grid-column: 1; grid-row: 1; }
.iot-grid__cell--l2 { grid-column: 1; grid-row: 2 / 4; }
.iot-grid__cell--map { grid-column: 2; grid-row: 1 / 4; }
.iot-grid__cell--r1 { grid-column: 3; grid-row: 1; }
.iot-grid__cell--r2 { grid-column: 3; grid-row: 2; }
.iot-grid__cell--r3 { grid-column: 3; grid-row: 3; }

@media (max-width: 900px) {
  .iot-grid {
    grid-template-columns: 1fr;
    grid-template-rows: auto;
  }
  .iot-grid__cell--l1,
  .iot-grid__cell--l2,
  .iot-grid__cell--map,
  .iot-grid__cell--r1,
  .iot-grid__cell--r2,
  .iot-grid__cell--r3 {
    grid-column: 1;
    grid-row: auto;
    min-height: 200px;
  }
  .iot-grid__cell--map { min-height: 360px; }
  .iot-top { grid-template-columns: 1fr; text-align: center; }
}
</style>
