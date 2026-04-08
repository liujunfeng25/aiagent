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
  border-radius: var(--sx-radius-cockpit-tile);
  background: var(--sx-panel-fill);
  border: 1px solid var(--sx-glass-border);
  box-shadow: var(--sx-panel-shadow);
  overflow: hidden;
}

.cpb__corner {
  position: absolute;
  width: 10px;
  height: 10px;
  pointer-events: none;
  z-index: 2;
  border: 1.5px solid transparent;
}
.cpb__corner--tl { top: -1px; left: -1px; border-top-color: var(--sx-primary); border-left-color: var(--sx-primary); }
.cpb__corner--tr { top: -1px; right: -1px; border-top-color: var(--sx-edge-cyan-strong); border-right-color: var(--sx-edge-cyan-strong); }
.cpb__corner--bl { bottom: -1px; left: -1px; border-bottom-color: var(--sx-corner-gold-soft); border-left-color: var(--sx-corner-gold-soft); }
.cpb__corner--br { bottom: -1px; right: -1px; border-bottom-color: var(--sx-primary); border-right-color: var(--sx-primary); }

.cpb__head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-bottom: 1px solid rgba(30, 144, 255, 0.18);
  background: linear-gradient(90deg, rgba(30, 144, 255, 0.10) 0%, transparent 60%);
  flex-shrink: 0;
}

.cpb__head-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--sx-primary);
  box-shadow: 0 0 8px var(--sx-glow-cyan);
  flex-shrink: 0;
}

.cpb__title {
  font-size: 13px;
  font-weight: 600;
  color: var(--sx-text-title);
  letter-spacing: 0.06em;
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
