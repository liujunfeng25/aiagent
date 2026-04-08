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
  border: 1px solid rgba(30, 144, 255, 0.28);
  background: linear-gradient(120deg, rgba(8, 19, 46, 0.85), rgba(7, 28, 58, 0.68));
  box-shadow: inset 0 0 18px rgba(30, 144, 255, 0.1);
}
.ai-page-header__title {
  margin: 0;
  font-size: 22px;
  letter-spacing: 0.04em;
  color: #e8eef8;
}
.ai-page-header__sub {
  margin: 6px 0 0;
  color: rgba(148, 163, 184, 0.9);
  font-size: 13px;
}
.ai-page-header__actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
