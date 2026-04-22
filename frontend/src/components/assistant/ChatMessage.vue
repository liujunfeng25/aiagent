<template>
  <div
    class="sx-asst-msg"
    :class="{
      'sx-asst-msg--user': message.role === 'user',
      'sx-asst-msg--assistant': message.role === 'assistant',
      'sx-asst-msg--error': message.error,
    }"
  >
    <span class="sx-asst-avatar" aria-hidden="true">
      <template v-if="message.role === 'user'">我</template>
      <template v-else>AI</template>
    </span>
    <div class="sx-asst-msg__body">
      <div
        v-if="message.role === 'assistant' && message.pending"
        class="sx-asst-pending-head"
      >
        <div
          class="sx-asst-progress-track"
          :class="{ 'sx-asst-progress-track--shimmer': progressPct < 22 }"
        >
          <div
            class="sx-asst-progress-fill"
            :style="{ width: progressWidth }"
          />
        </div>
        <div v-if="message.eta_hint" class="sx-asst-eta-hint">
          {{ message.eta_hint }}
        </div>
      </div>
      <div class="sx-asst-bubble-text">
        <template v-if="message.pending">
          <template v-if="visibleText">
            <span>{{ visibleText }}</span>
            <span class="sx-asst-caret" aria-hidden="true" />
          </template>
          <template v-else>
            <span class="sx-asst-phase">{{ message.phase || '思考中' }}</span>
            <span class="sx-asst-pending__dots"><span /><span /><span /></span>
          </template>
        </template>
        <template v-else>{{ visibleText }}</template>
      </div>
      <div v-if="latencyLine" class="sx-asst-latency">
        {{ latencyLine }}
      </div>
      <DataCard v-if="message.data_card" :card="message.data_card" />
      <ReportCard
        v-if="message.report_content"
        :title="reportTitle"
        :markdown="message.report_content"
        :formats="message.export_formats"
        :on-export="onExport"
      />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import DataCard from './DataCard.vue'
import ReportCard from './ReportCard.vue'

const props = defineProps({
  message: { type: Object, required: true },
  onExport: { type: Function, default: null },
})

// 剥掉 <data_card>/<report_content> 块，气泡只展示自然语言
const visibleText = computed(() => {
  const c = props.message.content || ''
  return c
    .replace(/<data_card>[\s\S]*?<\/data_card>/g, '')
    .replace(/<report_content>[\s\S]*?<\/report_content>/g, '')
    .trim()
})

const reportTitle = computed(() => {
  const md = props.message.report_content || ''
  const m = /^#\s+(.+)$/m.exec(md)
  return (m && m[1].trim()) || props.message.title || '业务报告'
})

const progressPct = computed(() => {
  const n = Number(props.message.progress_pct)
  return Number.isFinite(n) ? Math.min(100, Math.max(0, n)) : 8
})

const progressWidth = computed(() => `${progressPct.value}%`)

const latencyLine = computed(() => {
  if (props.message.pending || props.message.role !== 'assistant') return ''
  const lat = props.message.latency_sec
  if (lat == null || Number.isNaN(Number(lat))) return ''
  const srv = props.message.server_elapsed_ms
  let s = `耗时 ${Number(lat).toFixed(1)}s`
  if (typeof srv === 'number' && srv >= 0) {
    s += `（服务端 ${(srv / 1000).toFixed(1)}s）`
  }
  return s
})
</script>
