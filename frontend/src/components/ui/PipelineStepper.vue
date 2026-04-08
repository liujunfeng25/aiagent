<template>
  <div class="pipe">
    <div
      v-for="(item, idx) in items"
      :key="item.key || idx"
      :class="['pipe__item', { 'pipe__item--active': idx <= activeIndex }]"
    >
      <span class="pipe__idx">{{ idx + 1 }}</span>
      <span class="pipe__name">{{ item.label }}</span>
    </div>
  </div>
</template>

<script setup>
defineProps({
  items: { type: Array, default: () => [] },
  activeIndex: { type: Number, default: 0 },
})
</script>

<style scoped>
.pipe {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}
.pipe__item {
  display: flex;
  align-items: center;
  gap: 8px;
  border: 1px solid rgba(100, 116, 139, 0.35);
  border-radius: 999px;
  padding: 6px 10px;
  color: rgba(148, 163, 184, 0.9);
  background: rgba(15, 23, 42, 0.38);
}
.pipe__item--active {
  border-color: rgba(30, 144, 255, 0.6);
  color: #e8eef8;
  box-shadow: inset 0 0 12px rgba(30, 144, 255, 0.18);
}
.pipe__idx {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  background: rgba(30, 144, 255, 0.25);
}
.pipe__name {
  font-size: 12px;
  white-space: nowrap;
}
</style>
