<template>
  <CockpitPanelBlue title="设备状态统计" title-en="DEVICE STATUS">
    <div class="ds">
      <div class="ds__cards">
        <div v-for="card in cards" :key="card.key" class="ds__card">
          <span class="ds__card-val" :style="{ color: card.color }">{{ card.value }}</span>
          <span class="ds__card-label">{{ card.label }}</span>
          <span class="ds__card-icon" :style="{ background: card.bg }">{{ card.icon }}</span>
        </div>
      </div>
      <div class="ds__bar-wrap">
        <div class="ds__bar-header">
          <span class="ds__bar-label">在线率</span>
          <span class="ds__bar-pct">{{ data.onlineRate ?? 0 }}%</span>
        </div>
        <div class="ds__bar-track">
          <div class="ds__bar-fill" :style="{ width: `${data.onlineRate ?? 0}%` }" />
        </div>
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

const cards = computed(() => [
  { key: 'total', label: '设备总数', value: props.data.total ?? 0, color: '#e8eef8', bg: 'rgba(30,144,255,0.18)', icon: '⬡' },
  { key: 'online', label: '在线', value: props.data.online ?? 0, color: '#34d399', bg: 'rgba(52,211,153,0.15)', icon: '●' },
  { key: 'offline', label: '离线', value: props.data.offline ?? 0, color: '#94a3b8', bg: 'rgba(148,163,184,0.12)', icon: '○' },
  { key: 'alarm', label: '告警', value: props.data.alarm ?? 0, color: '#f87171', bg: 'rgba(248,113,113,0.15)', icon: '⚠' },
])
</script>

<style scoped>
.ds { display: flex; flex-direction: column; height: 100%; gap: 10px; }

.ds__cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px;
}

.ds__card {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 10px 4px 8px;
  border-radius: 4px;
  background: rgba(10, 20, 50, 0.5);
  border: 1px solid rgba(30, 144, 255, 0.12);
}

.ds__card-icon {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
}

.ds__card-val {
  font-size: 22px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  text-shadow: 0 0 10px currentColor;
}

.ds__card-label {
  font-size: 11px;
  color: rgba(140, 170, 220, 0.7);
}

.ds__bar-wrap { margin-top: auto; }

.ds__bar-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
}

.ds__bar-label { font-size: 11px; color: rgba(140, 170, 220, 0.7); }
.ds__bar-pct { font-size: 13px; font-weight: 600; color: #60a5fa; }

.ds__bar-track {
  height: 8px;
  border-radius: 4px;
  background: rgba(10, 20, 50, 0.6);
  overflow: hidden;
}

.ds__bar-fill {
  height: 100%;
  border-radius: 4px;
  background: linear-gradient(90deg, #1e90ff, #00c8ff);
  box-shadow: 0 0 10px rgba(30, 144, 255, 0.5);
  transition: width 0.6s ease;
}
</style>
