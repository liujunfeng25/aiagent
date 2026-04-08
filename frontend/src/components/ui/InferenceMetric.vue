<template>
  <div class="im">
    <span class="im__label">{{ label }}</span>
    <strong class="im__value">{{ value }}</strong>
    <span v-if="trend" :class="['im__trend', trend > 0 ? 'up' : 'down']">{{ trend > 0 ? '▲' : '▼' }} {{ Math.abs(trend) }}%</span>
  </div>
</template>

<script setup>
defineProps({
  label: { type: String, default: '' },
  value: { type: [String, Number], default: '--' },
  trend: { type: Number, default: 0 },
})
</script>

<style scoped>
.im { border: 1px solid rgba(30, 144, 255, 0.25); border-radius: 10px; padding: 10px 12px; background: rgba(8, 17, 38, 0.62); display: flex; flex-direction: column; gap: 4px; }
.im__label { font-size: 12px; color: rgba(148,163,184,.86); }
.im__value { color: #e8eef8; font-size: 22px; line-height: 1.2; }
.im__trend { font-size: 12px; }
.im__trend.up { color: #34d399; }
.im__trend.down { color: #f87171; }
</style>
