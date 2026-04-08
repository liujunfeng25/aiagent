<template>
  <CockpitPanelBlue title="视频监控" title-en="VIDEO FEED">
    <div class="cf">
      <div v-for="cam in data" :key="cam.id" class="cf__cell">
        <div class="cf__thumb">
          <img v-if="cam.thumbUrl" :src="cam.thumbUrl" :alt="cam.name" class="cf__img" />
          <div v-else class="cf__placeholder">
            <span class="cf__cam-icon">📷</span>
            <span class="cf__cam-no-signal">{{ cam.status === 'offline' ? '离线' : 'LIVE' }}</span>
          </div>
        </div>
        <div class="cf__info">
          <span class="cf__name" :title="cam.name">{{ cam.name }}</span>
          <span :class="['cf__dot', cam.status === 'online' ? 'cf__dot--on' : 'cf__dot--off']" />
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
.cf {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  height: 100%;
}

.cf__cell {
  display: flex;
  flex-direction: column;
  border-radius: 4px;
  overflow: hidden;
  background: rgba(5, 12, 35, 0.6);
  border: 1px solid rgba(30, 144, 255, 0.12);
}

.cf__thumb {
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}

.cf__img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.cf__placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  width: 100%;
  height: 100%;
  background: linear-gradient(180deg, rgba(8, 20, 60, 0.9), rgba(5, 12, 35, 0.95));
}

.cf__cam-icon { font-size: 24px; opacity: 0.4; }

.cf__cam-no-signal {
  font-size: 10px;
  letter-spacing: 0.15em;
  color: rgba(140, 170, 220, 0.5);
  font-weight: 600;
}

.cf__info {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 6px;
  background: rgba(5, 12, 35, 0.8);
  border-top: 1px solid rgba(30, 144, 255, 0.1);
}

.cf__name {
  flex: 1;
  font-size: 10px;
  color: #cbd5e1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cf__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.cf__dot--on {
  background: #34d399;
  box-shadow: 0 0 6px rgba(52, 211, 153, 0.7);
}

.cf__dot--off {
  background: #64748b;
}
</style>
