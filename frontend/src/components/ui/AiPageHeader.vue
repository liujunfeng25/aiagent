<template>
  <div class="ai-page-header">
    <div>
      <h1 class="ai-page-header__title">{{ title }}</h1>
      <p v-if="subtitle" class="ai-page-header__sub">{{ subtitle }}</p>
    </div>
    <div v-if="$slots.actions" class="ai-page-header__actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
})
</script>

<style scoped>
.ai-page-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  margin-bottom: 14px;
  border-radius: 12px;
  border: 1px solid var(--sx-glass-border);
  background: var(--sx-glass-page-header);
  box-shadow: var(--sx-inset-glow-header);
}
.ai-page-header__title {
  margin: 0;
  font-size: 22px;
  letter-spacing: 0.04em;
  color: var(--sx-text-title);
  text-shadow: var(--sx-text-shadow-readable);
}
.ai-page-header__sub {
  margin: 6px 0 0;
  color: var(--sx-text-readable-muted);
  font-size: 13px;
  text-shadow: var(--sx-text-shadow-strong);
  max-width: 72ch;
}
.ai-page-header__actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
