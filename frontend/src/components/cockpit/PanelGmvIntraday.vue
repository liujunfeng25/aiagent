<template>
  <CockpitPanel title="今日成交额" title-en="TODAY GMV">
    <template #titleActions>
      <span
        class="gmv-live-pulse"
        :class="{ 'gmv-live-pulse--on': liveWsConnected }"
        title="绿色脉冲：正在通过实时通道读取今日成交；灰色：未连接"
        aria-hidden="true"
      />
    </template>
    <div class="gmv-intra">
      <div class="gmv-hero-kpi" v-if="heroData">
        <div class="gmv-hero-kpi__item">
          <span class="gmv-hero-kpi__value gmv-hero-kpi__value--gmv">{{ heroData.gmvDisplay }}</span>
          <span class="gmv-hero-kpi__label">今日 GMV</span>
        </div>
        <div class="gmv-hero-kpi__item">
          <span class="gmv-hero-kpi__value gmv-hero-kpi__value--orders">{{ heroData.orderCount }}</span>
          <span class="gmv-hero-kpi__label">今日订单</span>
        </div>
        <div class="gmv-hero-kpi__item">
          <span class="gmv-hero-kpi__value gmv-hero-kpi__value--ticket">{{ heroData.avgTicket }}</span>
          <span class="gmv-hero-kpi__label">客单价</span>
        </div>
      </div>
      <p class="gmv-intra__hint">
        <span
          class="gmv-intra__ws-pill"
          :class="{ 'gmv-intra__ws-pill--on': liveWsConnected }"
        >
          {{ liveWsConnected ? '实时通道·已连接' : '实时通道·未连接' }}
        </span>
        累计 GMV 阶梯线；点击<strong>数据点</strong>看该分钟订单。
        <button type="button" class="gmv-intra__hint-btn" @click="openLastBucketDetail">最近一分钟明细</button>
      </p>
      <div class="gmv-intra__main">
        <div ref="chartRef" class="gmv-intra__chart" />
        <aside class="gmv-intra__feed" aria-label="实时成交">
          <div class="gmv-intra__feed-head">
            <div class="gmv-intra__feed-title">实时成交</div>
            <div class="gmv-intra__feed-kpi">
              <span>近1分钟 {{ props.recentMinuteCount }} 笔</span>
              <strong>+¥{{ Number(props.recentMinuteAmount || 0).toLocaleString() }}</strong>
            </div>
          </div>
          <div
            v-if="parsedTickerLines.length"
            class="gmv-intra__ticker"
            aria-live="polite"
          >
            <div
              v-for="(line, i) in parsedTickerLines"
              :key="i"
              class="gmv-intra__tick"
              :class="{ 'gmv-intra__tick--flash': i === 0 }"
            >
              <span class="gmv-intra__tick-time">{{ line.time }}</span>
              <span class="gmv-intra__tick-amount">{{ line.amount }}</span>
            </div>
          </div>
          <p v-else class="gmv-intra__feed-empty">等待推送…</p>
        </aside>
      </div>
    </div>

    <el-dialog
      v-model="detailOpen"
      :title="detailTitle"
      width="min(960px, 96vw)"
      class="gmv-intra-dialog"
      append-to-body
      destroy-on-close
      @closed="onDetailClosed"
    >
      <div v-loading="detailLoading" class="gmv-intra-detail">
        <p v-if="detailMeta" class="gmv-intra-detail__meta">{{ detailMeta }}</p>
        <p class="gmv-intra-detail__hint">点击每行左侧箭头展开，查看该订单商品明细。</p>
        <el-table
          :key="detailTableKey"
          :data="detailRows"
          row-key="id"
          stripe
          size="small"
          max-height="440"
          empty-text="该分钟暂无订单"
          @expand-change="onOrderExpandChange"
        >
          <el-table-column type="expand" width="40">
            <template #default="{ row }">
              <div class="gmv-intra-detail__expand">
                <div v-if="lineState(row.id)?.loading" class="gmv-intra-detail__expand-loading">加载明细…</div>
                <p v-else-if="lineState(row.id)?.error" class="gmv-intra-detail__expand-err">{{ lineState(row.id).error }}</p>
                <template v-else>
                  <p v-if="lineState(row.id)?.warning" class="gmv-intra-detail__expand-warn">{{ lineState(row.id).warning }}</p>
                  <el-table
                    v-if="(lineState(row.id)?.rows || []).length"
                    :data="lineState(row.id).rows"
                    size="small"
                    border
                    class="gmv-intra-detail__lines"
                  >
                    <el-table-column prop="goods_name" label="商品" min-width="160" show-overflow-tooltip />
                    <el-table-column label="数量" width="90" align="right">
                      <template #default="{ row: line }">
                        {{ formatQty(line.qty) }}
                      </template>
                    </el-table-column>
                    <el-table-column label="小计" width="120" align="right">
                      <template #default="{ row: line }">
                        ¥{{ Number(line.line_amount).toLocaleString() }}
                      </template>
                    </el-table-column>
                  </el-table>
                  <p v-else-if="!lineState(row.id)?.warning" class="gmv-intra-detail__expand-empty">暂无商品行</p>
                </template>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="order_sn" label="订单号" min-width="120" show-overflow-tooltip />
          <el-table-column prop="id" label="内部ID" min-width="88" />
          <el-table-column label="下单时间" min-width="168">
            <template #default="{ row }">
              {{ formatRowTime(row.add_time) }}
            </template>
          </el-table-column>
          <el-table-column label="成交额" min-width="104">
            <template #default="{ row }">
              ¥{{ Number(row.total_amount).toLocaleString() }}
            </template>
          </el-table-column>
          <el-table-column prop="member_id" label="会员ID" min-width="88" />
          <el-table-column prop="member_realname" label="会员实名" min-width="100" show-overflow-tooltip />
          <el-table-column prop="member_login" label="会员账号" min-width="96" show-overflow-tooltip />
        </el-table>
      </div>
    </el-dialog>
  </CockpitPanel>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, shallowRef } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import CockpitPanel from './CockpitPanel.vue'
import { sxVar } from '../../utils/sxCss.js'
import { sxTooltip, sxAxisX, sxAxisY, sxGrid, sxGlow, sxAnimation } from '../../utils/echartTheme.js'

const props = defineProps({
  /** [minute_ts_sec, cumulative_gmv] */
  series: { type: Array, default: () => [] },
  tickerLines: { type: Array, default: () => [] },
  liveWsConnected: { type: Boolean, default: false },
  /** 与 API day_start_ts 一致（秒） */
  axisDayStartTs: { type: Number, default: 0 },
  /** 时间轴 max（秒），一般为 min(now, 当日末) */
  axisMaxTs: { type: Number, default: 0 },
  liveTodayPatch: { type: Object, default: null },
  recentMinuteAmount: { type: Number, default: 0 },
  recentMinuteCount: { type: Number, default: 0 },
})

function fmtMoney(n) {
  if (n == null || Number.isNaN(n)) return '--'
  return `¥${Number(n).toLocaleString()}`
}

const heroData = computed(() => {
  const p = props.liveTodayPatch
  if (!p) return null
  return {
    orderCount: p.order_count != null ? String(p.order_count) : '--',
    gmvDisplay: p.gmv != null ? fmtMoney(p.gmv) : '--',
    avgTicket: p.avg_ticket != null ? `¥${p.avg_ticket}` : '--',
  }
})
const parsedTickerLines = computed(() => props.tickerLines.map((line) => parseTickerLine(line)))

const chartRef = ref(null)
const chart = shallowRef(null)

const detailOpen = ref(false)
const detailLoading = ref(false)
const detailRows = ref([])
const detailTitle = ref('分时订单明细')
const detailMeta = ref('')
/** 切换分钟时变更，避免 el-table 复用展开状态 */
const detailTableKey = ref(0)
/** order id -> { loading?, fetched?, rows?, warning?, error? } */
const lineItemsById = ref({})

function formatRowTime(ts) {
  if (ts == null || ts === '') return '--'
  const n = Number(ts)
  if (Number.isNaN(n)) return String(ts)
  return new Date(n * 1000).toLocaleString('zh-CN', { hour12: false })
}

function formatQty(q) {
  if (q == null || q === '') return '--'
  const n = Number(q)
  if (Number.isNaN(n)) return String(q)
  if (Math.abs(n - Math.round(n)) < 1e-9) return String(Math.round(n))
  const r = Math.round(n * 10000) / 10000
  return String(r)
}

function lineState(oid) {
  if (oid == null) return null
  return lineItemsById.value[String(oid)] ?? null
}

async function ensureLineItems(orderId) {
  const k = String(orderId)
  const cur = lineItemsById.value[k]
  if (cur?.fetched) return
  if (cur?.loading) return
  lineItemsById.value = { ...lineItemsById.value, [k]: { loading: true, fetched: false } }
  try {
    const r = await fetch(
      `/api/insights/business/order-line-items?order_id=${encodeURIComponent(orderId)}`,
    )
    if (!r.ok) {
      throw new Error(await parseErrorResponse(r))
    }
    const d = await r.json()
    lineItemsById.value = {
      ...lineItemsById.value,
      [k]: {
        loading: false,
        fetched: true,
        rows: Array.isArray(d.rows) ? d.rows : [],
        warning: typeof d.warning === 'string' ? d.warning : '',
      },
    }
  } catch (e) {
    lineItemsById.value = {
      ...lineItemsById.value,
      [k]: {
        loading: false,
        fetched: true,
        rows: [],
        error: e?.message || '加载失败',
      },
    }
  }
}

function onOrderExpandChange(row, expandedRows) {
  const open = expandedRows.some((r) => r.id === row.id)
  if (open) void ensureLineItems(row.id)
}

function alignMinuteBucket(tsSec) {
  const t0 = props.axisDayStartTs
  if (!t0) return tsSec
  return t0 + Math.floor((tsSec - t0) / 60) * 60
}

async function parseErrorResponse(res) {
  const text = await res.text()
  try {
    const j = JSON.parse(text)
    const d = j.detail
    if (Array.isArray(d)) return d.map((x) => x.msg || String(x)).join('; ')
    if (typeof d === 'string') return d
    return j.message || text || `HTTP ${res.status}`
  } catch {
    return text || `HTTP ${res.status}`
  }
}

async function fetchMinuteOrders(minuteTs) {
  detailLoading.value = true
  detailRows.value = []
  detailMeta.value = ''
  lineItemsById.value = {}
  detailOpen.value = true
  try {
    const r = await fetch(
      `/api/insights/business/today-intraday-minute-orders?minute_start=${encodeURIComponent(minuteTs)}`,
    )
    if (!r.ok) {
      throw new Error(await parseErrorResponse(r))
    }
    const d = await r.json()
    detailRows.value = Array.isArray(d.orders) ? d.orders : []
    detailTableKey.value = d.minute_start || Date.now()
    const start = new Date(d.minute_start * 1000).toLocaleString('zh-CN', { hour12: false })
    const end = new Date((d.minute_end_exclusive - 1) * 1000).toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    })
    detailTitle.value = `分时明细 · ${start} 起 至 ${end}（该分钟内）`
    detailMeta.value = `共 ${d.total_count} 笔${d.truncated ? '（仅展示前 500 笔）' : ''}`
  } catch (e) {
    detailOpen.value = false
    ElMessage.error(e?.message || '加载订单明细失败')
  } finally {
    detailLoading.value = false
  }
}

function openLastBucketDetail() {
  const s = props.series
  if (!Array.isArray(s) || !s.length) {
    ElMessage.info('暂无分时数据，请稍后再试')
    return
  }
  void fetchMinuteOrders(s[s.length - 1][0])
}

function onChartClick(params) {
  if (params?.componentType !== 'series') return
  const val = params.value
  let tsSec = null
  let yVal = null
  if (Array.isArray(val) && val.length >= 1) {
    tsSec = Math.floor(Number(val[0]) / 1000)
    yVal = val.length >= 2 ? Number(val[1]) : null
  } else if (typeof params.dataIndex === 'number' && props.series?.[params.dataIndex]) {
    tsSec = props.series[params.dataIndex][0]
  }
  if (tsSec == null || Number.isNaN(tsSec)) return

  const t0 = props.axisDayStartTs
  const t1 = props.axisMaxTs
  if (t0 && tsSec === t0 && yVal === 0) {
    ElMessage.info('此为当日 0 点起点（累计 0），请点击黄色阶梯上的时刻查看该分钟订单')
    return
  }
  const lastRealTs = props.series?.length ? Number(props.series[props.series.length - 1][0]) : null
  if (t1 && lastRealTs != null && tsSec === t1 && t1 > lastRealTs) {
    ElMessage.info('此处为延伸至当前时刻的持平线，请点击左侧有台阶变化的时刻查看订单明细')
    return
  }

  void fetchMinuteOrders(alignMinuteBucket(tsSec))
}

function bindChartInteraction() {
  if (!chart.value) return
  chart.value.off('click')
  chart.value.on('click', onChartClick)
}

function onDetailClosed() {
  detailRows.value = []
  detailMeta.value = ''
  lineItemsById.value = {}
}

function pad2(n) {
  return n < 10 ? `0${n}` : `${n}`
}

function parseTickerLine(line) {
  const text = String(line || '').trim()
  const m = text.match(/^(\d{2}:\d{2}:\d{2})\s+(.*)$/)
  if (m) return { time: m[1], amount: m[2] || '--' }
  return { time: '--:--:--', amount: text || '--' }
}

/**
 * 阶梯图数据：左侧强制从当日 0 点累计 0 起，右侧延伸至 axisMax（持平）。
 * pairs: [unix_sec, cumulative]
 */
function buildStepSeriesData(pairs) {
  const raw = Array.isArray(pairs) ? [...pairs] : []
  let ordered = true
  for (let i = 1; i < raw.length; i += 1) {
    if (Number(raw[i][0]) < Number(raw[i - 1][0])) {
      ordered = false
      break
    }
  }
  if (!ordered) raw.sort((a, b) => Number(a[0]) - Number(b[0]))
  const t0 = props.axisDayStartTs
  const t1 = props.axisMaxTs
  const out = []

  if (t0 > 0) {
    out.push([t0 * 1000, 0])
  }
  for (const row of raw) {
    const t = Number(row[0])
    const v = Number(row[1])
    if (!Number.isFinite(t)) continue
    const ms = t * 1000
    const last = out[out.length - 1]
    if (last && last[0] === ms) {
      if (last[1] === 0 && v !== 0) {
        out.push([ms, v])
      } else {
        out[out.length - 1] = [ms, v]
      }
    } else {
      out.push([ms, v])
    }
  }

  if (t1 > 0 && t0 > 0 && out.length) {
    const endMs = t1 * 1000
    const last = out[out.length - 1]
    if (last[0] < endMs) {
      out.push([endMs, last[1]])
    }
  } else if (t0 > 0 && t1 > 0 && !raw.length) {
    out.push([t1 * 1000, 0])
  }

  return out
}

function buildOption(pairs) {
  const seriesData = buildStepSeriesData(pairs)
  const t0 = props.axisDayStartTs
  const t1 = props.axisMaxTs
  const xMin = t0 > 0 ? t0 * 1000 : undefined
  const xMax = t1 > 0 && t0 > 0 ? t1 * 1000 : undefined
  const lastPoint = seriesData.length ? seriesData[seriesData.length - 1] : null

  return {
    ...sxAnimation,
    animationDurationUpdate: 240,
    grid: sxGrid({ top: 22, bottom: 48, left: 56 }),
    tooltip: sxTooltip({
      formatter(params) {
        const p = params[0]
        const v = p.value
        const ms = Array.isArray(v) ? v[0] : p.axisValue
        const y = Array.isArray(v) ? v[1] : p.data
        const tlabel = ms != null
          ? new Date(ms).toLocaleString('zh-CN', { hour12: false })
          : ''
        return `${tlabel}<br/>累计 GMV: ¥${Number(y).toLocaleString()}<br/><span style="opacity:.85;font-size:11px">点击数据点查看该分钟订单</span>`
      },
    }),
    xAxis: {
      ...sxAxisX({
        axisLabel: {
          fontSize: 10,
          rotate: 22,
          hideOverlap: false,
          margin: 12,
          formatter: (v) => {
            const d = new Date(v)
            const hh = pad2(d.getHours())
            const mm = pad2(d.getMinutes())
            if (mm === '00') return hh === '00' ? `${hh}:${mm}` : `${hh}:00`
            return `${hh}:${mm}`
          },
        },
      }),
      type: 'time',
      min: xMin,
      max: xMax,
      boundaryGap: false,
      splitNumber: 12,
    },
    yAxis: {
      ...sxAxisY({
        axisLabel: { formatter: (v) => (v >= 1000 ? `${(v / 1000).toFixed(1)}k` : v) },
      }),
      type: 'value',
    },
    series: [{
      type: 'line',
      step: 'end',
      showSymbol: false,
      symbol: 'circle',
      symbolSize: 0,
      lineStyle: {
        color: '#fbbf24',
        width: 2.2,
        ...sxGlow('rgba(251,191,36,0.32)', 6),
      },
      itemStyle: {
        color: '#fbbf24',
        borderColor: sxVar('--sx-chart-line-point-border'),
        borderWidth: 1,
        shadowBlur: 0,
        shadowColor: 'transparent',
      },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(251, 191, 36, 0.45)' },
          { offset: 0.4, color: 'rgba(34, 211, 238, 0.10)' },
          { offset: 1, color: 'rgba(251, 191, 36, 0.02)' },
        ]),
      },
      data: seriesData,
      emphasis: {
        focus: 'series',
        itemStyle: { shadowBlur: 6, shadowColor: 'rgba(251,191,36,0.32)' },
      },
    }, {
      type: 'scatter',
      symbol: 'circle',
      symbolSize: 8,
      data: lastPoint ? [lastPoint] : [],
      silent: true,
      itemStyle: {
        color: '#fde047',
        shadowBlur: 10,
        shadowColor: 'rgba(251,191,36,0.48)',
      },
      z: 5,
      animationDuration: 180,
      animationDurationUpdate: 180,
    }],
  }
}

function init() {
  if (!chartRef.value) return
  chart.value = echarts.init(chartRef.value)
  chart.value.setOption(buildOption(props.series))
  bindChartInteraction()
}

let ro = null
onMounted(() => {
  init()
  if (typeof ResizeObserver !== 'undefined' && chartRef.value) {
    ro = new ResizeObserver(() => chart.value?.resize())
    ro.observe(chartRef.value)
  }
})
onUnmounted(() => {
  ro?.disconnect()
  chart.value?.dispose()
})

watch(
  () => [props.series, props.axisDayStartTs, props.axisMaxTs],
  () => {
    const opt = buildOption(props.series)
    chart.value?.setOption(
      {
        xAxis: { min: opt.xAxis.min, max: opt.xAxis.max },
        series: opt.series,
      },
      { notMerge: false, lazyUpdate: true },
    )
    bindChartInteraction()
  },
  { deep: true },
)
</script>

<style scoped>
.gmv-live-pulse {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: rgba(148, 163, 184, 0.65);
  box-shadow: 0 0 0 1px rgba(148, 163, 184, 0.35);
  vertical-align: middle;
}
.gmv-live-pulse--on {
  background: #4ade80;
  box-shadow: 0 0 0 0 rgba(74, 222, 128, 0.45);
  animation: gmv-live-pulse-ring 2.2s ease-out infinite;
}
@keyframes gmv-live-pulse-ring {
  0% {
    box-shadow:
      0 0 0 0 rgba(74, 222, 128, 0.5),
      0 0 0 0 rgba(250, 204, 21, 0.35);
  }
  60% {
    box-shadow:
      0 0 0 10px rgba(74, 222, 128, 0),
      0 0 0 4px rgba(250, 204, 21, 0.12);
  }
  100% {
    box-shadow:
      0 0 0 0 rgba(74, 222, 128, 0),
      0 0 0 0 rgba(250, 204, 21, 0);
  }
}

.gmv-hero-kpi {
  flex-shrink: 0;
  display: flex;
  justify-content: center;
  gap: clamp(24px, 5vw, 64px);
  padding: 10px 16px 6px;
}
.gmv-hero-kpi__item {
  text-align: center;
  min-width: 0;
}
.gmv-hero-kpi__value {
  display: block;
  font-size: clamp(22px, 3vw, 38px);
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  line-height: 1.1;
  letter-spacing: 0.02em;
}
.gmv-hero-kpi__value--gmv {
  color: #fbbf24;
  text-shadow: 0 0 18px rgba(251, 191, 36, 0.5), 0 0 40px rgba(251, 191, 36, 0.15);
}
.gmv-hero-kpi__value--orders {
  color: #22d3ee;
  text-shadow: 0 0 18px rgba(34, 211, 238, 0.5), 0 0 40px rgba(34, 211, 238, 0.15);
}
.gmv-hero-kpi__value--ticket {
  color: #38bdf8;
  text-shadow: 0 0 18px rgba(56, 189, 248, 0.45), 0 0 40px rgba(56, 189, 248, 0.12);
}
.gmv-hero-kpi__label {
  display: block;
  margin-top: 4px;
  font-size: 11px;
  letter-spacing: 0.12em;
  color: rgba(203, 213, 225, 0.78);
  text-transform: uppercase;
}

.gmv-intra {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  gap: 8px;
}
.gmv-intra__hint {
  flex-shrink: 0;
  margin: 0;
  font-size: 12px;
  color: rgba(226, 232, 240, 0.78);
  line-height: 1.6;
}
.gmv-intra__ws-pill {
  display: inline-block;
  margin-right: 8px;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 10px;
  letter-spacing: 0.06em;
  vertical-align: middle;
  background: rgba(71, 85, 105, 0.45);
  color: rgba(226, 232, 240, 0.85);
  border: 1px solid rgba(148, 163, 184, 0.35);
}
.gmv-intra__ws-pill--on {
  background: rgba(22, 163, 74, 0.25);
  border-color: rgba(74, 222, 128, 0.45);
  color: #bbf7d0;
}
.gmv-intra__hint-btn {
  padding: 0;
  border: none;
  background: none;
  color: #fbbf24;
  cursor: pointer;
  text-decoration: underline;
  font: inherit;
  margin-left: 4px;
}
.gmv-intra__hint-btn:hover {
  color: #fde047;
}
.gmv-intra__main {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: row;
  gap: 12px;
  align-items: stretch;
}
.gmv-intra__chart {
  flex: 1;
  min-width: 0;
  min-height: 200px;
  width: 100%;
  cursor: crosshair;
}
.gmv-intra__feed {
  flex: 0 0 clamp(250px, 31%, 360px);
  min-width: 250px;
  display: flex;
  flex-direction: column;
  min-height: 0;
  border-radius: 8px;
  border: 1px solid rgba(250, 204, 21, 0.18);
  background: rgba(15, 23, 42, 0.5);
  overflow: hidden;
}
.gmv-intra__feed-head {
  flex-shrink: 0;
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 12px 7px;
  border-bottom: 1px solid rgba(250, 204, 21, 0.12);
}
.gmv-intra__feed-title {
  flex-shrink: 0;
  font-size: 12px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: rgba(250, 204, 21, 0.75);
}
.gmv-intra__feed-kpi {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  font-size: 11px;
  color: rgba(226, 232, 240, 0.78);
}
.gmv-intra__feed-kpi strong {
  color: #fde68a;
  font-size: 13px;
  letter-spacing: 0.01em;
  text-shadow: 0 0 10px rgba(251, 191, 36, 0.22);
}
.gmv-intra__ticker {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 10px 12px;
  font-family: ui-monospace, monospace;
  font-size: 12px;
  line-height: 1.75;
  color: rgba(254, 240, 138, 0.92);
}
.gmv-intra__tick {
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: baseline;
  gap: 10px;
  letter-spacing: 0.01em;
}
.gmv-intra__tick-time {
  color: rgba(196, 210, 228, 0.9);
}
.gmv-intra__tick-amount {
  text-align: right;
  font-weight: 700;
  color: rgba(254, 240, 138, 0.96);
  text-shadow: 0 0 10px rgba(251, 191, 36, 0.22);
}
.gmv-intra__feed-empty {
  flex: 1;
  margin: 0;
  padding: 14px 12px;
  font-size: 13px;
  color: rgba(148, 163, 184, 0.75);
}
.gmv-intra__tick--flash {
  color: #fef08a;
  font-weight: 600;
}
.gmv-intra-detail__meta {
  margin: 0 0 10px;
  font-size: 12px;
  color: rgba(226, 232, 240, 0.88);
}
.gmv-intra-detail__hint {
  margin: 0 0 10px;
  font-size: 11px;
  color: rgba(148, 163, 184, 0.9);
  line-height: 1.4;
}
.gmv-intra-detail__expand {
  max-width: 880px;
  padding: 8px 12px 12px 28px;
  background: rgba(15, 23, 42, 0.45);
  border-radius: 6px;
  border: 1px solid rgba(250, 204, 21, 0.12);
}
.gmv-intra-detail__expand-loading,
.gmv-intra-detail__expand-empty {
  margin: 0;
  font-size: 12px;
  color: rgba(148, 163, 184, 0.9);
}
.gmv-intra-detail__expand-err {
  margin: 0;
  font-size: 12px;
  color: #f87171;
}
.gmv-intra-detail__expand-warn {
  margin: 0 0 8px;
  font-size: 12px;
  color: rgba(250, 204, 121, 0.95);
}
.gmv-intra-detail__lines {
  margin-top: 6px;
}

@media (max-width: 900px) {
  .gmv-intra__main {
    flex-direction: column;
  }
  .gmv-intra__feed {
    flex: 0 0 auto;
    max-height: 220px;
    min-width: 0;
  }
  .gmv-intra__chart {
    min-height: 220px;
  }
}
</style>

<style>
.gmv-intra-dialog.el-dialog {
  --el-dialog-bg-color: rgba(15, 23, 42, 0.97);
  --el-dialog-border-color: rgba(250, 204, 21, 0.28);
  background: rgba(15, 23, 42, 0.97);
  border: 1px solid rgba(250, 204, 21, 0.22);
}
.gmv-intra-dialog .el-dialog__title {
  color: #f8fafc;
}
.gmv-intra-dialog .el-dialog__headerbtn .el-dialog__close {
  color: #94a3b8;
}
.gmv-intra-dialog .el-table {
  --el-table-bg-color: rgba(15, 23, 42, 0.55);
  --el-table-row-hover-bg-color: rgba(251, 191, 36, 0.08);
  --el-table-tr-bg-color: rgba(15, 23, 42, 0.35);
  --el-table-header-bg-color: rgba(30, 41, 59, 0.95);
  --el-table-text-color: #e2e8f0;
  --el-table-border-color: rgba(51, 65, 85, 0.55);
}
</style>
