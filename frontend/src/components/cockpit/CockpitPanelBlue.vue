<template>
  <div class="cpb">
    <span class="cpb__corner cpb__corner--tl" aria-hidden="true" />
    <span class="cpb__corner cpb__corner--tr" aria-hidden="true" />
    <span class="cpb__corner cpb__corner--bl" aria-hidden="true" />
    <span class="cpb__corner cpb__corner--br" aria-hidden="true" />
    <div v-if="title" class="cpb__head">
      <i class="cpb__head-dot" aria-hidden="true" />
      <span class="cpb__title">{{ title }}</span>
      <span v-if="titleEn" class="cpb__title-en">{{ titleEn }}</span>
    </div>
    <div class="cpb__body">
      <slot />
    </div>
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, default: '' },
  titleEn: { type: String, default: '' },
})
</script>

<style scoped>
.cpb {
  position: relative;
  display: flex;
  flex-direction: column;
  border-radius: 4px;
  background: linear-gradient(
    165deg,
    rgba(8, 12, 28, 0.82) 0%,
    rgba(8, 14, 32, 0.72) 50%,
    rgba(6, 38, 62, 0.35) 100%
  );
  backdrop-filter: blur(16px) saturate(1.3);
  -webkit-backdrop-filter: blur(16px) saturate(1.3);
  border: 1px solid rgba(30, 144, 255, 0.14);
  box-shadow:
    0 0 24px rgba(30, 144, 255, 0.04),
    0 2px 12px rgba(0, 0, 0, 0.25),
    inset 0 1px 0 rgba(255, 255, 255, 0.04);
  overflow: hidden;
}

.cpb__corner {
  position: absolute;
  width: 8px;
  height: 8px;
  pointer-events: none;
  z-index: 2;
  border: 1px solid transparent;
}
.cpb__corner--tl { top: -1px; left: -1px; border-top-color: rgba(30, 144, 255, 0.45); border-left-color: rgba(30, 144, 255, 0.45); }
.cpb__corner--tr { top: -1px; right: -1px; border-top-color: rgba(34, 211, 238, 0.35); border-right-color: rgba(34, 211, 238, 0.35); }
.cpb__corner--bl { bottom: -1px; left: -1px; border-bottom-color: rgba(250, 204, 21, 0.2); border-left-color: rgba(250, 204, 21, 0.2); }
.cpb__corner--br { bottom: -1px; right: -1px; border-bottom-color: rgba(30, 144, 255, 0.35); border-right-color: rgba(30, 144, 255, 0.35); }

.cpb__head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-bottom: 1px solid rgba(30, 144, 255, 0.1);
  background: linear-gradient(90deg, rgba(30, 144, 255, 0.06) 0%, transparent 60%);
  flex-shrink: 0;
}

.cpb__head-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #60a5fa;
  box-shadow: 0 0 10px rgba(30, 144, 255, 0.5), 0 0 3px rgba(96, 165, 250, 0.8);
  flex-shrink: 0;
}

.cpb__title {
  font-size: 13px;
  font-weight: 600;
  color: #f1f5f9;
  letter-spacing: 0.06em;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.4);
}

.cpb__title-en {
  font-size: 9px;
  letter-spacing: 0.18em;
  color: var(--sx-text-dim);
  text-transform: uppercase;
}

.cpb__body {
  flex: 1;
  min-height: 0;
  padding: 8px 10px;
  position: relative;
}
</style>
