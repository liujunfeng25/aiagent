<template>
  <CockpitPanel title="数据新鲜度" title-en="LIVE STATUS">
    <div class="fresh-wrap">
      <div class="fresh-block fresh-block--channel">
        <span class="fresh-label">实时通道</span>
        <div class="fresh-channel-line">
          <div class="fresh-channel-left">
            <span
              class="fresh-pill"
              :class="props.liveWsConnected ? 'fresh-pill--on' : 'fresh-pill--off'"
            >
              {{ props.liveWsConnected ? '已连接' : '未连接' }}
            </span>
            <span class="fresh-pill-note">WebSocket /live-gmv</span>
            <span
              v-if="props.liveWsConnected"
              class="fresh-channel-ping"
              aria-live="polite"
            >{{ pingCountdownInline }}</span>
          </div>
          <div
            class="fresh-ecg"
            :class="{
              'fresh-ecg--live': props.liveWsConnected,
              'fresh-ecg--beat': beatFlash,
            }"
            role="img"
            aria-label="实时通道心跳波形"
          >
            <div class="fresh-ecg__glass" aria-hidden="true">
              <!-- 能量条式电磁扫光 + 中心过曝（随 ping 触发一次） -->
              <div class="fresh-ecg__emp-bloom" />
              <div class="fresh-ecg__emp-beam" />
              <svg
                class="fresh-ecg__svg"
                viewBox="0 0 80 36"
                preserveAspectRatio="none"
              >
                <defs>
                  <linearGradient id="freshEcgGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stop-color="rgba(34, 211, 238, 0.35)" />
                    <stop offset="45%" stop-color="rgba(103, 232, 249, 0.85)" />
                    <stop offset="100%" stop-color="rgba(234, 179, 8, 0.45)" />
                  </linearGradient>
                  <filter id="freshEcgGlow" x="-20%" y="-20%" width="140%" height="140%">
                    <feGaussianBlur stdDeviation="0.8" result="b" />
                    <feMerge>
                      <feMergeNode in="b" />
                      <feMergeNode in="SourceGraphic" />
                    </feMerge>
                  </filter>
                </defs>
                <!-- 已连接：单周期路径复制三份 + SVG 坐标平移实现无缝滚动 -->
                <g v-if="props.liveWsConnected" class="fresh-ecg__scroll">
                  <g>
                    <animateTransform
                      attributeName="transform"
                      type="translate"
                      from="0 0"
                      to="-80 0"
                      dur="10s"
                      repeatCount="indefinite"
                    />
                    <path
                      class="fresh-ecg__wave"
                      fill="none"
                      stroke="url(#freshEcgGrad)"
                      stroke-width="1.35"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      vector-effect="non-scaling-stroke"
                      filter="url(#freshEcgGlow)"
                      d="M0,18 L8,18 L10,18 L12,7 L14,18 L20,18 L28,18 L30,9 L32,18 L40,18 L48,18 L50,13 L52,23 L54,18 L80,18"
                    />
                    <path
                      class="fresh-ecg__wave"
                      fill="none"
                      stroke="url(#freshEcgGrad)"
                      stroke-width="1.35"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      vector-effect="non-scaling-stroke"
                      filter="url(#freshEcgGlow)"
                      transform="translate(80,0)"
                      d="M0,18 L8,18 L10,18 L12,7 L14,18 L20,18 L28,18 L30,9 L32,18 L40,18 L48,18 L50,13 L52,23 L54,18 L80,18"
                    />
                    <path
                      class="fresh-ecg__wave"
                      fill="none"
                      stroke="url(#freshEcgGrad)"
                      stroke-width="1.35"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      vector-effect="non-scaling-stroke"
                      filter="url(#freshEcgGlow)"
                      transform="translate(160,0)"
                      d="M0,18 L8,18 L10,18 L12,7 L14,18 L20,18 L28,18 L30,9 L32,18 L40,18 L48,18 L50,13 L52,23 L54,18 L80,18"
                    />
                  </g>
                </g>
                <path
                  v-else
                  class="fresh-ecg__flat"
                  fill="none"
                  stroke="rgba(148, 163, 184, 0.45)"
                  stroke-width="1.2"
                  vector-effect="non-scaling-stroke"
                  d="M0,18 L80,18"
                />
              </svg>
            </div>
          </div>
        </div>
      </div>
      <div class="fresh-metrics">
        <div class="fresh-metric fresh-metric--pulse-row">
          <span class="fresh-metric__label">通道心跳</span>
          <strong class="fresh-metric__value fresh-metric__value--pulse" :class="pingCountdownClass">{{ pingCountdownText }}</strong>
          <span class="fresh-metric__hint">距下次 JSON 保活 ping（约 60s 周期）</span>
        </div>
        <div class="fresh-metric">
          <span class="fresh-metric__label">推送延迟</span>
          <strong class="fresh-metric__value" :class="latencyClass(pushLatencySec)">{{ fmtLatency(pushLatencySec) }}</strong>
        </div>
        <div class="fresh-metric">
          <span class="fresh-metric__label">拉取延迟</span>
          <strong class="fresh-metric__value" :class="latencyClass(fetchLatencySec)">{{ fmtLatency(fetchLatencySec) }}</strong>
        </div>
        <div class="fresh-metric">
          <span class="fresh-metric__label">近5分钟笔数</span>
          <strong class="fresh-metric__value">{{ Number(props.recent5mCount || 0).toLocaleString() }}</strong>
        </div>
        <div class="fresh-metric">
          <span class="fresh-metric__label">近5分钟金额</span>
          <strong class="fresh-metric__value">¥{{ Number(props.recent5mAmount || 0).toLocaleString() }}</strong>
        </div>
      </div>
      <div class="fresh-row fresh-row--current">
        <span class="fresh-label">当前分钟成交</span>
        <span class="fresh-value">+¥{{ Number(props.recentMinuteAmount || 0).toLocaleString() }}</span>
        <span class="fresh-sub">{{ Number(props.recentMinuteCount || 0).toLocaleString() }} 笔（实时流累计）</span>
      </div>
      <div class="fresh-row fresh-row--block">
        <span class="fresh-label">分时阶梯图</span>
        <span class="fresh-value">{{ fmtTs(props.lastIntradayFetchedAt) }}</span>
        <span class="fresh-sub">自业务库 REST 同步（today-intraday-gmv）</span>
      </div>
      <div class="fresh-row fresh-row--block">
        <span class="fresh-label">汇总与成交推送</span>
        <span class="fresh-value">{{ fmtTs(props.lastLivePushAt) }}</span>
        <span class="fresh-sub">最近一笔 WebSocket snapshot / batch 到达本页时刻</span>
      </div>
      <p class="fresh-footnote">时间为本机浏览器当前时区，与页眉时钟一致。收到 JSON ping 时波形触发电磁脉冲；倒计时为距下次服务端保活的大致时间。</p>
    </div>
  </CockpitPanel>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import CockpitPanel from './CockpitPanel.vue'

const props = defineProps({
  liveWsConnected: { type: Boolean, default: false },
  lastIntradayFetchedAt: { type: Number, default: null },
  lastLivePushAt: { type: Number, default: null },
  /** 服务端 JSON ping 到达时刻（毫秒） */
  lastWsPingAt: { type: Number, default: null },
  /** WebSocket 连接建立时刻（毫秒），用于首次 ping 前倒计时 */
  wsOpenedAt: { type: Number, default: null },
  recentMinuteAmount: { type: Number, default: 0 },
  recentMinuteCount: { type: Number, default: 0 },
  recent5mAmount: { type: Number, default: 0 },
  recent5mCount: { type: Number, default: 0 },
})

/** 与后端 live_gmv_poller.handle 中 receive_text 超时一致 */
const WS_PING_INTERVAL_MS = 60000

const beatFlash = ref(false)
let beatTimer = null

watch(
  () => props.lastWsPingAt,
  (v) => {
    if (v == null || !props.liveWsConnected) return
    beatFlash.value = true
    if (beatTimer) clearTimeout(beatTimer)
    beatTimer = setTimeout(() => {
      beatFlash.value = false
      beatTimer = null
    }, 1380)
  },
)

onUnmounted(() => {
  if (beatTimer) clearTimeout(beatTimer)
})

const nowMs = ref(Date.now())
let timer = null
onMounted(() => {
  timer = setInterval(() => {
    nowMs.value = Date.now()
  }, 500)
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
})

function fmtTs(ms) {
  if (ms == null || !Number.isFinite(ms)) return '—'
  return new Date(ms).toLocaleString('zh-CN', { hour12: false })
}

const pushLatencySec = computed(() => {
  if (!Number.isFinite(props.lastLivePushAt)) return null
  return Math.max(0, Math.floor((nowMs.value - props.lastLivePushAt) / 1000))
})
const fetchLatencySec = computed(() => {
  if (!Number.isFinite(props.lastIntradayFetchedAt)) return null
  return Math.max(0, Math.floor((nowMs.value - props.lastIntradayFetchedAt) / 1000))
})

function pingBaseMs() {
  const ping = Number(props.lastWsPingAt)
  const opened = Number(props.wsOpenedAt)
  if (Number.isFinite(ping)) return ping
  if (Number.isFinite(opened)) return opened
  return null
}

const pingCountdownSec = computed(() => {
  if (!props.liveWsConnected) return null
  const base = pingBaseMs()
  if (base == null) return null
  const next = base + WS_PING_INTERVAL_MS
  return Math.max(0, Math.ceil((next - nowMs.value) / 1000))
})

const pingCountdownText = computed(() => {
  const v = pingCountdownSec.value
  if (v == null) return '—'
  if (v <= 0) return '即将'
  return `${v}s`
})

/** 实时通道行内展示，避免 KPI 格子裁切时仍能看到 */
const pingCountdownInline = computed(() => {
  const v = pingCountdownSec.value
  if (v == null) return '心跳 —'
  if (v <= 0) return '心跳 即将'
  return `下次 ${v}s`
})

const pingCountdownClass = computed(() => {
  const v = pingCountdownSec.value
  if (v == null) return 'is-muted'
  if (v <= 5) return 'is-pulse-urgent'
  if (v <= 15) return 'is-warn'
  return 'is-good'
})

function fmtLatency(v) {
  if (!Number.isFinite(v)) return '—'
  if (v < 60) return `${v}s`
  const min = Math.floor(v / 60)
  const sec = v % 60
  return `${min}m ${sec}s`
}

function latencyClass(v) {
  if (!Number.isFinite(v)) return 'is-muted'
  if (v <= 10) return 'is-good'
  if (v <= 60) return 'is-warn'
  return 'is-bad'
}
</script>

<style scoped>
.fresh-wrap {
  flex: 1;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  gap: 12px;
  padding: 4px 2px 8px;
}

.fresh-block--channel {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
  width: 100%;
}

.fresh-channel-line {
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-height: 34px;
}

.fresh-channel-left {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

/* 心电图：与驾驶舱玻璃 + 电青金点缀一致 */
.fresh-ecg {
  flex: 1;
  min-width: 80px;
  height: 34px;
  border-radius: 8px;
  overflow: hidden;
  transition: box-shadow 0.45s ease, transform 0.5s ease;
}

.fresh-ecg__glass {
  position: relative;
  height: 100%;
  border-radius: 8px;
  border: 1px solid rgba(103, 232, 249, 0.22);
  background:
    linear-gradient(
      165deg,
      rgba(10, 15, 35, 0.55) 0%,
      rgba(8, 47, 73, 0.18) 100%
    );
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.06),
    0 0 16px rgba(34, 211, 238, 0.06);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.fresh-ecg__emp-bloom,
.fresh-ecg__emp-beam {
  position: absolute;
  inset: 0;
  pointer-events: none;
  border-radius: inherit;
  z-index: 0;
}

.fresh-ecg__emp-bloom {
  opacity: 0;
  background: radial-gradient(
    ellipse 90% 140% at 50% 50%,
    rgba(103, 232, 249, 0.5) 0%,
    rgba(34, 211, 238, 0.15) 35%,
    transparent 70%
  );
  mix-blend-mode: screen;
}

.fresh-ecg__emp-beam {
  opacity: 0;
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(34, 211, 238, 0) 36%,
    rgba(34, 211, 238, 0.65) 44%,
    rgba(250, 204, 21, 0.95) 50%,
    rgba(103, 232, 249, 0.85) 56%,
    rgba(34, 211, 238, 0) 64%,
    transparent 100%
  );
  background-size: 52% 100%;
  background-repeat: no-repeat;
  background-position: -25% 50%;
  mix-blend-mode: screen;
  filter: blur(0.6px);
}

.fresh-ecg--beat .fresh-ecg__emp-bloom {
  animation: fresh-ecg-bloom 1.15s ease-in-out forwards;
}

.fresh-ecg--beat .fresh-ecg__emp-beam {
  animation: fresh-ecg-beam 1.35s ease-in-out forwards;
}

@keyframes fresh-ecg-bloom {
  0% {
    opacity: 0;
    transform: scale(0.35);
  }
  40% {
    opacity: 1;
    transform: scale(1.12);
  }
  100% {
    opacity: 0;
    transform: scale(1.45);
  }
}

@keyframes fresh-ecg-beam {
  0% {
    opacity: 0;
    background-position: -35% 50%;
  }
  18% {
    opacity: 1;
  }
  100% {
    opacity: 0.12;
    background-position: 140% 50%;
  }
}

.fresh-ecg--live .fresh-ecg__glass {
  border-color: rgba(74, 222, 128, 0.22);
}

.fresh-ecg__svg {
  position: relative;
  z-index: 1;
  display: block;
  width: 100%;
  height: 100%;
}

.fresh-ecg--beat .fresh-ecg__glass {
  border-color: rgba(103, 232, 249, 0.65);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.14),
    0 0 28px rgba(34, 211, 238, 0.55),
    0 0 44px rgba(250, 204, 21, 0.22),
    0 0 2px 1px rgba(103, 232, 249, 0.4);
  transform: scaleY(1.06);
}

.fresh-ecg--beat .fresh-ecg__wave {
  stroke-width: 2.1;
}

.fresh-pill-note {
  font-size: 10px;
  color: rgba(148, 163, 184, 0.75);
  letter-spacing: 0.02em;
}

.fresh-channel-ping {
  flex-shrink: 0;
  font-family: ui-monospace, 'SF Mono', Menlo, monospace;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: rgba(186, 230, 253, 0.95);
  text-shadow: 0 0 10px rgba(34, 211, 238, 0.35);
  padding: 2px 8px;
  border-radius: 6px;
  border: 1px solid rgba(103, 232, 249, 0.28);
  background: rgba(8, 47, 73, 0.35);
}

.fresh-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.fresh-row--block {
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
}

.fresh-row--current {
  flex-direction: column;
  align-items: flex-start;
  gap: 3px;
}

.fresh-label {
  font-size: 11px;
  letter-spacing: 0.12em;
  color: rgba(125, 211, 252, 0.65);
  text-transform: uppercase;
}

.fresh-pill {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  border: 1px solid rgba(148, 163, 184, 0.4);
  background: rgba(51, 65, 85, 0.35);
  color: rgba(226, 232, 240, 0.85);
}

.fresh-pill--on {
  border-color: rgba(74, 222, 128, 0.5);
  background: rgba(22, 163, 74, 0.22);
  color: #bbf7d0;
  box-shadow: 0 0 12px rgba(74, 222, 128, 0.12);
}

.fresh-pill--off {
  border-color: rgba(248, 113, 113, 0.35);
  color: #fecaca;
}

.fresh-value {
  font-family: ui-monospace, 'SF Mono', Menlo, monospace;
  font-size: clamp(14px, 1.6vw, 17px);
  font-weight: 700;
  color: #fef08a;
  text-shadow: 0 0 12px rgba(250, 204, 21, 0.22);
}

.fresh-sub {
  font-size: 10px;
  line-height: 1.35;
  color: rgba(148, 163, 184, 0.88);
  max-width: 420px;
}

.fresh-metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.fresh-metric--pulse-row {
  grid-column: 1 / -1;
  border-color: rgba(103, 232, 249, 0.22);
  background: linear-gradient(
    165deg,
    rgba(15, 23, 42, 0.5) 0%,
    rgba(8, 47, 73, 0.22) 100%
  );
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.fresh-metric__hint {
  font-size: 9px;
  letter-spacing: 0.03em;
  color: rgba(148, 163, 184, 0.82);
}

.fresh-metric__value--pulse {
  font-size: 15px;
  letter-spacing: 0.06em;
}

.fresh-metric {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 10px;
  border-radius: 6px;
  border: 1px solid rgba(56, 189, 248, 0.14);
  background: rgba(15, 23, 42, 0.35);
}

.fresh-metric__label {
  font-size: 10px;
  letter-spacing: 0.04em;
  color: rgba(148, 163, 184, 0.9);
}

.fresh-metric__value {
  font-family: ui-monospace, 'SF Mono', Menlo, monospace;
  font-size: 14px;
  color: rgba(226, 232, 240, 0.95);
}

.fresh-metric__value.is-good { color: #86efac; }
.fresh-metric__value.is-warn { color: #fde68a; }
.fresh-metric__value.is-bad { color: #fca5a5; }
.fresh-metric__value.is-muted { color: rgba(148, 163, 184, 0.9); }
.fresh-metric__value.is-pulse-urgent {
  color: #fef08a;
  text-shadow:
    0 0 12px rgba(250, 204, 21, 0.45),
    0 0 22px rgba(34, 211, 238, 0.25);
}

.fresh-footnote {
  margin: 4px 0 0;
  font-size: 9px;
  color: rgba(100, 116, 139, 0.95);
  letter-spacing: 0.04em;
}
</style>
