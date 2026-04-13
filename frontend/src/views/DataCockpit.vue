<template>
  <div
    class="cockpit-root"
    :class="{ 'cockpit-root--gold-era': activeTab === 'ops' || activeTab === 'smart' }"
  >
    <!-- Tab 1: 智能驾驶舱（3D 地图 + 业务数据） -->
    <div v-if="activeTab === 'smart'" class="cockpit-shell">
      <div class="cockpit-shell__bg" aria-hidden="true" />
      <div class="cockpit-shell__scan" aria-hidden="true" />

      <header class="cockpit-top">
        <div class="cockpit-top__side cockpit-top__side--left">
          <span class="cockpit-top__tag">SMART · DATA · COCKPIT</span>
        </div>
        <div class="cockpit-top__center">
          <div class="cockpit-top__title-line" />
          <h1 class="cockpit-top__title">智能驾驶舱</h1>
          <p class="cockpit-top__sub">{{ smartSubtitle }}</p>
          <div class="cockpit-top__title-line cockpit-top__title-line--short" />
        </div>
        <div class="cockpit-top__side cockpit-top__side--right">
          <div class="cockpit-top__clock-wrap">
            <span class="cockpit-top__clock">{{ clockText }}</span>
            <span class="cockpit-top__clock-label">LOCAL</span>
          </div>
        </div>
      </header>

      <div v-if="loadErrorOps" class="cockpit-shell__err">
        {{ loadErrorOps }}
        <el-button type="primary" size="small" class="cockpit-retry" @click="loadOpsData">重试</el-button>
      </div>

      <div class="cockpit-grid cockpit-grid--smart">
        <div class="cockpit-grid__cell cockpit-grid__cell--r1c1">
          <PanelRegion :data="regionData" />
        </div>
        <div class="cockpit-grid__cell cockpit-grid__cell--map">
          <CockpitPanel title="车辆分布" title-en="VEHICLE LOCATION">
            <CockpitBeijingMap
              :vehicles="mapVehicles"
              :drill-adcode="drillAdcode"
              @drill="onMapDrill"
              @back="onBackCity"
            />
          </CockpitPanel>
        </div>
        <div class="cockpit-grid__cell cockpit-grid__cell--r1c3">
          <PanelOrderRank :data="orderRankData" :hint="smartRankGoodsHint" />
        </div>
        <div class="cockpit-grid__cell cockpit-grid__cell--r2c1">
          <PanelOrderTrend :data="orderTrendData" />
        </div>
        <div class="cockpit-grid__cell cockpit-grid__cell--r2c3">
          <PanelGoodsPie :data="goodsData" :hint="smartRankGoodsHint" />
        </div>
        <div class="cockpit-grid__cell cockpit-grid__cell--r3c1">
          <PanelKpi :data="kpiLegacy" />
        </div>
        <div class="cockpit-grid__cell cockpit-grid__cell--r3c2">
          <PanelTrendLine :data="orderTrendData" />
        </div>
        <div class="cockpit-grid__cell cockpit-grid__cell--r3c3">
          <PanelGrowth :kpi="kpiLegacy" />
        </div>
      </div>
    </div>

    <!-- Tab 2: 运营指挥台（无地图，成交节奏条带 + 真实 KPI） -->
    <div v-else-if="activeTab === 'ops'" class="cockpit-shell">
      <div class="cockpit-shell__bg" aria-hidden="true" />
      <div class="cockpit-shell__scan" aria-hidden="true" />

      <header class="cockpit-top">
        <div class="cockpit-top__side cockpit-top__side--left">
          <span class="cockpit-top__tag">AI · OPS · PULSE</span>
        </div>
        <div class="cockpit-top__center">
          <div class="cockpit-top__title-line" />
          <h1 class="cockpit-top__title">运营指挥台</h1>
          <p class="cockpit-top__sub">{{ opsSubtitle }}</p>
          <div class="cockpit-top__title-line cockpit-top__title-line--short" />
        </div>
        <div class="cockpit-top__side cockpit-top__side--right">
          <div class="cockpit-top__clock-wrap">
            <span class="cockpit-top__clock">{{ clockText }}</span>
            <span class="cockpit-top__clock-label">LOCAL</span>
          </div>
        </div>
      </header>

      <div v-if="loadErrorOps" class="cockpit-shell__err">
        {{ loadErrorOps }}
        <el-button type="primary" size="small" class="cockpit-retry" @click="loadOpsData">重试</el-button>
      </div>

      <div class="cockpit-grid cockpit-grid--ops">
        <div class="cockpit-grid__cell cockpit-grid__cell--ops-hero">
          <PanelGmvIntraday
            :series="gmvIntradaySeries"
            :ticker-lines="gmvTickerLines"
            :live-ws-connected="gmvWsConnected"
            :axis-day-start-ts="gmvDayStartTs"
            :axis-max-ts="gmvAxisMaxTs"
            :live-today-patch="gmvLiveTodayPatch"
            :recent-minute-amount="gmvRecentMinuteAmount"
            :recent-minute-count="gmvRecentMinuteCount"
          />
        </div>
        <div class="cockpit-grid__cell cockpit-grid__cell--ops-rank">
          <PanelOrderRank :data="orderRankData" />
        </div>
        <div class="cockpit-grid__cell cockpit-grid__cell--ops-goods">
          <PanelGoodsPie :data="goodsData" />
        </div>
        <div class="cockpit-grid__cell cockpit-grid__cell--ops-intraday">
          <PanelWeekdayProfile
            :raw-buckets="gmvRawBuckets"
            :axis-day-start-ts="gmvDayStartTs"
          />
        </div>
        <div class="cockpit-grid__cell cockpit-grid__cell--ops-kpi">
          <PanelOpsDataFreshness
            :live-ws-connected="gmvWsConnected"
            :last-intraday-fetched-at="gmvLastIntradayFetchedAt"
            :last-live-push-at="gmvLastLivePushAt"
            :last-ws-ping-at="gmvLastWsPingAt"
            :ws-opened-at="gmvWsOpenedAt"
            :recent-minute-amount="gmvRecentMinuteAmount"
            :recent-minute-count="gmvRecentMinuteCount"
            :recent5m-amount="gmvRecent5mAmount"
            :recent5m-count="gmvRecent5mCount"
          />
        </div>
      </div>
    </div>

    <el-button
      v-if="drillAdcode && activeTab === 'smart'"
      type="primary"
      class="cockpit-float-back"
      @click="onBackCity"
    >
      返回全市
    </el-button>

    <CockpitViewIoT
      v-else-if="activeTab === 'iot' || activeTab === 'iot3d'"
      :map-mode="activeTab === 'iot3d' ? 'amap3d' : 'amap'"
      :device-status="iotDeviceStatus"
      :all-cameras="iotAllCameras"
      :camera-list="iotCameraList"
      :device-bindings="iotDeviceBindings"
      :temp-humidity="iotTempHumidity"
      :temp-threshold="TEMP_THRESHOLD"
      :vehicles="iotVehicles"
      :warehouses="iotWarehouses"
      :clock-text="clockText"
      :load-error="''"
    />

    <nav class="cockpit-tab-bar">
      <div class="cockpit-tab-bar__inner">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          :class="['cockpit-tab-bar__item', { 'cockpit-tab-bar__item--active': activeTab === tab.key }]"
          @click="onTabClick(tab.key)"
        >
          <span class="cockpit-tab-bar__icon">{{ tab.icon }}</span>
          <span class="cockpit-tab-bar__label">{{ tab.label }}</span>
        </button>
      </div>
    </nav>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import PanelRegion from '../components/cockpit/PanelRegion.vue'
import PanelOrderRank from '../components/cockpit/PanelOrderRank.vue'
import PanelOrderTrend from '../components/cockpit/PanelOrderTrend.vue'
import PanelGoodsPie from '../components/cockpit/PanelGoodsPie.vue'
import PanelTrendLine from '../components/cockpit/PanelTrendLine.vue'
import PanelGmvIntraday from '../components/cockpit/PanelGmvIntraday.vue'
import PanelWeekdayProfile from '../components/cockpit/PanelWeekdayProfile.vue'
import PanelOpsDataFreshness from '../components/cockpit/PanelOpsDataFreshness.vue'
import PanelKpi from '../components/cockpit/PanelKpi.vue'
import PanelGrowth from '../components/cockpit/PanelGrowth.vue'
import CockpitPanel from '../components/cockpit/CockpitPanel.vue'
import CockpitBeijingMap from '../components/cockpit/CockpitBeijingMap.vue'
import CockpitViewIoT from '../components/cockpit/CockpitViewIoT.vue'
import { useCockpitLiveGmv } from '../composables/useCockpitLiveGmv.js'
import { generateMockVehiclesInBeijing } from '../mock/cockpitVehicles.js'
import {
  mockDeviceStatus,
  mockAllCameras,
  mockCameraList,
  mockDeviceBindings,
  mockTempHumidity24h,
  mockWarehouses,
  TEMP_THRESHOLD,
} from '../mock/cockpitIoT.js'

const API_BASE = '/api/insights/business'
const GEO_URL = '/geo/beijing_110000_full.json'

/** 默认运营台：无地图首屏，较智能驾驶舱更轻；物联 tab 含高德外链，一般最慢 */
const activeTab = ref('ops')
const tabs = [
  { key: 'ops', label: '运营指挥台', icon: '◉' },
  { key: 'smart', label: '智能驾驶舱', icon: '◈' },
  { key: 'iot', label: '物联监控大屏', icon: '◎' },
  { key: 'iot3d', label: '3D物联监控大屏', icon: '◆' },
]

const loadErrorOps = ref('')

const clockText = ref('')
const orderTrendData = ref([])
const orderRankData = ref([])
const goodsData = ref([])
const regionData = ref([])
const kpiRange = ref(null)
const kpiToday = ref(null)
/** 智能驾驶舱 PanelKpi / PanelGrowth 用（KPI 来自 kpi-summary：订单/GMV/会员/退单等为业务库实查） */
const kpiLegacy = ref({})
const mapVehicles = ref([])
const drillAdcode = ref('')
const iotVehicles = ref([])

const iotDeviceStatus = ref({})
const iotAllCameras = ref([])
const iotCameraList = ref([])
const iotDeviceBindings = ref([])
const iotTempHumidity = ref([])
const iotWarehouses = ref([])

/** 仅在需要地图/物联车辆时拉 GeoJSON，避免默认运营台也解析 ~100KB+ 区界 */
let geoJsonCache = null
async function ensureGeoAndVehicles() {
  if (mapVehicles.value.length && iotVehicles.value.length) return
  if (!geoJsonCache) {
    try {
      const r = await fetch(GEO_URL)
      if (r.ok) geoJsonCache = await r.json()
    } catch {
      geoJsonCache = null
    }
  }
  if (!geoJsonCache) return
  if (!mapVehicles.value.length) {
    mapVehicles.value = generateMockVehiclesInBeijing(52, geoJsonCache)
  }
  if (!iotVehicles.value.length) {
    iotVehicles.value = generateMockVehiclesInBeijing(28, geoJsonCache)
  }
}

watch(activeTab, (k) => {
  if (k === 'smart' || k === 'iot' || k === 'iot3d') void ensureGeoAndVehicles()
})

let clockTimer = null
let opsAutoRetryTimer = null
let opsAutoRetryDelayMs = 5000
/** 由 useCockpitLiveGmv 注入：运营台每次拉排名/单品时同步重拉今日分时桶，避免「日内成交结构」只靠首屏+WS 显得不更新 */
let gmvLoadIntraday = async () => {}

function pad2(n) { return n < 10 ? `0${n}` : `${n}` }

function tickClock() {
  const d = new Date()
  clockText.value = `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())} ${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`
}

const opsSubtitle = computed(() => {
  return '订单与客户数据来自业务库 · 统计区间 今日'
})

const smartSubtitle = computed(() => {
  const r = kpiRange.value
  if (r?.start_date && r?.end_date) {
    return `2D 态势地图演示点位为模拟数据 · 其余图表来自业务库 · 统计区间 ${r.start_date} ~ ${r.end_date}（上海时区）`
  }
  return '2D 态势地图演示点位为模拟数据 · 其余图表来自业务库 · 加载成功后显示统计区间与上海时区说明'
})

/** 智能驾驶舱：订单排名 / 单品分布 的统计区间（与接口 start/end 一致） */
const smartRankGoodsHint = computed(() => {
  const r = kpiRange.value
  if (r?.start_date && r?.end_date) {
    return `排名统计区间：${r.start_date} ~ ${r.end_date}（上海时区）`
  }
  return ''
})

function syncKpiLegacy(kr, kt) {
  const t = kt?.ok ? kt.data : null
  const r = kr?.ok ? kr.data : null
  kpiLegacy.value = {
    todayOrders: t?.order_count ?? r?.order_count ?? '--',
    todayGmv: t?.gmv ?? r?.gmv ?? '--',
    avgOrderAmount: t?.avg_ticket ?? r?.avg_ticket ?? '--',
    distinctBuyers: t?.distinct_buyers ?? '--',
    returnRateByAmount: t?.return_rate_by_amount_pct ?? '--',
    firstOrderMembers: t?.first_order_members ?? '--',
  }
}

function onMapDrill({ level, adcode }) {
  if (level === 'district') {
    drillAdcode.value = adcode || ''
  }
}

function onBackCity() {
  drillAdcode.value = ''
}

async function fetchJson(url) {
  const res = await fetch(url)
  const text = await res.text()
  let body
  try {
    body = JSON.parse(text)
  } catch {
    body = null
  }
  if (!res.ok) {
    const detail = body?.detail
    const msg = typeof detail === 'string'
      ? detail
      : (Array.isArray(detail) ? detail.map((x) => x.msg || x).join('; ') : text || res.statusText)
    throw new Error(msg || `HTTP ${res.status}`)
  }
  return body
}

async function safeFetchJson(url) {
  try {
    return { ok: true, data: await fetchJson(url) }
  } catch (e) {
    return { ok: false, error: e?.message || String(e) }
  }
}

function todayDateStr() {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

async function loadOpsData() {
  loadErrorOps.value = ''
  const today = todayDateStr()
  const isOps = activeTab.value === 'ops'

  const fetches = [
    safeFetchJson(`${API_BASE}/orders-top-members${isOps ? `?start_date=${today}&end_date=${today}` : ''}`),
    safeFetchJson(`${API_BASE}/goods-top${isOps ? `?start_date=${today}&end_date=${today}` : ''}`),
    safeFetchJson(`${API_BASE}/kpi-summary?scope=today`),
  ]
  if (!isOps) {
    fetches.push(
      safeFetchJson(`${API_BASE}/orders-daily`),
      safeFetchJson(`${API_BASE}/region-distribution`),
      safeFetchJson(`${API_BASE}/kpi-summary?scope=range`),
    )
  }

  const results = await Promise.all(fetches)
  const [members, goods, kt] = results

  orderRankData.value = members.ok && Array.isArray(members.data?.rows) ? members.data.rows : []
  goodsData.value = goods.ok && Array.isArray(goods.data?.rows) ? goods.data.rows : []
  kpiToday.value = kt.ok && kt.data?.scope === 'today' ? kt.data : null

  const errParts = []
  if (!members.ok) errParts.push(`会员排名：${members.error}`)
  if (!goods.ok) errParts.push(`单品分布：${goods.error}`)
  if (!kt.ok) errParts.push(`今日 KPI：${kt.error}`)

  if (!isOps) {
    const [daily, region, kr] = [results[3], results[4], results[5]]
    orderTrendData.value = daily.ok && Array.isArray(daily.data?.series) ? daily.data.series : []
    regionData.value = region.ok && Array.isArray(region.data?.rows) ? region.data.rows : []
    kpiRange.value = kr.ok && kr.data?.scope === 'range' ? kr.data : null
    if (!daily.ok) errParts.push(`订单趋势：${daily.error}`)
    if (!region.ok) errParts.push(`区域分布：${region.error}`)
    if (!kr.ok) errParts.push(`区间 KPI：${kr.error}`)
    syncKpiLegacy(kr, kt)
  } else {
    syncKpiLegacy(null, kt)
  }

  loadErrorOps.value = errParts.join(' ')
  if (loadErrorOps.value) {
    scheduleOpsAutoRetry()
  } else {
    clearOpsAutoRetry()
  }

  if (activeTab.value === 'ops') {
    try {
      await gmvLoadIntraday()
    } catch {
      /* 与 WS 增量并行；REST 失败时仍保留 WS 合并数据 */
    }
  }
}

const opsLiveEnabled = computed(() => activeTab.value === 'ops')
const {
  cumulativeSeries: gmvIntradaySeries,
  liveTodayPatch: gmvLiveTodayPatch,
  tickerLines: gmvTickerLines,
  wsConnected: gmvWsConnected,
  gmvDayStartTs,
  gmvAxisMaxTs,
  rawBuckets: gmvRawBuckets,
  recentMinuteAmount: gmvRecentMinuteAmount,
  recentMinuteCount: gmvRecentMinuteCount,
  recent5mAmount: gmvRecent5mAmount,
  recent5mCount: gmvRecent5mCount,
  lastIntradayFetchedAt: gmvLastIntradayFetchedAt,
  lastLivePushAt: gmvLastLivePushAt,
  lastWsPingAt: gmvLastWsPingAt,
  wsOpenedAt: gmvWsOpenedAt,
  loadIntraday: gmvLoadIntradayFromComposable,
} = useCockpitLiveGmv(opsLiveEnabled, {
  onChartsRefresh: loadOpsData,
  refreshDebounceMs: 8000,
})
gmvLoadIntraday = gmvLoadIntradayFromComposable

function onTabClick(key) {
  activeTab.value = key
  clearOpsAutoRetry()
  if (key === 'ops' || key === 'smart') {
    void loadOpsData()
  }
}

function clearOpsAutoRetry() {
  if (opsAutoRetryTimer) {
    clearTimeout(opsAutoRetryTimer)
    opsAutoRetryTimer = null
  }
  opsAutoRetryDelayMs = 5000
}

function scheduleOpsAutoRetry() {
  if (opsAutoRetryTimer) return
  if (activeTab.value !== 'ops' && activeTab.value !== 'smart') return
  const delay = opsAutoRetryDelayMs
  opsAutoRetryTimer = setTimeout(async () => {
    opsAutoRetryTimer = null
    // 非看板页时不再重试，避免无意义后台请求
    if (activeTab.value !== 'ops' && activeTab.value !== 'smart') {
      clearOpsAutoRetry()
      return
    }
    await loadOpsData()
    if (loadErrorOps.value) {
      opsAutoRetryDelayMs = Math.min(60000, Math.round(opsAutoRetryDelayMs * 1.8))
    } else {
      opsAutoRetryDelayMs = 5000
    }
  }, delay)
}

function initIotMock() {
  iotDeviceStatus.value = mockDeviceStatus()
  iotAllCameras.value = mockAllCameras()
  iotCameraList.value = mockCameraList()
  iotDeviceBindings.value = mockDeviceBindings()
  iotTempHumidity.value = mockTempHumidity24h()
  iotWarehouses.value = mockWarehouses()
}

onMounted(() => {
  tickClock()
  clockTimer = setInterval(tickClock, 1000)
  initIotMock()
  /* 不 await：首屏先渲染，图表随接口返回逐项铺满，避免整页「卡死」感 */
  void loadOpsData()
})

onUnmounted(() => {
  if (clockTimer) clearInterval(clockTimer)
  clearOpsAutoRetry()
})
</script>

<style scoped>
.cockpit-root {
  position: relative;
  display: flex;
  flex-direction: column;
  min-height: calc(100vh - 60px);
  height: calc(100vh - 60px);
  overflow: hidden;
}

.cockpit-shell {
  position: relative;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  flex: 1;
  min-height: 0;
  padding: 14px 16px 16px;
  color: var(--sx-text-body);
  overflow: hidden;
}

.cockpit-shell__bg {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  background: url('/cockpit-bg.jpg') center / cover no-repeat;
  background-color: #060a14;
}

.cockpit-shell__bg::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse 90% 60% at 50% 10%, rgba(34, 211, 238, 0.06), transparent 55%),
    radial-gradient(ellipse 50% 40% at 85% 50%, rgba(56, 189, 248, 0.03), transparent 50%),
    linear-gradient(
      180deg,
      rgba(6, 10, 20, 0.82) 0%,
      rgba(6, 10, 20, 0.65) 35%,
      rgba(6, 10, 20, 0.72) 65%,
      rgba(6, 10, 20, 0.85) 100%
    );
}

.cockpit-shell__bg::after {
  content: '';
  position: absolute;
  inset: 0;
  opacity: 0.07;
  background-image:
    linear-gradient(rgba(34, 211, 238, 0.12) 1px, transparent 1px),
    linear-gradient(90deg, rgba(34, 211, 238, 0.08) 1px, transparent 1px);
  background-size: 96px 96px;
}

.cockpit-shell__scan {
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  background: linear-gradient(
    180deg,
    transparent 0%,
    rgba(34, 211, 238, 0.018) 47%,
    rgba(56, 189, 248, 0.025) 50%,
    transparent 53%
  );
  background-size: 100% 280%;
  animation: cockpit-scan 18s linear infinite;
  opacity: 0.45;
}

@keyframes cockpit-scan {
  0% { background-position: 0% 0%; }
  100% { background-position: 0% 100%; }
}

.cockpit-top {
  position: relative;
  z-index: 2;
  display: grid;
  grid-template-columns: 1fr minmax(200px, 420px) 1fr;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
  margin-bottom: 8px;
  padding: 2px 0 6px;
}

.cockpit-top__side { display: flex; align-items: center; min-height: 36px; }
.cockpit-top__side--left { justify-content: flex-start; }
.cockpit-top__side--right { justify-content: flex-end; gap: 12px; flex-wrap: wrap; }

.cockpit-top__tag {
  font-size: 10px;
  letter-spacing: 0.28em;
  color: var(--sx-text-tag);
  text-transform: uppercase;
}

.cockpit-top__center { text-align: center; }

.cockpit-top__title-line {
  height: 1px;
  width: min(72%, 220px);
  margin: 0 auto 8px;
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(56, 189, 248, 0.2) 15%,
    rgba(103, 232, 249, 0.7) 40%,
    rgba(56, 189, 248, 0.8) 60%,
    rgba(56, 189, 248, 0.2) 85%,
    transparent 100%
  );
  box-shadow:
    0 0 8px rgba(34, 211, 238, 0.35),
    0 0 20px rgba(34, 211, 238, 0.12);
  border-radius: 1px;
}

.cockpit-top__title-line--short {
  width: min(40%, 120px);
  margin: 8px auto 0;
  opacity: 0.5;
}

.cockpit-top__title {
  font-size: clamp(18px, 2.4vw, 26px);
  font-weight: 700;
  letter-spacing: 0.22em;
  color: #f8fafc;
  text-shadow:
    0 0 20px rgba(34, 211, 238, 0.3),
    0 1px 4px rgba(0, 0, 0, 0.5);
  margin: 0;
  line-height: 1.2;
}

.cockpit-top__sub {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--sx-text-muted);
  letter-spacing: 0.06em;
}

.cockpit-top__clock-wrap { display: flex; flex-direction: column; align-items: flex-end; gap: 2px; }

.cockpit-top__clock {
  font-family: ui-monospace, 'SF Mono', Menlo, Monaco, Consolas, monospace;
  font-size: 14px;
  font-weight: 600;
  color: var(--sx-text-clock);
  text-shadow: 0 0 8px rgba(34, 211, 238, 0.45);
  letter-spacing: 0.04em;
}

.cockpit-top__clock-label {
  font-size: 9px;
  letter-spacing: 0.35em;
  color: var(--sx-warm-amber-muted);
}

.cockpit-shell__err {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 8px 12px;
  margin-bottom: 6px;
  border-radius: 6px;
  background: var(--sx-error-bg);
  border: 1px solid var(--sx-error-border);
  color: var(--sx-error-text);
  font-size: 13px;
}

.cockpit-retry { flex-shrink: 0; }

.cockpit-grid {
  position: relative;
  z-index: 2;
  flex: 1;
  min-height: 0;
  display: grid;
  gap: 10px;
}

.cockpit-grid--smart {
  grid-template-columns: 1fr 1.4fr 1fr;
  grid-template-rows: 1fr 1fr 0.85fr;
}

.cockpit-grid--ops {
  grid-template-columns: 1fr 1fr 1fr;
  grid-template-rows: 1fr 1fr 0.7fr;
}

.cockpit-grid__cell {
  min-height: 0;
  min-width: 0;
  overflow: hidden;
  display: flex;
}

.cockpit-grid__cell > * { flex: 1; min-height: 0; }

.cockpit-grid__cell--r1c1 { grid-column: 1; grid-row: 1; }
.cockpit-grid__cell--r1c2 { grid-column: 2; grid-row: 1; }
.cockpit-grid__cell--r1c3 { grid-column: 3; grid-row: 1; }
.cockpit-grid__cell--map { grid-column: 2; grid-row: 1 / 3; }
.cockpit-grid__cell--r2c1 { grid-column: 1; grid-row: 2; }
.cockpit-grid__cell--r2c3 { grid-column: 3; grid-row: 2; }
.cockpit-grid__cell--r2wide { grid-column: 1 / 3; grid-row: 2; }
.cockpit-grid__cell--r2side { grid-column: 3; grid-row: 2; }
.cockpit-grid__cell--r3c1 { grid-column: 1; grid-row: 3; }
.cockpit-grid__cell--r3c2 { grid-column: 2; grid-row: 3; }
.cockpit-grid__cell--r3c3 { grid-column: 3; grid-row: 3; }
.cockpit-grid__cell--r3trend { grid-column: 1; grid-row: 3; }
.cockpit-grid__cell--r3kpi { grid-column: 2 / 4; grid-row: 3; }

.cockpit-grid__cell--ops-hero { grid-column: 1 / 3; grid-row: 1 / 3; }
.cockpit-grid__cell--ops-rank { grid-column: 3; grid-row: 1; }
.cockpit-grid__cell--ops-goods { grid-column: 3; grid-row: 2; }
.cockpit-grid__cell--ops-intraday { grid-column: 1; grid-row: 3; }
.cockpit-grid__cell--ops-kpi { grid-column: 2 / 4; grid-row: 3; }

.cockpit-float-back {
  position: absolute;
  right: 18px;
  bottom: 52px;
  z-index: 20;
  background: var(--sx-cockpit-float-btn-bg) !important;
  border: 1px solid var(--sx-cockpit-float-btn-border) !important;
  color: var(--sx-cockpit-float-btn-color) !important;
  box-shadow: var(--sx-cockpit-float-btn-shadow);
}

.cockpit-tab-bar {
  position: relative;
  z-index: 10;
  flex-shrink: 0;
  padding: 0 12px;
  background: linear-gradient(180deg, rgba(5, 10, 25, 0.65) 0%, rgba(5, 10, 25, 0.96) 100%);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-top: 1px solid rgba(30, 144, 255, 0.12);
}

.cockpit-tab-bar__inner {
  display: flex;
  justify-content: center;
  gap: 4px;
  max-width: 640px;
  margin: 0 auto;
}

.cockpit-tab-bar__item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border: none;
  background: transparent;
  color: var(--sx-text-tab);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.3s ease;
  border-bottom: 2px solid transparent;
  position: relative;
}

.cockpit-tab-bar__item:hover {
  color: var(--sx-text-title);
}

.cockpit-tab-bar__item--active {
  color: var(--sx-text-title);
  border-bottom-color: var(--sx-primary);
  background: var(--sx-tab-active-underline);
}

.cockpit-tab-bar__item--active::after {
  content: '';
  position: absolute;
  bottom: -1px;
  left: 15%;
  right: 15%;
  height: 2px;
  background: var(--sx-primary);
  box-shadow: 0 0 10px rgba(30, 144, 255, 0.6), 0 0 20px rgba(30, 144, 255, 0.3);
  border-radius: 2px;
}

.cockpit-tab-bar__icon {
  font-size: 14px;
}

.cockpit-tab-bar__label {
  font-weight: 500;
  letter-spacing: 0.05em;
}

/* 运营指挥台 / 智能驾驶舱：恢复青金双色氛围（物联 Tab 仍为冷色 Token） */
.cockpit-root--gold-era .cockpit-shell {
  color: #e2e8f0;
}
.cockpit-root--gold-era .cockpit-shell__bg {
  background: url('/cockpit-bg.jpg') center / cover no-repeat;
  background-color: #060a14;
}
.cockpit-root--gold-era .cockpit-shell__bg::before {
  background:
    radial-gradient(ellipse 90% 60% at 50% 5%, rgba(34, 211, 238, 0.07), transparent 50%),
    radial-gradient(ellipse 50% 40% at 90% 45%, rgba(234, 179, 8, 0.025), transparent 50%),
    radial-gradient(ellipse 50% 40% at 10% 50%, rgba(34, 211, 238, 0.03), transparent 50%),
    linear-gradient(
      180deg,
      rgba(6, 10, 20, 0.82) 0%,
      rgba(6, 10, 20, 0.62) 35%,
      rgba(6, 10, 20, 0.68) 65%,
      rgba(6, 10, 20, 0.84) 100%
    );
}
.cockpit-root--gold-era .cockpit-shell__scan {
  background: linear-gradient(
    180deg,
    transparent 0%,
    rgba(34, 211, 238, 0.015) 47%,
    rgba(234, 179, 8, 0.012) 50%,
    transparent 53%
  );
}
.cockpit-root--gold-era .cockpit-top__tag {
  color: rgba(125, 211, 252, 0.6);
}
.cockpit-root--gold-era .cockpit-top__title-line {
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(234, 179, 8, 0.3) 15%,
    rgba(234, 179, 8, 0.65) 30%,
    rgba(103, 232, 249, 0.8) 50%,
    rgba(59, 130, 246, 0.5) 70%,
    rgba(59, 130, 246, 0.2) 85%,
    transparent 100%
  );
  box-shadow:
    0 0 10px rgba(34, 211, 238, 0.3),
    0 0 18px rgba(234, 179, 8, 0.08);
}
.cockpit-root--gold-era .cockpit-top__title {
  color: #f8fafc;
  text-shadow:
    0 0 20px rgba(34, 211, 238, 0.28),
    0 0 30px rgba(234, 179, 8, 0.1),
    0 1px 4px rgba(0, 0, 0, 0.5);
}
.cockpit-root--gold-era .cockpit-top__sub {
  color: rgba(148, 163, 184, 0.9);
}
.cockpit-root--gold-era .cockpit-top__clock {
  color: #a5f3fc;
  text-shadow: 0 0 8px rgba(34, 211, 238, 0.45);
}
.cockpit-root--gold-era .cockpit-top__clock-label {
  color: rgba(234, 179, 8, 0.72);
}
.cockpit-root--gold-era .cockpit-tab-bar__item--active {
  border-bottom-color: rgba(250, 204, 21, 0.55);
  background: linear-gradient(
    180deg,
    transparent 0%,
    rgba(234, 179, 8, 0.07) 40%,
    rgba(30, 144, 255, 0.06) 100%
  );
}
.cockpit-root--gold-era .cockpit-tab-bar__item--active::after {
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(234, 179, 8, 0.95) 35%,
    rgba(56, 189, 248, 0.95) 65%,
    transparent 100%
  );
  box-shadow:
    0 0 10px rgba(234, 179, 8, 0.4),
    0 0 14px rgba(30, 144, 255, 0.35);
}
.cockpit-root--gold-era .cockpit-float-back {
  background: linear-gradient(180deg, rgba(234, 179, 8, 0.18), rgba(30, 144, 255, 0.28)) !important;
  border: 1px solid rgba(234, 179, 8, 0.45) !important;
  color: #ecfeff !important;
  box-shadow:
    0 0 12px rgba(234, 179, 8, 0.2),
    0 0 14px rgba(30, 144, 255, 0.25);
}

@media (max-width: 900px) {
  .cockpit-grid--smart,
  .cockpit-grid--ops {
    grid-template-columns: 1fr;
    grid-template-rows: auto;
  }
  .cockpit-grid__cell--map {
    grid-column: 1;
    grid-row: auto;
    min-height: 360px;
  }
  .cockpit-grid__cell--r1c1,
  .cockpit-grid__cell--r1c2,
  .cockpit-grid__cell--r1c3,
  .cockpit-grid__cell--r2c1,
  .cockpit-grid__cell--r2c3,
  .cockpit-grid__cell--r2wide,
  .cockpit-grid__cell--r2side,
  .cockpit-grid__cell--r3c1,
  .cockpit-grid__cell--r3c2,
  .cockpit-grid__cell--r3c3,
  .cockpit-grid__cell--r3trend,
  .cockpit-grid__cell--r3kpi,
  .cockpit-grid__cell--ops-hero,
  .cockpit-grid__cell--ops-rank,
  .cockpit-grid__cell--ops-goods,
  .cockpit-grid__cell--ops-intraday,
  .cockpit-grid__cell--ops-kpi {
    grid-column: 1;
    grid-row: auto;
    min-height: 200px;
  }
  .cockpit-top { grid-template-columns: 1fr; text-align: center; }
  .cockpit-top__side--left,
  .cockpit-top__side--right { justify-content: center; }
}
</style>