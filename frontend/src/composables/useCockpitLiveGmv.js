/**
 * 运营指挥台：今日 GMV 分时 REST + WebSocket 增量；关联图表 debounce 刷新。
 */
import { ref, watch, onUnmounted } from 'vue'

const API_BASE = '/api/insights/business'

function fmtClock(ts) {
  return new Date(ts * 1000).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

function avgTicket(gmv, oc) {
  const n = Number(oc) || 0
  if (!n) return 0
  return Math.round((Number(gmv) / n) * 100) / 100
}

/**
 * @param {import('vue').Ref<boolean>} enabledRef
 * @param {{ onChartsRefresh?: () => void, refreshDebounceMs?: number }} opts
 */
export function useCockpitLiveGmv(enabledRef, opts = {}) {
  const { onChartsRefresh, refreshDebounceMs = 8000 } = opts

  /** @type {import('vue').Ref<[number, number][]>} */
  const cumulativeSeries = ref([])
  /** @type {import('vue').Ref<{ order_count: number, gmv: number, avg_ticket: number } | null>} */
  const liveTodayPatch = ref(null)
  const wsConnected = ref(false)
  const tickerLines = ref([])
  /** @type {import('vue').Ref<{ id: number, add_time: number, amount: number, minute_start: number }[]>} 含订单 id，供点击拉详情 */
  const tickerFeedItems = ref([])
  /** 进入页面前当日的最近若干笔订单（与 batch 行字段一致），仅拉取一次 */
  const todayBackfillItems = ref([])
  const todayBackfillLoading = ref(false)
  let backfillLoaded = false
  let backfillInFlight = false
  /** 今日 0 点 UNIX 秒（与 today-intraday-gmv.day_start_ts 一致） */
  const gmvDayStartTs = ref(0)
  /** 时间轴右界：min(当前时刻, 当日 23:59:59) */
  const gmvAxisMaxTs = ref(0)

  let ws = null
  let reconnectAttempt = 0
  let reconnectTimer = null
  let refreshTimer = null
  let axisTimer = null
  const MAX_TICKER = 24
  const MAX_OPS_TICKER = 16
  /** @type {import('vue').Ref<string[]>} 运营台：WebSocket 推送的退货单增量提示 */
  const opsAlertReturnTicks = ref([])
  const rawBuckets = ref([])
  const recentMinuteAmount = ref(0)
  const recentMinuteCount = ref(0)
  const recent5mAmount = ref(0)
  const recent5mCount = ref(0)
  /** 成功 GET today-intraday-gmv 后的本地毫秒时间 */
  const lastIntradayFetchedAt = ref(null)
  /** 最近 WebSocket snapshot / batch（含汇总）到达时刻，毫秒 */
  const lastLivePushAt = ref(null)
  /** 服务端 JSON ping（保活）到达时刻，毫秒；用于数据新鲜度心电条 */
  const lastWsPingAt = ref(null)
  /** WebSocket onopen 时刻（毫秒），用于首包 ping 前估算「下次心跳」倒计时 */
  const wsOpenedAt = ref(null)
  /** 仅用于计算近 5 分钟指标的滚动队列 */
  let recentOrderQueue = []

  function recalcRecentStats(nowSec = Math.floor(Date.now() / 1000)) {
    const minTs = nowSec - 300
    recentOrderQueue = recentOrderQueue.filter((r) => r.ts >= minTs)
    recent5mCount.value = recentOrderQueue.length
    recent5mAmount.value = recentOrderQueue.reduce((s, r) => s + (Number(r.amount) || 0), 0)

    let latestMinute = 0
    for (const r of recentOrderQueue) {
      if (r.minuteStart > latestMinute) latestMinute = r.minuteStart
    }
    if (!latestMinute) {
      recentMinuteCount.value = 0
      recentMinuteAmount.value = 0
      return
    }
    let c = 0
    let amt = 0
    for (const r of recentOrderQueue) {
      if (r.minuteStart === latestMinute) {
        c += 1
        amt += Number(r.amount) || 0
      }
    }
    recentMinuteCount.value = c
    recentMinuteAmount.value = amt
  }

  function bumpAxisToNow() {
    const t0 = gmvDayStartTs.value
    if (!t0) return
    const endDay = t0 + 86400 - 1
    const now = Math.floor(Date.now() / 1000)
    gmvAxisMaxTs.value = Math.min(now, endDay)
    recalcRecentStats(now)
  }

  function applySnapshot(msg) {
    const oc = msg.order_count ?? 0
    const gmv = msg.cumulative_gmv ?? 0
    liveTodayPatch.value = {
      order_count: oc,
      gmv,
      avg_ticket: avgTicket(gmv, oc),
    }
    lastLivePushAt.value = Date.now()
    bumpAxisToNow()
  }

  function applyBatch(msg) {
    const oc = msg.order_count ?? 0
    const gmv = msg.cumulative_gmv ?? 0
    liveTodayPatch.value = {
      order_count: oc,
      gmv,
      avg_ticket: msg.avg_ticket != null ? msg.avg_ticket : avgTicket(gmv, oc),
    }
    lastLivePushAt.value = Date.now()
    bumpAxisToNow()
    const rows = msg.rows || []
    if (!rows.length) return
    const last = rows[rows.length - 1]
    const mk = last.minute_start
    const cum = gmv
    const arr = [...cumulativeSeries.value]
    const prev = arr[arr.length - 1]
    if (prev && prev[0] === mk) {
      arr[arr.length - 1] = [mk, cum]
    } else {
      arr.push([mk, cum])
    }
    cumulativeSeries.value = arr
    const rb = [...rawBuckets.value]
    for (const r of rows) {
      const rmk = r.minute_start
      const rAmt = Number(r.amount) || 0
      const existIdx = rb.findIndex((b) => b[0] === rmk)
      if (existIdx >= 0) {
        rb[existIdx] = [rmk, rb[existIdx][1] + rAmt]
      } else {
        rb.push([rmk, rAmt])
      }
    }
    rawBuckets.value = rb
    const lines = [...tickerLines.value]
    const feed = [...tickerFeedItems.value]
    for (let i = rows.length - 1; i >= 0; i -= 1) {
      const r = rows[i]
      lines.unshift(`${fmtClock(r.add_time)}  +¥${Number(r.amount).toLocaleString()}`)
      const oid = Number(r.id)
      feed.unshift({
        id: Number.isFinite(oid) ? oid : 0,
        add_time: Number(r.add_time) || 0,
        amount: Number(r.amount) || 0,
        minute_start: Number(r.minute_start) || 0,
      })
      recentOrderQueue.push({
        ts: Number(r.add_time) || Math.floor(Date.now() / 1000),
        minuteStart: Number(r.minute_start) || 0,
        amount: Number(r.amount) || 0,
      })
    }
    tickerLines.value = lines.slice(0, MAX_TICKER)
    tickerFeedItems.value = feed.filter((x) => x.id > 0).slice(0, MAX_TICKER)
    recalcRecentStats()
  }

  function applyOpsAlertBatch(msg) {
    const rows = msg.returns || []
    if (!rows.length) return
    lastLivePushAt.value = Date.now()
    const lines = [...opsAlertReturnTicks.value]
    for (let i = rows.length - 1; i >= 0; i -= 1) {
      const r = rows[i]
      const sn = r.backorder_sn || `#${r.id}`
      const amt = Number(r.total_amount) || 0
      lines.unshift(
        `${fmtClock(r.add_time)}  退货 ${sn}  +\u00a5${amt.toLocaleString()}`,
      )
    }
    opsAlertReturnTicks.value = lines.slice(0, MAX_OPS_TICKER)
  }

  async function loadTodayBackfill() {
    if (backfillLoaded || !enabledRef.value || backfillInFlight) return
    backfillInFlight = true
    todayBackfillLoading.value = true
    try {
      const beforeTs = Math.floor(Date.now() / 1000)
      const r = await fetch(
        `${API_BASE}/today-orders-backfill?before_ts=${encodeURIComponent(beforeTs)}`,
      )
      if (!r.ok) return
      const d = await r.json()
      if (!enabledRef.value) return
      const arr = Array.isArray(d.orders) ? d.orders : []
      todayBackfillItems.value = arr
        .map((row) => ({
          id: Number(row.id) || 0,
          add_time: Number(row.add_time) || 0,
          amount: Number(row.amount) || 0,
          minute_start: 0,
        }))
        .filter((x) => x.id > 0)
      backfillLoaded = true
    } catch {
      /* 静默 */
    } finally {
      backfillInFlight = false
      todayBackfillLoading.value = false
    }
  }

  async function loadIntraday() {
    try {
      const r = await fetch(`${API_BASE}/today-intraday-gmv`)
      if (!r.ok) return
      const d = await r.json()
      const t0 = Number(d.day_start_ts) || 0
      gmvDayStartTs.value = t0
      const qe = Number(d.query_end_ts)
      gmvAxisMaxTs.value = Number.isFinite(qe) && qe > 0 ? qe : t0
      bumpAxisToNow()
      const buckets = d.buckets || []
      rawBuckets.value = buckets.map((b) => [b.minute_start, Number(b.bucket_gmv) || 0])
      const lastBucket = buckets.length ? buckets[buckets.length - 1] : null
      recentMinuteAmount.value = Number(lastBucket?.bucket_gmv || 0)
      recentMinuteCount.value = 0
      recent5mAmount.value = 0
      recent5mCount.value = 0
      recentOrderQueue = []
      let cum = 0
      cumulativeSeries.value = buckets.map((b) => {
        cum += Number(b.bucket_gmv) || 0
        return [b.minute_start, cum]
      })
      lastIntradayFetchedAt.value = Date.now()
      void loadTodayBackfill()
    } catch {
      /* 静默，驾驶舱其它数据仍可用 */
    }
  }

  function scheduleChartsRefresh() {
    if (typeof onChartsRefresh !== 'function') return
    if (refreshTimer) clearTimeout(refreshTimer)
    refreshTimer = setTimeout(() => {
      refreshTimer = null
      try {
        onChartsRefresh()
      } catch {
        /* */
      }
    }, refreshDebounceMs)
  }

  function disconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (axisTimer) {
      clearInterval(axisTimer)
      axisTimer = null
    }
    if (refreshTimer) {
      clearTimeout(refreshTimer)
      refreshTimer = null
    }
    if (ws) {
      try {
        ws.close()
      } catch {
        /* */
      }
      ws = null
    }
    wsConnected.value = false
    lastWsPingAt.value = null
    wsOpenedAt.value = null
  }

  function connect() {
    if (ws) return
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const u = `${proto}//${window.location.host}/api/insights/business/ws/live-gmv`
    try {
      ws = new WebSocket(u)
    } catch {
      return
    }
    ws.onopen = () => {
      wsConnected.value = true
      wsOpenedAt.value = Date.now()
      reconnectAttempt = 0
      if (import.meta.env.DEV) {
        console.info('[live-gmv] WebSocket 已连接', u)
      }
    }
    ws.onclose = (ev) => {
      wsConnected.value = false
      lastWsPingAt.value = null
      wsOpenedAt.value = null
      ws = null
      if (import.meta.env.DEV && enabledRef.value) {
        console.warn('[live-gmv] WebSocket 已断开', ev.code, ev.reason || '')
      }
      if (!enabledRef.value) return
      reconnectAttempt += 1
      const delay = Math.min(30000, 1000 * 2 ** Math.min(reconnectAttempt, 5))
      reconnectTimer = setTimeout(async () => {
        reconnectTimer = null
        if (!enabledRef.value) return
        await loadIntraday()
        connect()
      }, delay)
    }
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data)
        if (msg.type === 'ping') {
          lastWsPingAt.value = Date.now()
          return
        }
        if (msg.type === 'snapshot') applySnapshot(msg)
        if (msg.type === 'batch') {
          applyBatch(msg)
          scheduleChartsRefresh()
        }
        if (msg.type === 'ops_alert_batch') applyOpsAlertBatch(msg)
        if (msg.type === 'refresh_hint') scheduleChartsRefresh()
      } catch {
        /* */
      }
    }
    ws.onerror = () => {
      if (import.meta.env.DEV) {
        console.warn('[live-gmv] WebSocket 连接异常，请检查 Network → WS 是否在刷新后出现', u)
      }
    }
  }

  watch(
    enabledRef,
    (v) => {
      if (v) {
        void loadIntraday().then(() => connect())
        if (axisTimer) clearInterval(axisTimer)
        axisTimer = setInterval(bumpAxisToNow, 30000)
      } else {
        disconnect()
        liveTodayPatch.value = null
        tickerLines.value = []
        tickerFeedItems.value = []
        todayBackfillItems.value = []
        todayBackfillLoading.value = false
        backfillLoaded = false
        backfillInFlight = false
        opsAlertReturnTicks.value = []
        gmvDayStartTs.value = 0
        gmvAxisMaxTs.value = 0
        lastIntradayFetchedAt.value = null
        lastLivePushAt.value = null
        lastWsPingAt.value = null
        wsOpenedAt.value = null
        recentMinuteAmount.value = 0
        recentMinuteCount.value = 0
        recent5mAmount.value = 0
        recent5mCount.value = 0
        recentOrderQueue = []
      }
    },
    { immediate: true },
  )

  /**
   * 多 Uvicorn worker 时 WS 可能连到落后进程的内存 Hub；HTTP kpi-summary 走库更准。
   * 在实时通道仍显示「已连接」、且今日单量与库表一致时，若 GMV 偏差 > 0.5 则用库表校正顶栏三指标。
   */
  function reconcileHeroFromHttpIfDrift(httpGmv, httpOrderCount) {
    if (!enabledRef.value || !wsConnected.value) return false
    const live = liveTodayPatch.value
    if (!live) return false
    const ho = Number(httpOrderCount)
    const hg = Number(httpGmv)
    if (!Number.isFinite(ho) || !Number.isFinite(hg)) return false
    const lo = Number(live.order_count)
    const lg = Number(live.gmv)
    if (!Number.isFinite(lo) || !Number.isFinite(lg)) return false
    if (Math.round(lo) !== Math.round(ho)) return false
    if (Math.abs(lg - hg) <= 0.5) return false
    liveTodayPatch.value = {
      order_count: ho,
      gmv: hg,
      avg_ticket: avgTicket(hg, ho),
    }
    return true
  }

  onUnmounted(() => disconnect())

  return {
    cumulativeSeries,
    liveTodayPatch,
    wsConnected,
    tickerLines,
    tickerFeedItems,
    todayBackfillItems,
    todayBackfillLoading,
    gmvDayStartTs,
    gmvAxisMaxTs,
    rawBuckets,
    recentMinuteAmount,
    recentMinuteCount,
    recent5mAmount,
    recent5mCount,
    lastIntradayFetchedAt,
    lastLivePushAt,
    lastWsPingAt,
    wsOpenedAt,
    loadIntraday,
    opsAlertReturnTicks,
    reconcileHeroFromHttpIfDrift,
  }
}
