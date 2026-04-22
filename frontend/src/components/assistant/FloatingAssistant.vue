<template>
  <div class="sx-asst-root">
    <transition name="sx-asst-fade">
      <div
        v-if="open"
        class="sx-asst-backdrop"
        @click.self="open = false"
        aria-hidden="true"
      />
    </transition>

    <transition name="sx-asst-pop">
      <ChatWindow
        v-if="open"
        :messages="messages"
        :loading="loading"
        :on-export="handleExport"
        @send="handleSend"
        @close="open = false"
        @reset="reset"
      />
    </transition>

    <button
      v-if="!open"
      class="sx-asst-orb"
      :class="{ 'is-thinking': loading }"
      type="button"
      :title="'AI 业务分析助手'"
      @click="open = true"
      aria-label="打开 AI 业务分析助手"
    >
      <span class="sx-asst-orb__halo" aria-hidden="true" />
      <span class="sx-asst-orb__ring" aria-hidden="true" />
      <span class="sx-asst-orb__core" aria-hidden="true" />
      <span class="sx-asst-orb__mark" aria-hidden="true">AI</span>
      <span class="sx-asst-orb__sparkle sx-asst-orb__sparkle--a" aria-hidden="true" />
      <span class="sx-asst-orb__sparkle sx-asst-orb__sparkle--b" aria-hidden="true" />
    </button>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import ChatWindow from './ChatWindow.vue'
import { useAssistantChat } from '../../composables/useAssistantChat'
import '../../styles/assistant.css'

const open = ref(false)
const { messages, loading, send, reset, downloadReport } = useAssistantChat()

function handleSend(text) {
  if (!open.value) open.value = true
  send(text)
}

async function handleExport({ title, markdown, format }) {
  await downloadReport({ title, markdown, filename: title, format })
}

function onKeydown(e) {
  if (e.key === 'Escape' && open.value) {
    open.value = false
  }
}

watch(open, (v) => {
  // 弹窗打开时锁住主站滚动，营造「专注对话」的氛围
  if (typeof document === 'undefined') return
  document.body.classList.toggle('sx-asst-lock-scroll', v)
})

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  if (typeof document !== 'undefined') {
    document.body.classList.remove('sx-asst-lock-scroll')
  }
})
</script>
