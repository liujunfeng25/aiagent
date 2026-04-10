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
.cp {
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
  border: 1px solid rgba(34, 211, 238, 0.12);
  box-shadow:
    0 0 24px rgba(34, 211, 238, 0.04),
    0 2px 12px rgba(0, 0, 0, 0.25),
    inset 0 1px 0 rgba(255, 255, 255, 0.04);
  overflow: hidden;
}

.cp__corner {
  position: absolute;
  width: 8px;
  height: 8px;
  pointer-events: none;
  z-index: 2;
  border: 1px solid transparent;
}
.cp__corner--tl { top: -1px; left: -1px; border-top-color: rgba(34, 211, 238, 0.45); border-left-color: rgba(34, 211, 238, 0.45); }
.cp__corner--tr { top: -1px; right: -1px; border-top-color: rgba(250, 204, 21, 0.25); border-right-color: rgba(250, 204, 21, 0.25); }
.cp__corner--bl { bottom: -1px; left: -1px; border-bottom-color: rgba(250, 204, 21, 0.2); border-left-color: rgba(250, 204, 21, 0.2); }
.cp__corner--br { bottom: -1px; right: -1px; border-bottom-color: rgba(34, 211, 238, 0.3); border-right-color: rgba(34, 211, 238, 0.3); }

.cp__head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-bottom: 1px solid rgba(34, 211, 238, 0.08);
  background: linear-gradient(90deg, rgba(34, 211, 238, 0.05) 0%, rgba(234, 179, 8, 0.02) 52%, transparent 72%);
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
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #67e8f9;
  box-shadow: 0 0 10px rgba(34, 211, 238, 0.5), 0 0 3px rgba(34, 211, 238, 0.8);
  flex-shrink: 0;
}

.cp__title {
  font-size: 13px;
  font-weight: 600;
  color: #f1f5f9;
  letter-spacing: 0.06em;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.4);
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
