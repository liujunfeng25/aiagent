<template>
  <div class="msc">
    <div class="msc__name">{{ name }}</div>
    <div class="msc__meta">
      <span>版本 {{ version }}</span>
      <span>准确率 {{ accuracy }}%</span>
    </div>
    <RealtimeSignal :status="status" :label="statusLabel" />
  </div>
</template>

<script setup>
import RealtimeSignal from './RealtimeSignal.vue'

defineProps({
  name: { type: String, default: '模型' },
  version: { type: String, default: 'v1.0.0' },
  accuracy: { type: [Number, String], default: 0 },
  status: { type: String, default: 'ok' },
  statusLabel: { type: String, default: '已部署' },
})
</script>

<style scoped>
.msc { border: 1px solid rgba(30, 144, 255, 0.25); border-radius: 10px; padding: 10px 12px; background: rgba(8, 17, 38, 0.62); }
.msc__name { color: #e8eef8; font-weight: 600; margin-bottom: 6px; }
.msc__meta { display: flex; gap: 10px; color: rgba(148, 163, 184, 0.9); font-size: 12px; margin-bottom: 8px; }
</style>
