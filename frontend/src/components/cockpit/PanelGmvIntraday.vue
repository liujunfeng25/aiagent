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
          <span
            class="gmv-hero-kpi__value gmv-hero-kpi__value--gmv"
            :class="{ 'gmv-hero-kpi__value--bump': kpiBump }"
          >{{ displayGmv }}</span>
          <span class="gmv-hero-kpi__label">今日 GMV</span>
        </div>
        <div class="gmv-hero-kpi__item">
          <span
            class="gmv-hero-kpi__value gmv-hero-kpi__value--orders"
            :class="{ 'gmv-hero-kpi__value--bump': kpiBump }"
          >{{ displayOrders }}</span>
          <span class="gmv-hero-kpi__label">今日订单</span>
        </div>
        <div class="gmv-hero-kpi__item">
          <span
            class="gmv-hero-kpi__value gmv-hero-kpi__value--ticket"
            :class="{ 'gmv-hero-kpi__value--bump': kpiBump }"
          >{{ displayAvg }}</span>
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
        累计 GMV 阶梯线。查看分钟订单可使用「最近一分钟明细」。
        <button type="button" class="gmv-intra__hint-btn" @click="openLastBucketDetail">最近一分钟明细</button>
      </p>
      <div class="gmv-intra__main">
        <div ref="chartRef" class="gmv-intra__chart" />
        <aside class="gmv-intra__feed" aria-label="实时成交与补退预警">
          <div class="gmv-intra__feed-tabs" role="tablist">
            <button
              type="button"
              role="tab"
              class="gmv-intra__feed-tab"
              :class="{ 'gmv-intra__feed-tab--active': feedTab === 'gmv' }"
              :aria-selected="feedTab === 'gmv'"
              @click="feedTab = 'gmv'"
            >
              实时成交
            </button>
            <button
              type="button"
              role="tab"
              class="gmv-intra__feed-tab"
              :class="{ 'gmv-intra__feed-tab--active': feedTab === 'alerts' }"
              :aria-selected="feedTab === 'alerts'"
              @click="feedTab = 'alerts'"
            >
              补退预警
              <span v-if="opsAlertsBadge > 0" class="gmv-intra__feed-badge">{{ opsAlertsBadge }}</span>
            </button>
          </div>
          <template v-if="feedTab === 'gmv'">
            <div class="gmv-intra__feed-head">
              <div class="gmv-intra__feed-title">实时成交</div>
              <div class="gmv-intra__feed-kpi">
                <span>近1分钟 {{ props.recentMinuteCount }} 笔</span>
                <strong>+¥{{ Number(props.recentMinuteAmount || 0).toLocaleString() }}</strong>
              </div>
            </div>
            <div class="gmv-intra__feed-gmv-body">
              <div class="gmv-intra__ticker-zone">
                <div
                  v-if="displayTickerRows.length"
                  class="gmv-intra__ticker"
                  aria-live="polite"
                >
                  <div
                    v-for="(row, i) in displayTickerRows"
                    :key="row.key"
                    class="gmv-intra__tick"
                    :class="{
                      'gmv-intra__tick--flash': i === 0,
                      'gmv-intra__tick--clickable': row.orderId,
                    }"
                    :role="row.orderId ? 'button' : 'listitem'"
                    :tabindex="row.orderId ? 0 : -1"
                    :title="row.orderId ? '点击查看订单详情与明细' : ''"
                    @click="row.orderId && openOrderPeek(row.orderId)"
                    @keydown.enter.prevent="row.orderId && openOrderPeek(row.orderId)"
                    @keydown.space.prevent="row.orderId && openOrderPeek(row.orderId)"
                  >
                    <span class="gmv-intra__tick-time">{{ row.time }}</span>
                    <span class="gmv-intra__tick-amount">{{ row.amount }}</span>
                  </div>
                </div>
                <p v-else class="gmv-intra__feed-empty">等待推送…</p>
              </div>
              <div class="gmv-intra__backfill" aria-label="进入页面前的今日成交">
                <div class="gmv-intra__backfill-head">
                  <span class="gmv-intra__backfill-title">今日早些时候</span>
                  <span class="gmv-intra__backfill-sub">进入页面前 · 可滚动</span>
                </div>
                <div
                  v-if="props.backfillLoading"
                  class="gmv-intra__feed-empty gmv-intra__feed-empty--in-backfill"
                >
                  加载中…
                </div>
                <div
                  v-else-if="displayBackfillRows.length"
                  class="gmv-intra__ticker gmv-intra__ticker--backfill"
                >
                  <div
                    v-for="row in displayBackfillRows"
                    :key="row.key"
                    class="gmv-intra__tick gmv-intra__tick--backfill"
                    :class="{ 'gmv-intra__tick--clickable': row.orderId }"
                    :role="row.orderId ? 'button' : 'listitem'"
                    :tabindex="row.orderId ? 0 : -1"
                    :title="row.orderId ? '点击查看订单详情与明细' : ''"
                    @click="row.orderId && openOrderPeek(row.orderId)"
                    @keydown.enter.prevent="row.orderId && openOrderPeek(row.orderId)"
                    @keydown.space.prevent="row.orderId && openOrderPeek(row.orderId)"
                  >
                    <span class="gmv-intra__tick-time">{{ row.time }}</span>
                    <span class="gmv-intra__tick-amount">{{ row.amount }}</span>
                  </div>
                </div>
                <p
                  v-else
                  class="gmv-intra__feed-empty gmv-intra__feed-empty--in-backfill gmv-intra__feed-empty--subtle"
                >
                  暂无更早订单
                </p>
              </div>
            </div>
          </template>
          <template v-else>
            <div class="gmv-intra__feed-head gmv-intra__feed-head--alerts">
              <div class="gmv-intra__feed-title">今日概览</div>
              <el-button
                size="small"
                text
                type="warning"
                class="gmv-intra__alert-refresh"
                :loading="opsAlertsLoading"
                @click="loadOpsAlerts"
              >
                刷新
              </el-button>
            </div>
            <div
              class="gmv-intra__alert-body"
              :class="{ 'gmv-intra__alert-body--syncing': opsAlertsLoading && opsAlerts }"
            >
              <template v-if="opsAlerts">
                <div class="gmv-intra__alert-summary">
                  <div class="gmv-intra__alert-pill gmv-intra__alert-pill--return">
                    <span class="gmv-intra__alert-pill__lbl">退货待办</span>
                    <strong>{{ opsAlerts.return_pending?.count ?? 0 }}</strong>
                    <span class="gmv-intra__alert-pill__sub">笔</span>
                    <span class="gmv-intra__alert-pill__amt">¥{{ Number(opsAlerts.return_pending?.amount || 0).toLocaleString() }}</span>
                  </div>
                  <div class="gmv-intra__alert-pill gmv-intra__alert-pill--sup">
                    <span class="gmv-intra__alert-pill__lbl">补单订单</span>
                    <strong>{{ opsAlerts.supplement_today?.linked_count ?? 0 }}</strong>
                    <span class="gmv-intra__alert-pill__sub">笔</span>
                    <span class="gmv-intra__alert-pill__meta">分拣未结 {{ opsAlerts.supplement_today?.pending_disorder_count ?? 0 }}</span>
                  </div>
                </div>
                <div class="gmv-intra__alert-cols">
                  <div class="gmv-intra__alert-col">
                    <div class="gmv-intra__alert-col__hd">退货待办（最近）</div>
                    <ul class="gmv-intra__alert-list">
                      <li v-for="r in (opsAlerts.return_items || []).slice(0, 8)" :key="'r'+r.id" class="gmv-intra__alert-li">
                        <span class="gmv-intra__alert-li__t">{{ formatRowTime(r.add_time) }}</span>
                        <span class="gmv-intra__alert-li__sn" :title="r.backorder_sn">{{ r.backorder_sn }}</span>
                        <span class="gmv-intra__alert-li__amt">¥{{ Number(r.total_amount || 0).toLocaleString() }}</span>
                      </li>
                      <li v-if="!(opsAlerts.return_items || []).length" class="gmv-intra__alert-li--empty">暂无</li>
                    </ul>
                  </div>
                  <div class="gmv-intra__alert-col">
                    <div class="gmv-intra__alert-col__hd">补单订单（最近）</div>
                    <ul class="gmv-intra__alert-list">
                      <li v-for="s in (opsAlerts.supplement_items || []).slice(0, 8)" :key="'s'+s.id" class="gmv-intra__alert-li gmv-intra__alert-li--sup">
                        <span class="gmv-intra__alert-li__t">{{ formatRowTime(s.add_time) }}</span>
                        <span class="gmv-intra__alert-li__sn" :title="s.order_sn">{{ s.order_sn }}</span>
                        <span v-if="Number(s.disorder_status) !== 4" class="gmv-intra__alert-li__tag">分拣{{ s.disorder_status }}</span>
                      </li>
                      <li v-if="!(opsAlerts.supplement_items || []).length" class="gmv-intra__alert-li--empty">暂无</li>
                    </ul>
                  </div>
                </div>
                <div v-if="props.opsAlertReturnTicks?.length" class="gmv-intra__alert-ws">
                  <div class="gmv-intra__alert-ws__hd">通道推送 · 新退货单</div>
                  <div class="gmv-intra__ticker gmv-intra__ticker--dense">
                    <div v-for="(ln, j) in props.opsAlertReturnTicks" :key="j" class="gmv-intra__tick gmv-intra__tick--alert">
                      <span class="gmv-intra__tick-time gmv-intra__tick-time--wide">{{ ln }}</span>
                    </div>
                  </div>
                </div>
              </template>
              <p v-else-if="opsAlertsLoading" class="gmv-intra__feed-empty">加载中…</p>
              <p v-else class="gmv-intra__feed-empty">暂无预警数据</p>
            </div>
          </template>
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

    <el-dialog
      v-model="orderPeekOpen"
      title="订单详情"
      width="min(560px, 94vw)"
      class="gmv-order-peek-dialog"
      append-to-body
      destroy-on-close
      @closed="onOrderPeekClosed"
    >
      <div v-loading="orderPeekLoading" class="order-peek">
        <template v-if="orderPeekHead">
          <div class="order-peek__head">
            <div class="order-peek__head-title">订单信息</div>
            <dl class="order-peek__dl">
              <div class="order-peek__row">
                <dt>订单号</dt>
                <dd>{{ orderPeekHead.order_sn || '—' }}</dd>
              </div>
              <div class="order-peek__row">
                <dt>内部 ID</dt>
                <dd>{{ orderPeekHead.id ?? '—' }}</dd>
              </div>
              <div class="order-peek__row">
                <dt>下单时间</dt>
                <dd>{{ formatRowTime(orderPeekHead.add_time) }}</dd>
              </div>
              <div class="order-peek__row">
                <dt>成交额</dt>
                <dd class="order-peek__money">
                  ¥{{ Number(orderPeekHead.total_amount || 0).toLocaleString() }}
                </dd>
              </div>
              <div class="order-peek__row">
                <dt>会员</dt>
                <dd>
                  {{ [orderPeekHead.member_realname, orderPeekHead.member_login].filter(Boolean).join(' · ') || '—' }}
                </dd>
              </div>
              <div v-if="orderPeekHead.member_id != null && orderPeekHead.member_id !== ''" class="order-peek__row">
                <dt>会员 ID</dt>
                <dd>{{ orderPeekHead.member_id }}</dd>
              </div>
            </dl>
          </div>
          <div class="order-peek__lines-head">订单明细</div>
          <p v-if="orderPeekWarn" class="order-peek__warn">{{ orderPeekWarn }}</p>
          <el-table
            v-if="orderPeekLines.length"
            :data="orderPeekLines"
            size="small"
            class="order-peek__table"
            max-height="320"
            empty-text="暂无商品行"
          >
            <el-table-column prop="goods_name" label="商品" min-width="140" show-overflow-tooltip />
            <el-table-column label="数量" width="88" align="right">
              <template #default="{ row }">{{ formatQty(row.qty) }}</template>
            </el-table-column>
            <el-table-column label="小计" width="112" align="right">
              <template #default="{ row }">
                ¥{{ Number(row.line_amount || 0).toLocaleString() }}
              </template>
            </el-table-column>
          </el-table>
          <p v-else-if="!orderPeekLoading" class="order-peek__empty">暂无明细或未配置明细表</p>
        </template>
        <p v-else-if="!orderPeekLoading" class="order-peek__empty">无法加载订单</p>
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
import { animateKpiTriple } from '../../composables/useKpiTween.js'

const props = defineProps({
  /** [minute_ts_sec, cumulative_gmv] */
  series: { type: Array, default: () => [] },
  tickerLines: { type: Array, default: () => [] },
  /** WebSocket 推送的结构化成交（含 order id，可点击） */
  tickerFeedItems: { type: Array, default: () => [] },
  /** 进入页面前的今日订单（与 ticker 行字段一致） */
  backfillFeedItems: { type: Array, default: () => [] },
  backfillLoading: { type: Boolean, default: false },
  liveWsConnected: { type: Boolean, default: false },
  /** 与 API day_start_ts 一致（秒） */
  axisDayStartTs: { type: Number, default: 0 },
  /** 时间轴 max（秒），一般为 min(now, 当日末) */
  axisMaxTs: { type: Number, default: 0 },
  liveTodayPatch: { type: Object, default: null },
  recentMinuteAmount: { type: Number, default: 0 },
  recentMinuteCount: { type: Number, default: 0 },
  /** WebSocket 推送的新退货单行（纯展示字符串） */
  opsAlertReturnTicks: { type: Array, default: () => [] },
})

const feedTab = ref('gmv')
const opsAlerts = ref(null)
const opsAlertsLoading = ref(false)
let opsPollTimer = null

const opsAlertsBadge = computed(() => {
  const o = opsAlerts.value
  if (!o) return 0
  const a = Number(o.return_pending?.count || 0)
  const b = Number(o.supplement_today?.pending_disorder_count || 0)
  return Math.min(99, a + b)
})

async function loadOpsAlerts() {
  opsAlertsLoading.value = true
  try {
    const r = await fetch('/api/insights/business/ops-alerts?limit=12')
    if (r.ok) opsAlerts.value = await r.json()
  } catch {
    /* 静默 */
  } finally {
    opsAlertsLoading.value = false
  }
}

watch(feedTab, (t) => {
  if (t === 'alerts') void loadOpsAlerts()
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

const displayGmv = ref('--')
const displayOrders = ref('--')
const displayAvg = ref('--')
const kpiBump = ref(false)
/** 当前缓动中的数值，用于连续更新时作为起点 */
const currentGmv = ref(0)
const currentOrders = ref(0)
const currentAvg = ref(0)
let kpiTweenFirst = true
let cancelKpiTween = null
let bumpTimer = null

function formatTweenGmv(n) {
  return fmtMoney(n)
}
function formatTweenOrders(n) {
  return String(Math.round(n))
}
function formatTweenAvg(n) {
  return `¥${Number(n).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`
}

function patchToTargets(p) {
  if (!p) return null
  const gmv = p.gmv != null && Number.isFinite(Number(p.gmv)) ? Number(p.gmv) : null
  const orders = p.order_count != null && Number.isFinite(Number(p.order_count)) ? Number(p.order_count) : null
  const avg = p.avg_ticket != null && Number.isFinite(Number(p.avg_ticket)) ? Number(p.avg_ticket) : null
  if (gmv == null && orders == null && avg == null) return null
  return {
    gmv: gmv ?? currentGmv.value,
    orders: orders ?? currentOrders.value,
    avg: avg ?? currentAvg.value,
  }
}

function nearSame(a, b, eps) {
  return Math.abs(a - b) < eps
}

watch(
  () => props.liveTodayPatch,
  (p) => {
    const to = patchToTargets(p)
    if (!to) return

    const from = kpiTweenFirst
      ? { gmv: 0, orders: 0, avg: 0 }
      : { gmv: currentGmv.value, orders: currentOrders.value, avg: currentAvg.value }

    if (
      !kpiTweenFirst
      && nearSame(from.gmv, to.gmv, 0.005)
      && nearSame(from.orders, to.orders, 0.5)
      && nearSame(from.avg, to.avg, 0.005)
    ) {
      return
    }

    if (cancelKpiTween) {
      cancelKpiTween()
      cancelKpiTween = null
    }
    if (bumpTimer) {
      clearTimeout(bumpTimer)
      bumpTimer = null
    }

    kpiBump.value = true
    bumpTimer = window.setTimeout(() => {
      kpiBump.value = false
      bumpTimer = null
    }, 280)

    cancelKpiTween = animateKpiTriple(from, to, {
      durationMs: 520,
      onFrame: ({ gmv, orders, avg }) => {
        currentGmv.value = gmv
        currentOrders.value = orders
        currentAvg.value = avg
        displayGmv.value = formatTweenGmv(gmv)
        displayOrders.value = formatTweenOrders(orders)
        displayAvg.value = formatTweenAvg(avg)
      },
      onComplete: () => {
        currentGmv.value = to.gmv
        currentOrders.value = to.orders
        currentAvg.value = to.avg
        displayGmv.value = formatTweenGmv(to.gmv)
        displayOrders.value = formatTweenOrders(to.orders)
        displayAvg.value = formatTweenAvg(to.avg)
        cancelKpiTween = null
        kpiTweenFirst = false
      },
    })
  },
  { deep: true, immediate: true },
)

const parsedTickerLines = computed(() => props.tickerLines.map((line) => parseTickerLine(line)))

function fmtTickClock(ts) {
  const n = Number(ts)
  if (!Number.isFinite(n)) return '--:--:--'
  return new Date(n * 1000).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

/** 优先用含 id 的推送行；否则退回纯字符串 ticker（不可点） */
const displayTickerRows = computed(() => {
  const raw = props.tickerFeedItems
  if (Array.isArray(raw) && raw.length) {
    return raw.map((it, idx) => {
      const id = Number(it?.id)
      const add = Number(it?.add_time)
      const amt = Number(it?.amount)
      return {
        key: `${id}-${add}-${idx}`,
        orderId: Number.isFinite(id) && id > 0 ? id : null,
        time: fmtTickClock(add),
        amount: `+¥${Number.isFinite(amt) ? amt.toLocaleString() : '—'}`,
      }
    })
  }
  return parsedTickerLines.value.map((line, i) => ({
    key: `s-${i}`,
    orderId: null,
    time: line.time,
    amount: line.amount,
  }))
})

const displayBackfillRows = computed(() => {
  const raw = props.backfillFeedItems
  if (!Array.isArray(raw) || !raw.length) return []
  return raw.map((it, idx) => {
    const id = Number(it?.id)
    const add = Number(it?.add_time)
    const amt = Number(it?.amount)
    return {
      key: `bf-${id}-${add}-${idx}`,
      orderId: Number.isFinite(id) && id > 0 ? id : null,
      time: fmtTickClock(add),
      amount: `+¥${Number.isFinite(amt) ? amt.toLocaleString() : '—'}`,
    }
  })
})

const orderPeekOpen = ref(false)
const orderPeekLoading = ref(false)
const orderPeekHead = ref(null)
const orderPeekLines = ref([])
const orderPeekWarn = ref('')

function onOrderPeekClosed() {
  orderPeekHead.value = null
  orderPeekLines.value = []
  orderPeekWarn.value = ''
}

async function openOrderPeek(orderId) {
  const oid = Number(orderId)
  if (!Number.isFinite(oid) || oid <= 0) return
  orderPeekOpen.value = true
  orderPeekLoading.value = true
  orderPeekHead.value = null
  orderPeekLines.value = []
  orderPeekWarn.value = ''
  try {
    const [rh, rli] = await Promise.all([
      fetch(`/api/insights/business/order-head?order_id=${encodeURIComponent(oid)}`),
      fetch(`/api/insights/business/order-line-items?order_id=${encodeURIComponent(oid)}`),
    ])
    if (!rh.ok) {
      throw new Error(await parseErrorResponse(rh))
    }
    orderPeekHead.value = await rh.json()
    if (rli.ok) {
      const li = await rli.json()
      orderPeekLines.value = Array.isArray(li.rows) ? li.rows : []
      orderPeekWarn.value = typeof li.warning === 'string' ? li.warning : ''
    } else {
      orderPeekWarn.value = await parseErrorResponse(rli)
    }
  } catch (e) {
    orderPeekOpen.value = false
    ElMessage.error(e?.message || '加载订单失败')
  } finally {
    orderPeekLoading.value = false
  }
}

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
    ElMessage.info('此为当日 0 点起点（累计 0），请点击阶梯上产生累计变化的时刻查看该分钟订单')
    return
  }
  const lastRealTs = props.series?.length ? Number(props.series[props.series.length - 1][0]) : null
  if (t1 && lastRealTs != null && tsSec === t1 && t1 > lastRealTs) {
    ElMessage.info('此处为延伸至当前时刻的持平线，请点击左侧阶梯发生转折的时刻查看订单明细')
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
        return `${tlabel}<br/>累计 GMV: ¥${Number(y).toLocaleString()}`
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
  void loadOpsAlerts()
  opsPollTimer = setInterval(() => { void loadOpsAlerts() }, 45000)
})
onUnmounted(() => {
  if (opsPollTimer) {
    clearInterval(opsPollTimer)
    opsPollTimer = null
  }
  ro?.disconnect()
  chart.value?.dispose()
  if (cancelKpiTween) {
    cancelKpiTween()
    cancelKpiTween = null
  }
  if (bumpTimer) {
    clearTimeout(bumpTimer)
    bumpTimer = null
  }
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

@keyframes gmv-kpi-value-bump {
  0% {
    transform: translateY(0);
    filter: brightness(1);
  }
  45% {
    transform: translateY(-3px);
    filter: brightness(1.12);
  }
  100% {
    transform: translateY(0);
    filter: brightness(1);
  }
}
.gmv-hero-kpi__value--bump {
  animation: gmv-kpi-value-bump 0.28s ease-out both;
}
.gmv-hero-kpi__value--bump.gmv-hero-kpi__value--gmv {
  text-shadow:
    0 0 22px rgba(251, 191, 36, 0.65),
    0 0 48px rgba(251, 191, 36, 0.22);
}
.gmv-hero-kpi__value--bump.gmv-hero-kpi__value--orders {
  text-shadow:
    0 0 22px rgba(34, 211, 238, 0.6),
    0 0 48px rgba(34, 211, 238, 0.2);
}
.gmv-hero-kpi__value--bump.gmv-hero-kpi__value--ticket {
  text-shadow:
    0 0 22px rgba(56, 189, 248, 0.55),
    0 0 48px rgba(56, 189, 248, 0.18);
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
.gmv-intra__feed-tabs {
  display: flex;
  flex-shrink: 0;
  border-bottom: 1px solid rgba(250, 204, 21, 0.12);
}
.gmv-intra__feed-tab {
  flex: 1;
  margin: 0;
  padding: 8px 10px;
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  border: none;
  background: rgba(15, 23, 42, 0.65);
  color: rgba(148, 163, 184, 0.9);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}
.gmv-intra__feed-tab--active {
  background: rgba(251, 191, 36, 0.12);
  color: #fde68a;
  box-shadow: inset 0 -2px 0 rgba(251, 191, 36, 0.65);
}
.gmv-intra__feed-badge {
  min-width: 18px;
  padding: 0 5px;
  border-radius: 999px;
  background: rgba(248, 113, 113, 0.35);
  color: #fecaca;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0;
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
.gmv-intra__feed-gmv-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.gmv-intra__ticker-zone {
  flex: 1 1 0;
  min-height: 72px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.gmv-intra__ticker-zone > .gmv-intra__ticker {
  flex: 1;
  min-height: 0;
}
.gmv-intra__ticker-zone > .gmv-intra__feed-empty {
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.gmv-intra__backfill {
  flex: 1 1 0;
  min-height: 88px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-top: 1px solid rgba(250, 204, 21, 0.14);
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.2) 0%, rgba(15, 23, 42, 0.45) 100%);
}
.gmv-intra__backfill-head {
  flex-shrink: 0;
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 6px 10px;
  padding: 8px 12px 6px;
  border-bottom: 1px solid rgba(56, 189, 248, 0.1);
}
.gmv-intra__backfill-title {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: rgba(125, 211, 252, 0.88);
}
.gmv-intra__backfill-sub {
  font-size: 10px;
  color: rgba(148, 163, 184, 0.82);
  letter-spacing: 0.04em;
}
.gmv-intra__ticker--backfill {
  flex: 1;
  min-height: 0;
  padding-top: 6px;
  padding-bottom: 10px;
}
.gmv-intra__tick--backfill .gmv-intra__tick-time {
  color: rgba(186, 198, 214, 0.92);
}
.gmv-intra__tick--backfill .gmv-intra__tick-amount {
  color: rgba(253, 230, 138, 0.88);
  text-shadow: none;
}
.gmv-intra__feed-empty--in-backfill {
  flex: 1;
  min-height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0;
  padding: 8px 12px 12px;
}
.gmv-intra__feed-empty--subtle {
  color: rgba(148, 163, 184, 0.65);
  font-size: 12px;
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
.gmv-intra__tick--clickable {
  cursor: pointer;
  border-radius: 6px;
  margin: 0 -6px;
  padding: 4px 6px;
  outline: none;
  transition: background 0.15s ease, box-shadow 0.15s ease;
}
.gmv-intra__tick--clickable:hover {
  background: rgba(67, 204, 248, 0.12);
  box-shadow: 0 0 0 1px rgba(67, 204, 248, 0.28);
}
.gmv-intra__tick--clickable:focus-visible {
  box-shadow: 0 0 0 2px rgba(67, 204, 248, 0.55);
}
.order-peek {
  min-height: 120px;
  color: #e2e8f0;
  font-size: 14px;
  line-height: 1.5;
}
.order-peek__head {
  margin-bottom: 16px;
  padding: 14px 16px;
  border-radius: 10px;
  background: rgba(30, 41, 59, 0.65);
  border: 1px solid rgba(67, 204, 248, 0.22);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
}
.order-peek__head-title {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #7dd3fc;
  margin-bottom: 12px;
}
.order-peek__dl {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.order-peek__row {
  display: grid;
  grid-template-columns: 88px 1fr;
  gap: 12px;
  align-items: start;
}
.order-peek__row dt {
  margin: 0;
  font-size: 12px;
  font-weight: 600;
  color: rgba(148, 163, 184, 0.95);
  letter-spacing: 0.02em;
}
.order-peek__row dd {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #f8fafc;
  word-break: break-word;
}
.order-peek__money {
  color: #fde68a !important;
  font-size: 16px !important;
  letter-spacing: 0.02em;
}
.order-peek__lines-head {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #7dd3fc;
  margin: 4px 0 10px;
}
.order-peek__warn {
  margin: 0 0 10px;
  padding: 8px 10px;
  border-radius: 6px;
  font-size: 12px;
  color: #fcd34d;
  background: rgba(120, 53, 15, 0.35);
  border: 1px solid rgba(251, 191, 36, 0.25);
}
.order-peek__empty {
  margin: 12px 0 0;
  font-size: 13px;
  color: rgba(148, 163, 184, 0.9);
}
.gmv-intra__feed-empty {
  flex: 1;
  margin: 0;
  padding: 14px 12px;
  font-size: 13px;
  color: rgba(148, 163, 184, 0.75);
}
.gmv-intra__feed-head--alerts {
  align-items: center;
}
.gmv-intra__alert-refresh {
  padding: 2px 8px;
  font-size: 11px;
  color: #fde68a !important;
  --el-button-hover-text-color: #fef9c3;
}
.gmv-intra__alert-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 0 0 8px;
  transition: opacity 0.2s ease;
}
.gmv-intra__alert-body--syncing {
  opacity: 0.9;
}
.gmv-intra__alert-summary {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px 12px 0;
}
.gmv-intra__alert-pill {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: baseline;
  gap: 6px 10px;
  padding: 8px 10px;
  border-radius: 6px;
  font-size: 11px;
  color: rgba(226, 232, 240, 0.88);
}
.gmv-intra__alert-pill--return {
  border: 1px solid rgba(248, 113, 113, 0.35);
  background: rgba(127, 29, 29, 0.22);
}
.gmv-intra__alert-pill--sup {
  border: 1px solid rgba(56, 189, 248, 0.28);
  background: rgba(12, 74, 110, 0.22);
}
.gmv-intra__alert-pill__lbl {
  grid-column: 1 / -1;
  letter-spacing: 0.06em;
  opacity: 0.85;
}
.gmv-intra__alert-pill strong {
  font-size: 18px;
  color: #fef9c3;
}
.gmv-intra__alert-pill__sub {
  opacity: 0.75;
}
.gmv-intra__alert-pill__amt {
  grid-column: 1 / -1;
  font-weight: 600;
  color: #fecaca;
}
.gmv-intra__alert-pill__meta {
  grid-column: 1 / -1;
  font-size: 10px;
  color: rgba(125, 211, 252, 0.9);
}
.gmv-intra__alert-cols {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 10px 12px 0;
}
.gmv-intra__alert-col__hd {
  font-size: 10px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: rgba(250, 204, 21, 0.65);
  margin-bottom: 6px;
}
.gmv-intra__alert-list {
  list-style: none;
  margin: 0;
  padding: 0;
  max-height: 140px;
  overflow-y: auto;
}
.gmv-intra__alert-li {
  display: grid;
  grid-template-columns: 108px 1fr auto;
  gap: 6px;
  align-items: baseline;
  padding: 5px 6px;
  margin-bottom: 4px;
  border-radius: 4px;
  background: rgba(15, 23, 42, 0.55);
  border: 1px solid rgba(71, 85, 105, 0.35);
  font-size: 10px;
}
.gmv-intra__alert-li--sup {
  border-color: rgba(14, 165, 233, 0.22);
}
.gmv-intra__alert-li__t {
  color: rgba(196, 210, 228, 0.85);
  font-family: ui-monospace, monospace;
}
.gmv-intra__alert-li__sn {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #e2e8f0;
}
.gmv-intra__alert-li__amt {
  color: #fecaca;
  font-weight: 600;
}
.gmv-intra__alert-li__tag {
  grid-column: 3;
  font-size: 9px;
  padding: 1px 4px;
  border-radius: 3px;
  background: rgba(251, 191, 36, 0.2);
  color: #fde68a;
}
.gmv-intra__alert-li--empty {
  color: rgba(148, 163, 184, 0.65);
  font-size: 11px;
  padding: 8px;
  border: none;
  background: transparent;
}
.gmv-intra__alert-ws {
  margin: 10px 12px 0;
  padding-top: 8px;
  border-top: 1px dashed rgba(100, 116, 139, 0.35);
}
.gmv-intra__alert-ws__hd {
  font-size: 10px;
  letter-spacing: 0.06em;
  color: rgba(251, 191, 36, 0.7);
  margin-bottom: 6px;
}
.gmv-intra__ticker--dense {
  max-height: 120px;
  padding: 6px 8px;
}
.gmv-intra__tick--alert {
  grid-template-columns: 1fr;
}
.gmv-intra__tick-time--wide {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
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
.gmv-order-peek-dialog.el-dialog {
  --el-dialog-bg-color: rgba(15, 23, 42, 0.98);
  --el-dialog-border-color: rgba(56, 189, 248, 0.35);
  /* 避免 el-table stripe / 填充色用默认浅色，在深色弹窗里出现白条 */
  --el-fill-color-lighter: rgba(30, 41, 59, 0.72);
  background: rgba(15, 23, 42, 0.98);
  border: 1px solid rgba(56, 189, 248, 0.28);
  box-shadow: 0 24px 48px rgba(0, 0, 0, 0.45), 0 0 0 1px rgba(255, 255, 255, 0.04) inset;
}
.gmv-order-peek-dialog .el-dialog__title {
  color: #f8fafc;
  font-weight: 700;
  letter-spacing: 0.06em;
}
.gmv-order-peek-dialog .el-dialog__headerbtn .el-dialog__close {
  color: #94a3b8;
}
.gmv-order-peek-dialog .el-table {
  --el-table-bg-color: rgba(15, 23, 42, 0.5);
  --el-table-row-hover-bg-color: rgba(56, 189, 248, 0.1);
  --el-table-tr-bg-color: rgba(15, 23, 42, 0.35);
  --el-table-header-bg-color: rgba(30, 41, 59, 0.98);
  --el-table-text-color: #f1f5f9;
  --el-table-border-color: rgba(51, 65, 85, 0.6);
  font-size: 13px;
}
.gmv-order-peek-dialog .el-table th.el-table__cell {
  font-weight: 700;
  color: #bae6fd !important;
}
</style>
