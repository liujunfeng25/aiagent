<template>
  <CockpitPanelBlue title="摄像头状态" title-en="CAMERA STATUS">
    <div class="cs">
      <div v-if="!data.length" class="cs__empty">暂无摄像头数据</div>
      <div v-else class="cs__list">
        <div v-for="cam in data" :key="cam.id" class="cs__row">
          <span :class="['cs__dot', cam.status === 'online' ? 'cs__dot--on' : 'cs__dot--off']" />
          <span class="cs__name" :title="cam.name">{{ cam.name }}</span>
          <span class="cs__target">{{ cam.bindTarget }}</span>
          <span :class="['cs__badge', cam.status === 'online' ? 'cs__badge--on' : 'cs__badge--off']">
            {{ cam.status === 'online' ? '在线' : '离线' }}
          </span>
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
.cs { height: 100%; display: flex; flex-direction: column; }

.cs__empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(140, 170, 220, 0.5);
  font-size: 13px;
}

.cs__list {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}

.cs__list::-webkit-scrollbar { width: 3px; }
.cs__list::-webkit-scrollbar-track { background: transparent; }
.cs__list::-webkit-scrollbar-thumb { background: rgba(30, 144, 255, 0.25); border-radius: 2px; }

.cs__row {
  display: grid;
  grid-template-columns: 12px 1fr 0.8fr 44px;
  gap: 8px;
  align-items: center;
  padding: 8px 6px;
  border-bottom: 1px solid rgba(30, 144, 255, 0.08);
  font-size: 12px;
  transition: background 0.3s;
}

.cs__row:hover { background: rgba(30, 144, 255, 0.06); }

.cs__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.cs__dot--on {
  background: #34d399;
  box-shadow: 0 0 6px rgba(52, 211, 153, 0.7);
}

.cs__dot--off {
  background: #64748b;
}

.cs__name {
  color: #e0e8f4;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cs__target {
  color: rgba(140, 170, 220, 0.6);
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cs__badge {
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 10px;
  text-align: center;
  font-weight: 600;
}

.cs__badge--on {
  background: rgba(52, 211, 153, 0.15);
  color: #34d399;
  border: 1px solid rgba(52, 211, 153, 0.25);
}

.cs__badge--off {
  background: rgba(100, 116, 139, 0.15);
  color: #94a3b8;
  border: 1px solid rgba(100, 116, 139, 0.2);
}
</style>
