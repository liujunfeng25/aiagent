<template>
  <CockpitPanel title="数据新鲜度" title-en="LIVE STATUS">
    <div class="fresh-wrap">
      <div class="fresh-block fresh-block--channel">
        <span class="fresh-label">实时通道</span>
        <div class="fresh-channel-line">
          <span
            class="fresh-pill"
            :class="liveWsConnected ? 'fresh-pill--on' : 'fresh-pill--off'"
          >
            {{ liveWsConnected ? '已连接' : '未连接' }}
          </span>
          <span class="fresh-pill-note">WebSocket /live-gmv</span>
        </div>
      </div>
      <div class="fresh-row fresh-row--block">
        <span class="fresh-label">分时阶梯图</span>
        <span class="fresh-value">{{ fmtTs(lastIntradayFetchedAt) }}</span>
        <span class="fresh-sub">自业务库 REST 同步（today-intraday-gmv）</span>
      </div>
      <div class="fresh-row fresh-row--block">
        <span class="fresh-label">汇总与成交推送</span>
        <span class="fresh-value">{{ fmtTs(lastLivePushAt) }}</span>
        <span class="fresh-sub">最近一笔 WebSocket snapshot / batch 到达本页时刻</span>
      </div>
      <p class="fresh-footnote">时间为本机浏览器当前时区，与页眉时钟一致。</p>
    </div>
  </CockpitPanel>
</template>

<script setup>
import CockpitPanel from './CockpitPanel.vue'

defineProps({
  liveWsConnected: { type: Boolean, default: false },
  /** 成功拉取 today-intraday-gmv 的毫秒时间戳 */
  lastIntradayFetchedAt: { type: Number, default: null },
  /** 最近 snapshot/batch 更新毫秒时间戳 */
  lastLivePushAt: { type: Number, default: null },
})

function fmtTs(ms) {
  if (ms == null || !Number.isFinite(ms)) return '—'
  return new Date(ms).toLocaleString('zh-CN', { hour12: false })
}
</script>

<style scoped>
.fresh-wrap {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  gap: 14px;
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
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  width: 100%;
}

.fresh-pill-note {
  font-size: 10px;
  color: rgba(148, 163, 184, 0.75);
  letter-spacing: 0.02em;
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

.fresh-footnote {
  margin: 4px 0 0;
  font-size: 9px;
  color: rgba(100, 116, 139, 0.95);
  letter-spacing: 0.04em;
}
</style>
