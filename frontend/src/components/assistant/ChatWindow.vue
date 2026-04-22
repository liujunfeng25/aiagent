<template>
  <div class="sx-asst-panel" role="dialog" aria-label="AI 业务分析助手">
    <div class="sx-asst-header">
      <div class="sx-asst-header__title">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <rect x="4.5" y="6" width="15" height="11.5" rx="3.2" stroke="white" stroke-width="1.6" opacity="0.9" />
          <path d="M12 3.2v2.8" stroke="white" stroke-width="1.6" stroke-linecap="round" />
          <circle cx="12" cy="3" r="1.1" fill="white" />
          <circle cx="9.5" cy="11.5" r="1.2" fill="white" />
          <circle cx="14.5" cy="11.5" r="1.2" fill="white" />
          <path d="M9.2 14.6c.7.6 1.7 1 2.8 1s2.1-.4 2.8-1" stroke="white" stroke-width="1.4" stroke-linecap="round" fill="none" />
          <path d="M3.2 11.5h1.3M19.5 11.5h1.3" stroke="white" stroke-width="1.6" stroke-linecap="round" />
        </svg>
        <div>
          <strong>业务分析助手</strong>
          <div><small>销售 · 品类 · 区域 · 日报</small></div>
        </div>
      </div>
      <div class="sx-asst-header__actions">
        <button class="sx-asst-iconbtn" :title="'清空会话'" @click="$emit('reset')">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
            <path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </button>
        <button class="sx-asst-iconbtn" :title="'关闭'" @click="$emit('close')">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
            <path d="M6 6l12 12M6 18L18 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
          </svg>
        </button>
      </div>
    </div>

    <div ref="scrollRef" class="sx-asst-scroll">
      <ChatMessage
        v-for="m in messages"
        :key="m.id"
        :message="m"
        :on-export="onExport"
      />
    </div>

    <div v-if="chips.length" class="sx-asst-chips">
      <button
        v-for="(c, i) in chips"
        :key="i"
        class="sx-asst-chip"
        :disabled="loading"
        @click="$emit('send', c)"
      >
        {{ c }}
      </button>
    </div>

    <div class="sx-asst-input">
      <textarea
        ref="inputRef"
        v-model="draft"
        :disabled="loading"
        placeholder="请输入您的问题，回车发送，Shift+回车换行"
        rows="1"
        @keydown="onKey"
        @input="autosize"
      />
      <button
        class="sx-asst-send"
        :disabled="loading || !draft.trim()"
        @click="submit"
      >
        <template v-if="loading">
          <span class="sx-asst-pending__dots" aria-hidden="true">
            <span /><span /><span />
          </span>
        </template>
        <template v-else>
          <span>发送</span>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </template>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, watch } from 'vue'
import ChatMessage from './ChatMessage.vue'

const props = defineProps({
  messages: { type: Array, required: true },
  loading: { type: Boolean, default: false },
  onExport: { type: Function, default: null },
})
const emit = defineEmits(['send', 'close', 'reset'])

const draft = ref('')
const inputRef = ref(null)
const scrollRef = ref(null)

const chips = [
  '今天哪个区卖得最好？',
  '本月品类销售 TOP10',
  '生成今日日报',
  '近 7 天 GMV 趋势',
]

function submit() {
  const t = draft.value.trim()
  if (!t || props.loading) return
  emit('send', t)
  draft.value = ''
  nextTick(autosize)
}

function onKey(e) {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault()
    submit()
  }
}

function autosize() {
  const el = inputRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 120) + 'px'
}

function scrollToBottom() {
  const el = scrollRef.value
  if (!el) return
  el.scrollTop = el.scrollHeight + 200
}

watch(
  () => props.messages.length,
  () => nextTick(scrollToBottom),
)

watch(
  () => props.messages.map((m) => m.content).join('|'),
  () => nextTick(scrollToBottom),
)

onMounted(() => {
  nextTick(() => {
    scrollToBottom()
    inputRef.value?.focus()
  })
})
</script>
