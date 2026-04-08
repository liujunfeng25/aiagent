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
.im {
  border: 1px solid var(--sx-glass-border);
  border-radius: 10px;
  padding: 10px 12px;
  background: var(--sx-metric-bg);
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.im__label { font-size: 12px; color: var(--sx-text-muted); }
.im__value { color: var(--sx-text-title); font-size: 22px; line-height: 1.2; }
.im__trend { font-size: 12px; }
.im__trend.up { color: var(--sx-success); }
.im__trend.down { color: var(--sx-danger); }
</style>
