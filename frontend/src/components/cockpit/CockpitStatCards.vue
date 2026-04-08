<template>
  <div class="stat-row">
    <div v-for="c in cards" :key="c.key" class="stat-card">
      <span class="stat-card__corner stat-card__corner--tl" aria-hidden="true" />
      <span class="stat-card__corner stat-card__corner--tr" aria-hidden="true" />
      <span class="stat-card__corner stat-card__corner--bl" aria-hidden="true" />
      <span class="stat-card__corner stat-card__corner--br" aria-hidden="true" />
      <div class="stat-card__accent" aria-hidden="true" />
      <div class="stat-card__body">
        <div class="stat-card__label">{{ c.label }}</div>
        <div class="stat-card__label-en">{{ c.labelEn }}</div>
        <div class="stat-card__value">{{ c.value }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  stats: {
    type: Object,
    default: () => ({ total: 0, online: 0, alarm: 0, tempBad: 0 }),
  },
})

const cards = computed(() => [
  { key: 'total', label: '总车辆数', labelEn: 'TOTAL UNITS', value: props.stats.total },
  { key: 'online', label: '在线车辆数', labelEn: 'ONLINE', value: props.stats.online },
  { key: 'alarm', label: '告警车辆数', labelEn: 'ALARM', value: props.stats.alarm },
  { key: 'temp', label: '温度异常车辆数', labelEn: 'TEMP ABNORMAL', value: props.stats.tempBad },
])
</script>

<style scoped>
.stat-row {
  position: relative;
  z-index: 2;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 12px;
  flex-shrink: 0;
}

.stat-card {
  position: relative;
  padding: 14px 16px 14px 20px;
  border-radius: 2px;
  background: linear-gradient(165deg, rgba(15, 23, 42, 0.92) 0%, rgba(15, 23, 42, 0.72) 50%, rgba(8, 47, 73, 0.35) 100%);
  border: 1px solid rgba(34, 211, 238, 0.22);
  box-shadow:
    0 0 24px rgba(34, 211, 238, 0.06),
    inset 0 1px 0 rgba(255, 255, 255, 0.04);
  overflow: visible;
}

.stat-card__accent {
  position: absolute;
  left: 0;
  top: 8px;
  bottom: 8px;
  width: 3px;
  border-radius: 1px;
  background: linear-gradient(180deg, rgba(250, 204, 21, 0.95), rgba(34, 211, 238, 0.75), rgba(8, 145, 178, 0.5));
  box-shadow: 0 0 12px rgba(34, 211, 238, 0.35);
}

.stat-card__corner {
  position: absolute;
  width: 8px;
  height: 8px;
  pointer-events: none;
  border: 1px solid transparent;
  opacity: 0.9;
}

.stat-card__corner--tl {
  top: -1px;
  left: -1px;
  border-top-color: rgba(34, 211, 238, 0.75);
  border-left-color: rgba(34, 211, 238, 0.75);
}
.stat-card__corner--tr {
  top: -1px;
  right: -1px;
  border-top-color: rgba(250, 204, 21, 0.55);
  border-right-color: rgba(250, 204, 21, 0.55);
}
.stat-card__corner--bl {
  bottom: -1px;
  left: -1px;
  border-bottom-color: rgba(250, 204, 21, 0.45);
  border-left-color: rgba(250, 204, 21, 0.45);
}
.stat-card__corner--br {
  bottom: -1px;
  right: -1px;
  border-bottom-color: rgba(34, 211, 238, 0.55);
  border-right-color: rgba(34, 211, 238, 0.55);
}

.stat-card__body {
  position: relative;
  z-index: 1;
}

.stat-card__label {
  font-size: 13px;
  color: rgba(186, 230, 253, 0.9);
  letter-spacing: 0.06em;
  margin-bottom: 2px;
}

.stat-card__label-en {
  font-size: 9px;
  letter-spacing: 0.22em;
  color: rgba(148, 163, 184, 0.65);
  text-transform: uppercase;
  margin-bottom: 10px;
}

.stat-card__value {
  font-size: clamp(26px, 3.2vw, 34px);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: #f0f9ff;
  text-shadow:
    0 0 14px rgba(34, 211, 238, 0.5),
    0 0 28px rgba(234, 179, 8, 0.12);
  line-height: 1.05;
}

@media (max-width: 1100px) {
  .stat-row {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 520px) {
  .stat-row {
    grid-template-columns: 1fr;
  }
}
</style>
