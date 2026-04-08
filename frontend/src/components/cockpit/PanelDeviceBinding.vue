<template>
  <CockpitPanelBlue title="设备绑定信息" title-en="DEVICE BINDNG">
    <div class="db">
      <div class="db__head">
        <span>车牌号</span>
        <span>摄像头</span>
        <span>北斗终端</span>
        <span>温湿度</span>
      </div>
      <div class="db__body">
        <div v-for="(row, i) in data" :key="i" class="db__row">
          <span class="db__plate">{{ row.plateno }}</span>
          <span>{{ row.camera }}</span>
          <span>{{ row.beidou }}</span>
          <span>{{ row.tempSensor }}</span>
        </div>
      </div>
    </div>
  </CockpitPanelBlue>
</template>

<script setup>
import CockpitPanelBlue from './CockpitPanelBlue.vue'

defineProps({
  data: { type: Array, default: () => [] },
})
</script>

<style scoped>
.db { display: flex; flex-direction: column; height: 100%; }

.db__head {
  display: grid;
  grid-template-columns: 1.2fr 1fr 1fr 0.8fr;
  gap: 4px;
  padding: 4px 4px;
  border-bottom: 1px solid rgba(30, 144, 255, 0.2);
  font-size: 10px;
  font-weight: 600;
  color: rgba(140, 170, 220, 0.8);
  letter-spacing: 0.04em;
}

.db__body {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}

.db__body::-webkit-scrollbar { width: 3px; }
.db__body::-webkit-scrollbar-track { background: transparent; }
.db__body::-webkit-scrollbar-thumb { background: rgba(30, 144, 255, 0.25); border-radius: 2px; }

.db__row {
  display: grid;
  grid-template-columns: 1.2fr 1fr 1fr 0.8fr;
  gap: 4px;
  padding: 4px 4px;
  font-size: 10px;
  color: rgba(200, 215, 240, 0.8);
  border-bottom: 1px solid rgba(30, 144, 255, 0.06);
  transition: background 0.2s;
}

.db__row:hover { background: rgba(30, 144, 255, 0.06); }

.db__plate {
  color: #60a5fa;
  font-weight: 500;
}
</style>
