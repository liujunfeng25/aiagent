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
      <svg
        class="sx-asst-orb__mark"
        viewBox="0 0 24 24"
        fill="none"
        aria-hidden="true"
      >
        <path
          d="M12 3.2c-3.9 0-7 2.7-7 6.1 0 2.1 1.2 3.9 3.1 5v1.3c0 .4.3.8.7.9l2 .4v1.5c0 .4.3.8.8.8h.8c.4 0 .8-.3.8-.8v-1.5l2-.4c.4-.1.7-.5.7-.9v-1.3c1.9-1.1 3.1-2.9 3.1-5 0-3.4-3.1-6.1-7-6.1Z"
          stroke="currentColor"
          stroke-width="1.4"
          stroke-linejoin="round"
          fill="rgba(255,255,255,0.12)"
        />
        <circle cx="9.6" cy="9.8" r="1" fill="currentColor" />
        <circle cx="14.4" cy="9.8" r="1" fill="currentColor" />
        <path
          d="M9.8 13.2c.6.4 1.3.6 2.2.6s1.6-.2 2.2-.6"
          stroke="currentColor"
          stroke-width="1.2"
          stroke-linecap="round"
          fill="none"
        />
      </svg>
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
