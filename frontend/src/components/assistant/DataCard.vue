<template>
  <div class="sx-asst-card">
    <div class="sx-asst-card__header">
      <div class="sx-asst-card__title">
        <span class="sx-asst-card__title__icon" aria-hidden="true">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
            <path
              d="M4 19V5m4 14V10m4 9V8m4 11v-4m4 4V13"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
            />
          </svg>
        </span>
        {{ card?.title || '数据结果' }}
      </div>
    </div>

    <div v-if="kpis.length" class="sx-asst-kpis">
      <div v-for="(k, i) in kpis" :key="i" class="sx-asst-kpi">
        <div class="sx-asst-kpi__label">{{ k.label }}</div>
        <div class="sx-asst-kpi__value">{{ k.value }}</div>
        <div
          v-if="k.trend"
          class="sx-asst-kpi__trend"
          :class="{
            'sx-asst-kpi__trend--up': k.direction === 'up',
            'sx-asst-kpi__trend--down': k.direction === 'down',
          }"
        >
          {{ k.trend }}
        </div>
      </div>
    </div>

    <AssistantChart v-if="chart" :spec="chart" />

    <div v-if="rows.length" class="sx-asst-rank">
      <div v-for="(r, i) in rows" :key="i" class="sx-asst-rank__row">
        <span class="sx-asst-rank__rk">{{ r.rank ?? i + 1 }}</span>
        <div class="sx-asst-rank__main">
          <div class="sx-asst-rank__name" :title="r.name">{{ r.name }}</div>
          <div class="sx-asst-rank__bar">
            <i :style="{ width: clampBar(r.bar) + '%' }" />
          </div>
        </div>
        <div class="sx-asst-rank__value">
          {{ r.value }}
          <span v-if="r.trend" class="sx-asst-rank__trend">{{ r.trend }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import AssistantChart from './AssistantChart.vue'

const props = defineProps({ card: { type: Object, default: null } })

const kpis = computed(() => Array.isArray(props.card?.kpis) ? props.card.kpis : [])
const rows = computed(() => Array.isArray(props.card?.rows) ? props.card.rows : [])
const chart = computed(() => {
  const c = props.card?.chart
  if (!c || typeof c !== 'object') return null
  const kind = String(c.kind || '').toLowerCase()
  if (!['line', 'bar', 'pie', 'heatmap'].includes(kind)) return null
  return c
})

function clampBar(v) {
  const n = Number(v)
  if (!Number.isFinite(n)) return 0
  return Math.max(0, Math.min(100, n))
}
</script>
