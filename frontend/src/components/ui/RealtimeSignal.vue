<template>
  <span :class="['signal', `signal--${status}`]">
    <i class="signal__dot" />
    <span>{{ label }}</span>
  </span>
</template>

<script setup>
defineProps({
  status: { type: String, default: 'ok' }, // ok | warn | danger
  label: { type: String, default: '运行中' },
})
</script>

<style scoped>
.signal { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: rgba(226, 232, 240, 0.95); }
.signal__dot { width: 8px; height: 8px; border-radius: 999px; background: #34d399; box-shadow: 0 0 8px rgba(52,211,153,.8); animation: pulse 1.8s infinite; }
.signal--warn .signal__dot { background: #f59e0b; box-shadow: 0 0 8px rgba(245,158,11,.8); }
.signal--danger .signal__dot { background: #f87171; box-shadow: 0 0 8px rgba(248,113,113,.9); }
@keyframes pulse { 0%,100% { transform: scale(1);} 50% { transform: scale(1.35);} }
</style>
