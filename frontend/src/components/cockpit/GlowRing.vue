<template>
  <div class="saturn-scene" :style="sceneStyle">
    <div class="saturn-ring saturn-ring--outer" :style="ringStyle" />
    <div class="saturn-ring saturn-ring--dashed" :style="innerRingStyle" />
    <div class="saturn-dot-track" :style="ringStyle">
      <span class="saturn-dot" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  size: { type: Number, default: 160 },
})

const sceneStyle = computed(() => ({
  '--ring-size': `${props.size}px`,
}))

const ringStyle = computed(() => ({
  width: `${props.size}px`,
  height: `${props.size}px`,
  marginTop: `${-props.size / 2}px`,
  marginLeft: `${-props.size / 2}px`,
}))

const innerRingStyle = computed(() => {
  const inner = props.size - 12
  return {
    width: `${inner}px`,
    height: `${inner}px`,
    marginTop: `${-inner / 2}px`,
    marginLeft: `${-inner / 2}px`,
  }
})
</script>

<style scoped>
.saturn-scene {
  position: absolute;
  inset: 0;
  perspective: 600px;
  pointer-events: none;
  overflow: visible;
}

.saturn-ring {
  position: absolute;
  top: 50%;
  left: 50%;
  border-radius: 50%;
  transform-style: preserve-3d;
}

.saturn-ring--outer {
  border: 2px solid rgba(30, 144, 255, 0.35);
  box-shadow:
    0 0 14px rgba(30, 144, 255, 0.25),
    inset 0 0 14px rgba(30, 144, 255, 0.08);
  animation: saturn-orbit 10s linear infinite, saturn-pulse 4s ease-in-out infinite;
}

.saturn-ring--dashed {
  border: 1.5px dashed rgba(0, 200, 255, 0.28);
  box-shadow: 0 0 8px rgba(0, 200, 255, 0.12);
  animation: saturn-orbit-reverse 15s linear infinite;
}

.saturn-dot-track {
  position: absolute;
  top: 50%;
  left: 50%;
  border-radius: 50%;
  border: none;
  animation: saturn-orbit 10s linear infinite;
  transform-style: preserve-3d;
}

.saturn-dot {
  position: absolute;
  top: -3px;
  left: 50%;
  width: 6px;
  height: 6px;
  margin-left: -3px;
  border-radius: 50%;
  background: #4db8ff;
  box-shadow:
    0 0 8px rgba(30, 144, 255, 0.8),
    0 0 20px rgba(30, 144, 255, 0.4);
}

@keyframes saturn-orbit {
  from { transform: rotateX(68deg) rotateZ(0deg); }
  to { transform: rotateX(68deg) rotateZ(360deg); }
}

@keyframes saturn-orbit-reverse {
  from { transform: rotateX(68deg) rotateZ(360deg); }
  to { transform: rotateX(68deg) rotateZ(0deg); }
}

@keyframes saturn-pulse {
  0%, 100% {
    opacity: 0.55;
    box-shadow: 0 0 14px rgba(30, 144, 255, 0.25), inset 0 0 14px rgba(30, 144, 255, 0.08);
  }
  50% {
    opacity: 1;
    box-shadow: 0 0 22px rgba(30, 144, 255, 0.45), inset 0 0 18px rgba(30, 144, 255, 0.15);
  }
}
</style>
