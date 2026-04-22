<template>
  <div class="sx-asst-card">
    <div class="sx-asst-card__header">
      <div class="sx-asst-card__title">
        <span class="sx-asst-card__title__icon" aria-hidden="true">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
            <path
              d="M7 3h7l5 5v13a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z"
              stroke="currentColor"
              stroke-width="2"
              stroke-linejoin="round"
            />
            <path d="M13 3v6h6" stroke="currentColor" stroke-width="2" stroke-linejoin="round" />
          </svg>
        </span>
        {{ title }}
      </div>

      <div class="sx-asst-card__export">
        <button
          v-for="f in FORMATS"
          :key="f.value"
          type="button"
          class="sx-asst-card__dl"
          :class="{ 'is-busy': downloading === f.value }"
          :disabled="!!downloading"
          :title="f.title"
          @click="onDownload(f.value)"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
            <path d="M12 4v12m0 0 4-4m-4 4-4-4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
            <path d="M4 20h16" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
          </svg>
          {{ downloading === f.value ? '生成中…' : f.label }}
        </button>
      </div>
    </div>
    <div class="sx-asst-report-body" v-html="htmlContent" />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import MarkdownIt from 'markdown-it'

const props = defineProps({
  title: { type: String, default: '业务报告' },
  markdown: { type: String, default: '' },
  formats: { type: Array, default: () => ['docx'] },
  onExport: { type: Function, default: null },
})

const FORMAT_DICT = [
  { value: 'docx', label: 'Word', title: '下载 Word (.docx)，适合发邮件 / 打印' },
  { value: 'pptx', label: 'PPT', title: '下载 PowerPoint (.pptx)，适合汇报展示' },
  { value: 'md', label: 'Markdown', title: '下载 Markdown (.md)，适合二次编辑' },
]
const FORMATS = computed(() => {
  const allowed = Array.isArray(props.formats) && props.formats.length ? props.formats : ['docx']
  const set = new Set(allowed)
  return FORMAT_DICT.filter((x) => set.has(x.value))
})

const md = new MarkdownIt({ html: false, linkify: true, breaks: true })

const htmlContent = computed(() => {
  try {
    return md.render(props.markdown || '')
  } catch (_) {
    return `<pre>${(props.markdown || '').replace(/[<>&]/g, (c) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' }[c]))}</pre>`
  }
})

const downloading = ref('')

async function onDownload(format) {
  if (!props.onExport || downloading.value) return
  downloading.value = format
  try {
    await props.onExport({ title: props.title, markdown: props.markdown, format })
  } finally {
    downloading.value = ''
  }
}
</script>

<style scoped>
.sx-asst-card__export {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.sx-asst-card__dl.is-busy {
  opacity: 0.7;
}
</style>
