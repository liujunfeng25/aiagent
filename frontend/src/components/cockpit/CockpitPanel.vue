<template>
  <div class="cp">
    <span class="cp__corner cp__corner--tl" aria-hidden="true" />
    <span class="cp__corner cp__corner--tr" aria-hidden="true" />
    <span class="cp__corner cp__corner--bl" aria-hidden="true" />
    <span class="cp__corner cp__corner--br" aria-hidden="true" />
    <div v-if="title" class="cp__head">
      <i class="cp__head-dot" aria-hidden="true" />
      <div class="cp__head-text">
        <div class="cp__head-titles">
          <span class="cp__title">{{ title }}</span>
          <span v-if="titleEn" class="cp__title-en">{{ titleEn }}</span>
        </div>
        <p v-if="hint" class="cp__hint">{{ hint }}</p>
      </div>
      <div class="cp__head-actions">
        <slot name="titleActions" />
      </div>
    </div>
    <div class="cp__body">
      <slot />
    </div>
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, default: '' },
  titleEn: { type: String, default: '' },
  /** 标题下方一行说明（如统计区间） */
  hint: { type: String, default: '' },
})
</script>

<style scoped>
/* 青金角标 + 深空玻璃：与驾驶舱「上一版」视觉一致（运营 / 智能沿用；物联为 PanelBlue） */
.cp {
  position: relative;
  display: flex;
  flex-direction: column;
  border-radius: 2px;
  background: linear-gradient(165deg, rgba(10, 15, 35, 0.94) 0%, rgba(10, 15, 35, 0.78) 50%, rgba(8, 47, 73, 0.25) 100%);
  border: 1px solid rgba(34, 211, 238, 0.25);
  box-shadow:
    0 0 20px rgba(34, 211, 238, 0.05),
    inset 0 1px 0 rgba(255, 255, 255, 0.03);
  overflow: hidden;
}

.cp__corner {
  position: absolute;
  width: 10px;
  height: 10px;
  pointer-events: none;
  z-index: 2;
  border: 1.5px solid transparent;
}
.cp__corner--tl { top: -1px; left: -1px; border-top-color: rgba(34, 211, 238, 0.8); border-left-color: rgba(34, 211, 238, 0.8); }
.cp__corner--tr { top: -1px; right: -1px; border-top-color: rgba(250, 204, 21, 0.6); border-right-color: rgba(250, 204, 21, 0.6); }
.cp__corner--bl { bottom: -1px; left: -1px; border-bottom-color: rgba(250, 204, 21, 0.5); border-left-color: rgba(250, 204, 21, 0.5); }
.cp__corner--br { bottom: -1px; right: -1px; border-bottom-color: rgba(34, 211, 238, 0.6); border-right-color: rgba(34, 211, 238, 0.6); }

.cp__head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-bottom: 1px solid rgba(34, 211, 238, 0.15);
  background: linear-gradient(90deg, rgba(34, 211, 238, 0.08) 0%, rgba(234, 179, 8, 0.04) 52%, transparent 72%);
  flex-shrink: 0;
}

.cp__head-text {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  flex: 1;
  min-width: 0;
}

.cp__head-titles {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 8px;
  row-gap: 2px;
}

.cp__head-actions {
  margin-left: auto;
  flex-shrink: 0;
  display: flex;
  align-items: center;
}

.cp__head-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #22d3ee;
  box-shadow: 0 0 8px rgba(34, 211, 238, 0.6);
  flex-shrink: 0;
}

.cp__title {
  font-size: 13px;
  font-weight: 600;
  color: #e2e8f0;
  letter-spacing: 0.06em;
}

.cp__title-en {
  font-size: 9px;
  letter-spacing: 0.18em;
  color: rgba(148, 163, 184, 0.6);
  text-transform: uppercase;
}

.cp__hint {
  width: 100%;
  margin: 0;
  padding: 0;
  font-size: 10px;
  line-height: 1.35;
  color: rgba(148, 163, 184, 0.9);
  letter-spacing: 0.03em;
  font-weight: 400;
}

.cp__body {
  flex: 1;
  min-height: 0;
  padding: 8px 10px;
  position: relative;
  display: flex;
  flex-direction: column;
}
</style>
