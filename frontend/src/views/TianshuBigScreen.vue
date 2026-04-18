<template>
  <div class="tianshu-shell">
    <iframe
      :src="iframeSrc"
      class="tianshu-iframe"
      title="天枢大屏"
      referrerpolicy="same-origin"
      allowfullscreen
    />
    <p v-if="showEmbedHint" class="tianshu-hint">
      开发模式：iframe 指向独立 dev 服务。生产构建请执行
      <code>aiagent/scripts/sync-beijing-tianshu.sh</code>
      ，将子应用产物写入 <code>public/tianshu</code> 后随主站一并打包。
    </p>
  </div>
</template>

<script setup>
import { computed } from 'vue'

/** 开发：在 .env.development.local 设置 VITE_TIANSHU_URL=http://127.0.0.1:5174/ （beijing 项目 npm run dev -- --port 5174） */
const devUrl = import.meta.env.VITE_TIANSHU_URL

const iframeSrc = computed(() => {
  const u = devUrl != null ? String(devUrl).trim() : ''
  if (u) {
    const base = u.endsWith('/') ? u.slice(0, -1) : u
    return `${base}/`
  }
  return '/tianshu/index.html'
})

const showEmbedHint = computed(() => Boolean(import.meta.env.DEV && devUrl))
</script>

<style scoped>
.tianshu-shell {
  position: relative;
  width: 100%;
  min-height: calc(100vh - 60px);
  height: calc(100vh - 60px);
  margin: 0;
  padding: 0;
  overflow: hidden;
  background: var(--sx-bg-deep, #0a0e14);
}

.tianshu-iframe {
  display: block;
  width: 100%;
  height: 100%;
  border: 0;
}

.tianshu-hint {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  margin: 0;
  padding: 8px 12px;
  font-size: 12px;
  color: var(--sx-text-readable-muted, #94a3b8);
  background: rgba(10, 14, 20, 0.85);
  border-top: 1px solid var(--sx-edge-cyan-soft, rgba(103, 232, 249, 0.2));
}

.tianshu-hint code {
  font-size: 11px;
  color: var(--sx-cyan-bright, #67e8f9);
}
</style>
