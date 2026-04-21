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
          <PanelRegionBeijingDistribution :data="districtRegionBarData" @district-drill="onMapDrill" />
        </div>
        <div class="cockpit-grid__cell cockpit-grid__cell--map">
          <CockpitPanel title="订单分布" title-en="ORDER DISTRIBUTION">
            <div class="cockpit-smart-map-wrap">
              <div class="cockpit-smart-map-wrap__chart">
                <CockpitBeijingMap
                  map-geo="beijing"
                  :district-map-data="districtMapHeatData"
                  :order-markers="mapMarkersInDrill"
                  :show-order-scatter="showMapOrderScatter"
                  :drill-adcode="mapDrillAdcode"
                  @drill="onMapDrill"
                  @back="onMapBack"
                  @marker-click="onMapMarkerClick"
                />
              </div>
              <aside
                class="cockpit-smart-map-wrap__aside"
                :class="mapDrillAdcode ? 'cockpit-smart-map-wrap__aside--drill' : 'cockpit-smart-map-wrap__aside--insights'"
                :aria-label="mapDrillAdcode ? '区县客户列表' : '区县洞察与客单价'"
              >
                <div class="cockpit-smart-map-wrap__crumb">
                  <span>北京市</span>
                  <template v-if="mapDrillName">
                    <span class="cockpit-smart-map-wrap__crumb-sep">·</span>
                    <span>{{ mapDrillName }}</span>
                  </template>
                </div>
                <template v-if="mapDrillAdcode">
                  <el-input
                    v-model="districtSearch"
                    size="small"
                    clearable
                    placeholder="搜索客户 / 地址"
                    class="cockpit-smart-map-wrap__search"
                  />
                  <el-table
                    :data="districtListFiltered"
                    size="small"
                    stripe
                    :max-height="380"
                    class="cockpit-smart-map-wrap__table"
                    highlight-current-row
                    @row-click="onDistrictTableRowClick"
                  >
                    <el-table-column prop="customer_name" label="客户" min-width="88" show-overflow-tooltip />
                    <el-table-column prop="order_count" label="订单" width="52" align="right" />
                  </el-table>
                  <p v-if="!districtListFiltered.length" class="cockpit-smart-map-wrap__empty">
                    无匹配客户
                  </p>
                </template>
                <div v-else class="cockpit-smart-map-wrap__insights">
                  <div class="cockpit-smart-map-wrap__insights-body">
                    <PanelSmartSideInsights
                      embedded
                      :payload="smartSideInsights"
                      :hint="smartMapInsightsHint"
                    />
                  </div>
                  <p class="cockpit-smart-map-wrap__hint cockpit-smart-map-wrap__hint--compact">
                    地图单击区县下钻后，在此选择客户查看订单明细。
                  </p>
                </div>
              </aside>
            </div>
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
          <PanelGrowth :metrics="growthMetrics" />
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
            :ticker-feed-items="gmvTickerFeedItems"
            :backfill-feed-items="gmvTodayBackfillItems"
            :backfill-loading="gmvTodayBackfillLoading"
            :live-ws-connected="gmvWsConnected"
            :axis-day-start-ts="gmvDayStartTs"
            :axis-max-ts="gmvAxisMaxTs"
            :live-today-patch="gmvLiveTodayPatch"
            :recent-minute-amount="gmvRecentMinuteAmount"
            :recent-minute-count="gmvRecentMinuteCount"
            :ops-alert-return-ticks="gmvOpsAlertReturnTicks"
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

    <el-drawer
      v-model="drawerOpen"
      :title="drawerTitle"
      direction="rtl"
      size="min(780px, 96vw)"
      append-to-body
      destroy-on-close
      class="cockpit-member-drawer"
    >
      <div v-if="drawerRangeLabel" class="cockpit-drawer__range">{{ drawerRangeLabel }}</div>
      <el-table
        v-loading="drawerLoading"
        :data="drawerOrders"
        size="small"
        stripe
        border
        class="cockpit-drawer__table"
        @expand-change="onDrawerExpandChange"
      >
        <el-table-column type="expand">
          <template #default="{ row }">
            <div v-loading="Boolean(expandLoading[row.id])" class="cockpit-drawer__expand">
              <el-table
                v-if="(lineItemsByOrder[row.id] || []).length"
                :data="lineItemsByOrder[row.id]"
                size="small"
                border
              >
                <el-table-column prop="goods_name" label="商品" min-width="120" show-overflow-tooltip />
                <el-table-column prop="qty" label="数量" width="88" align="right" />
                <el-table-column prop="line_amount" label="金额" width="100" align="right" />
              </el-table>
              <el-empty
                v-else-if="!expandLoading[row.id]"
                description="暂无明细"
                :image-size="64"
              />
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="order_sn" label="订单号" min-width="168" show-overflow-tooltip />
        <el-table-column label="下单时间" min-width="172">
          <template #default="{ row }">
            {{ formatOrderTime(row.add_time) }}
          </template>
        </el-table-column>
        <el-table-column prop="total_amount" label="金额" min-width="128" align="right" show-overflow-tooltip />
      </el-table>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import PanelRegionBeijingDistribution from '../components/cockpit/PanelRegionBeijingDistribution.vue'
import PanelSmartSideInsights from '../components/cockpit/PanelSmartSideInsights.vue'
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
import {
  enrichMarkersWithDistrict,
  districtChoroplethFromMarkers,
} from '../utils/beijingGeoAssign.js'
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
import { sxwLogisticsAxiosParams } from '../utils/sxwLogisticsTenant.js'

const API_BASE = '/api/insights/business'
const GEO_URL = '/geo/beijing_110000_full.json'

/** 下钻后仅当本区地址落点 ≤ 此值时绘制散点，避免过密难点击 */
const COCKPIT_MAP_SCATTER_MAX = 40

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
const mapOrderMarkers = ref([])
/** 智能驾驶舱右侧：今日重点区域 + 客单价分布（cockpit-smart-side-insights） */
const smartSideInsights = ref(null)
/** 北京区县 GeoJSON：用于点落区与 choropleth（仅智能 Tab 懒加载） */
const beijingGeoJson = ref(null)
const mapDrillAdcode = ref('')
const mapDrillName = ref('')
const districtSearch = ref('')
const kpiRange = ref(null)
const kpiToday = ref(null)
/** 智能驾驶舱 PanelKpi / PanelGrowth 用（KPI 来自 kpi-summary：订单/GMV/会员/退单等为业务库实查） */
const kpiLegacy = ref({})
/** 增长指标：今日 vs 昨日 kpi-summary 实算环比 */
const growthMetrics = ref({
  orderMomPct: null,
  gmvMomPct: null,
  buyerMomPct: null,
  returnDeltaPp: null,
})
const iotVehicles = ref([])

const drawerOpen = ref(false)
const drawerTitle = ref('')
const drawerMemberId = ref(null)
const drawerAddress = ref('')
const drawerOrders = ref([])
const drawerLoading = ref(false)
const lineItemsByOrder = ref({})
const expandLoading = ref({})

const iotDeviceStatus = ref({})
const iotAllCameras = ref([])
const iotCameraList = ref([])
const iotDeviceBindings = ref([])
const iotTempHumidity = ref([])
const iotWarehouses = ref([])

/** 仅在需要地图/物联车辆时拉 GeoJSON，避免默认运营台也解析 ~100KB+ 区界 */
let geoJsonCache = null
async function ensureGeoAndVehicles() {
  if (iotVehicles.value.length) return
  if (!geoJsonCache) {
    try {
      const r = await fetch(GEO_URL)
      if (r.ok) geoJsonCache = await r.json()
    } catch {
      geoJsonCache = null
    }
  }
  if (!geoJsonCache) return
  if (!iotVehicles.value.length) {
    iotVehicles.value = generateMockVehiclesInBeijing(28, geoJsonCache)
  }
}

watch(activeTab, (k) => {
  if (k === 'iot' || k === 'iot3d') void ensureGeoAndVehicles()
  if (k === 'smart') void ensureBeijingGeoForSmartMap()
})

async function ensureBeijingGeoForSmartMap() {
  if (beijingGeoJson.value) return
  try {
    const r = await fetch(GEO_URL)
    if (r.ok) beijingGeoJson.value = await r.json()
  } catch {
    beijingGeoJson.value = null
  }
}

const mapMarkersEnriched = computed(() => {
  const raw = mapOrderMarkers.value
  const geo = beijingGeoJson.value
  if (!geo?.features?.length) {
    return raw.map((m) => ({ ...m, district_adcode: '', district_name: '' }))
  }
  return enrichMarkersWithDistrict(raw, geo)
})

const districtMapHeatData = computed(() => {
  const geo = beijingGeoJson.value
  if (!geo?.features?.length) return []
  return districtChoroplethFromMarkers(geo, mapMarkersEnriched.value)
})

/** 左侧「区域分布」：仅展示有订单的区县（与地图同源），供柱状图全量展示、无 dataZoom */
const districtRegionBarData = computed(() => {
  return districtMapHeatData.value
    .filter((d) => (Number(d.value) || 0) > 0 || (Number(d.order_sum) || 0) > 0)
    .map((d) => ({
      district_name: d.name,
      adcode: d.adcode ? String(d.adcode) : '',
      gmv: Number(d.value) || 0,
      order_count: Number(d.order_sum) || 0,
      customer_count: Number(d.customer_count) || 0,
    }))
    .sort((a, b) => b.gmv - a.gmv)
})

const mapMarkersInDrill = computed(() => {
  const ad = mapDrillAdcode.value
  if (!ad) return []
  return mapMarkersEnriched.value.filter((m) => m.district_adcode === ad)
})

const showMapOrderScatter = computed(() => {
  const n = mapMarkersInDrill.value.length
  return Boolean(mapDrillAdcode.value) && n > 0 && n <= COCKPIT_MAP_SCATTER_MAX
})

const drillDistrictCustomers = computed(() => {
  if (!mapDrillAdcode.value) return []
  return [...mapMarkersInDrill.value].sort(
    (a, b) => Number(b.order_count || 0) - Number(a.order_count || 0),
  )
})

const districtListFiltered = computed(() => {
  const q = districtSearch.value.trim().toLowerCase()
  const rows = drillDistrictCustomers.value
  if (!q) return rows
  return rows.filter((m) => {
    const name = (m.customer_name || '').toLowerCase()
    const addr = (m.address || '').toLowerCase()
    return name.includes(q) || addr.includes(q)
  })
})

function onMapDrill(payload) {
  mapDrillAdcode.value = payload?.adcode ? String(payload.adcode) : ''
  mapDrillName.value = (payload?.name || '').trim()
  districtSearch.value = ''
}

function onMapBack() {
  mapDrillAdcode.value = ''
  mapDrillName.value = ''
  districtSearch.value = ''
}

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
    return `统计区间 · ${r.start_date} ~ ${r.end_date}`
  }
  return '统计区间 · …'
})

const drawerRangeLabel = computed(() => {
  const r = kpiRange.value
  if (r?.start_date && r?.end_date) {
    return `统计区间：${r.start_date} ~ ${r.end_date}`
  }
  return ''
})

/** 智能驾驶舱：订单排名 / 单品分布 的统计区间（与接口 start/end 一致） */
const smartRankGoodsHint = computed(() => {
  const r = kpiRange.value
  if (r?.start_date && r?.end_date) {
    return `排名 · ${r.start_date} ~ ${r.end_date}`
  }
  return ''
})

/** 订单分布地图侧栏：重点区域 / 客单价（与顶栏一致为区间口径，不用「排名」） */
const smartMapInsightsHint = computed(() => {
  const r = kpiRange.value
  if (r?.start_date && r?.end_date) {
    return `统计区间 ${r.start_date} ~ ${r.end_date}`
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
  }
}

/** 环比：(今日-昨日)/昨日×100；昨日为 0 且无今日则无意义，返回 null */
function momPct(curr, prev) {
  const c = Number(curr)
  const p = Number(prev)
  if (!Number.isFinite(c) || !Number.isFinite(p)) return null
  if (p === 0) return c === 0 ? 0 : null
  return ((c - p) / p) * 100
}

/** 退货率变动：昨日% - 今日%（百分点，正数表示退货率下降） */
function computeGrowthMetrics(todayRow, yesterdayRow) {
  if (!todayRow || !yesterdayRow) {
    return { orderMomPct: null, gmvMomPct: null, buyerMomPct: null, returnDeltaPp: null }
  }
  const yRet = Number(yesterdayRow.return_rate_by_amount_pct) || 0
  const tRet = Number(todayRow.return_rate_by_amount_pct) || 0
  return {
    orderMomPct: momPct(todayRow.order_count, yesterdayRow.order_count),
    gmvMomPct: momPct(todayRow.gmv, yesterdayRow.gmv),
    buyerMomPct: momPct(todayRow.distinct_buyers, yesterdayRow.distinct_buyers),
    returnDeltaPp: yRet - tRet,
  }
}

function formatOrderTime(ts) {
  if (ts == null || ts === '') return '—'
  const n = Number(ts)
  if (!Number.isFinite(n)) return String(ts)
  const d = new Date(n * 1000)
  if (Number.isNaN(d.getTime())) return '—'
  const p = (x) => (x < 10 ? `0${x}` : `${x}`)
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

function onDistrictTableRowClick(row) {
  if (row) void onMapMarkerClick(row)
}

async function onMapMarkerClick(payload) {
  const addr = (payload.address || '').trim()
  drawerTitle.value = addr
    ? (addr.length > 44 ? `${addr.slice(0, 44)}…` : addr)
    : (payload.customer_name || '客户')
  const mc = Number(payload.member_count)
  const onlyOneMember = Number.isFinite(mc) ? mc === 1 : true
  drawerMemberId.value = onlyOneMember && payload.member_id != null ? payload.member_id : null
  drawerAddress.value = addr
  drawerOpen.value = true
  drawerLoading.value = true
  drawerOrders.value = []
  const r = kpiRange.value
  const start = r?.start_date || ''
  const end = r?.end_date || ''
  try {
    const q = new URLSearchParams()
    if (start) q.set('start_date', start)
    if (end) q.set('end_date', end)
    if (drawerMemberId.value != null && Number(drawerMemberId.value) > 0) {
      q.set('member_id', String(drawerMemberId.value))
    }
    if (drawerAddress.value) q.set('address', drawerAddress.value)
    const data = await fetchJson(`${API_BASE}/member-orders-in-range?${q.toString()}`)
    drawerOrders.value = Array.isArray(data.rows) ? data.rows : []
  } catch (e) {
    ElMessage.error(e?.message || '加载订单列表失败')
    drawerOrders.value = []
  } finally {
    drawerLoading.value = false
  }
}

async function onDrawerExpandChange(row, expandedRows) {
  if (!row?.id) return
  const opened = expandedRows.some((r) => r.id === row.id)
  if (!opened) return
  if (lineItemsByOrder.value[row.id]) return
  expandLoading.value = { ...expandLoading.value, [row.id]: true }
  try {
    const data = await fetchJson(`${API_BASE}/order-line-items?order_id=${row.id}`)
    lineItemsByOrder.value = {
      ...lineItemsByOrder.value,
      [row.id]: Array.isArray(data.rows) ? data.rows : [],
    }
  } catch {
    lineItemsByOrder.value = { ...lineItemsByOrder.value, [row.id]: [] }
  } finally {
    const next = { ...expandLoading.value }
    delete next[row.id]
    expandLoading.value = next
  }
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

function yesterdayDateStr() {
  const d = new Date()
  d.setDate(d.getDate() - 1)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

async function loadOpsData() {
  loadErrorOps.value = ''
  const today = todayDateStr()
  const isOps = activeTab.value === 'ops'
  const yday = yesterdayDateStr()

  /** 与区间 KPI 同一窗口，保证地图/抽屉与 kr 一致 */
  let krRangePrefetch = null
  let rangeQuery = ''
  if (!isOps) {
    void ensureBeijingGeoForSmartMap()
    krRangePrefetch = await safeFetchJson(`${API_BASE}/kpi-summary?scope=range`)
    const kr0 = krRangePrefetch.ok ? krRangePrefetch.data : null
    if (kr0?.start_date && kr0?.end_date) {
      const sd = encodeURIComponent(kr0.start_date)
      const ed = encodeURIComponent(kr0.end_date)
      rangeQuery = `start_date=${sd}&end_date=${ed}`
    }
  }

  const fetches = [
    safeFetchJson(`${API_BASE}/orders-top-members${isOps ? `?start_date=${today}&end_date=${today}` : ''}`),
    safeFetchJson(`${API_BASE}/goods-top${isOps ? `?start_date=${today}&end_date=${today}` : ''}`),
    safeFetchJson(`${API_BASE}/kpi-summary?scope=today`),
  ]
  if (!isOps) {
    const mapUrl = rangeQuery
      ? `${API_BASE}/cockpit-customer-map-points?limit=300&${rangeQuery}`
      : `${API_BASE}/cockpit-customer-map-points?limit=300`
    const sideUrl = rangeQuery
      ? `${API_BASE}/cockpit-smart-side-insights?${rangeQuery}`
      : `${API_BASE}/cockpit-smart-side-insights`
    const smartTail = [
      safeFetchJson(`${API_BASE}/orders-daily`),
      safeFetchJson(mapUrl),
      Promise.resolve(krRangePrefetch),
      safeFetchJson(`${API_BASE}/kpi-summary?scope=range&start_date=${yday}&end_date=${yday}`),
      safeFetchJson(sideUrl),
    ]
    fetches.push(...smartTail)
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
    let idx = 3
    const daily = results[idx++]
    const mapPts = results[idx++]
    const kr = results[idx++]
    const ky = results[idx++]
    const side = results[idx++]
    orderTrendData.value = daily.ok && Array.isArray(daily.data?.series) ? daily.data.series : []
    mapOrderMarkers.value = mapPts.ok && Array.isArray(mapPts.data?.points) ? mapPts.data.points : []
    smartSideInsights.value = side.ok && side.data ? side.data : null
    mapDrillAdcode.value = ''
    mapDrillName.value = ''
    districtSearch.value = ''
    kpiRange.value = kr.ok && kr.data?.scope === 'range' ? kr.data : null
    if (!daily.ok) errParts.push(`订单趋势：${daily.error}`)
    if (!mapPts.ok) errParts.push(`订单分布地图：${mapPts.error}`)
    if (mapPts.ok && mapPts.data?.geocode_enabled === false) {
      errParts.push('订单分布：未配置高德 Web Key，无法解析地址坐标')
    }
    if (!kr.ok) errParts.push(`区间 KPI：${kr.error}`)
    if (!ky.ok) errParts.push(`昨日 KPI（增长指标）：${ky.error}`)
    if (!side.ok) errParts.push(`驾驶舱侧栏洞察：${side.error}`)
    syncKpiLegacy(kr, kt)
    const t = kt.ok ? kt.data : null
    const y = ky.ok ? ky.data : null
    growthMetrics.value = computeGrowthMetrics(t, y)
  } else {
    syncKpiLegacy(null, kt)
    growthMetrics.value = {
      orderMomPct: null,
      gmvMomPct: null,
      buyerMomPct: null,
      returnDeltaPp: null,
    }
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
  tickerFeedItems: gmvTickerFeedItems,
  todayBackfillItems: gmvTodayBackfillItems,
  todayBackfillLoading: gmvTodayBackfillLoading,
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
  opsAlertReturnTicks: gmvOpsAlertReturnTicks,
  reconcileHeroFromHttpIfDrift: gmvReconcileHeroFromHttp,
} = useCockpitLiveGmv(opsLiveEnabled, {
  onChartsRefresh: loadOpsData,
  refreshDebounceMs: 8000,
})
gmvLoadIntraday = gmvLoadIntradayFromComposable

/** 运营台：定时用库表 KPI 校正 WS 顶栏 GMV（多 worker 内存分叉时） */
let opsGmvDriftTimer = null
const OPS_GMV_DRIFT_POLL_MS = 20000

async function pollOpsGmvDriftReconcile() {
  if (activeTab.value !== 'ops') return
  const kt = await safeFetchJson(`${API_BASE}/kpi-summary?scope=today`)
  if (!kt.ok || kt.data?.scope !== 'today') return
  gmvReconcileHeroFromHttp(Number(kt.data.gmv), Number(kt.data.order_count))
}

watch(
  [gmvLiveTodayPatch, kpiToday, gmvWsConnected, activeTab],
  () => {
    if (activeTab.value !== 'ops' || !gmvWsConnected.value || !kpiToday.value || !gmvLiveTodayPatch.value) {
      return
    }
    const t = kpiToday.value
    gmvReconcileHeroFromHttp(Number(t.gmv), Number(t.order_count))
  },
  { deep: true },
)

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

/** 物联大屏首格：与智能物流「位置」页同源——先拉车辆列表，优先选 camera_count>0 的车，再 GET …/cameras/live。失败保持 mock。 */
async function hydrateIotCameraPreviewStream() {
  const list = iotCameraList.value
  if (!list.length) return

  try {
    const { data: vdata } = await axios.get('/api/logistics/vehicles', {
      params: sxwLogisticsAxiosParams({
        page: 1,
        page_size: 100,
        plateno: '',
      }),
    })
    if (vdata.status && vdata.status !== 200) return
    const payload = vdata.data
    const items = payload?.items || (Array.isArray(payload) ? payload : [])
    const withCam = items.find((r) => Number(r.camera_count) > 0)
    const veh = withCam || items[0]
    const vid = veh?.id
    if (vid == null || vid === '') return

    const { data } = await axios.get(`/api/logistics/vehicles/${vid}/cameras/live`, {
      params: sxwLogisticsAxiosParams(),
    })
    if (data.status && data.status !== 200) return
    const rows = data.data || []
    const row = rows.find((r) => r && !r.error && r.hls)
    if (!row) return

    const h = String(row.hls || '').trim()
    const http = h.toLowerCase().startsWith('http://') || h.toLowerCase().startsWith('https://')

    list[0] = {
      ...list[0],
      vehicle_id: vid,
      thumbUrl: '',
      status: 'online',
      streamUrl: http ? h : '',
      hls: row.hls,
      camera_source: row.camera_source,
      ys7_access_token: row.ys7_access_token,
      camera_device_id: row.camera_device_id,
      device_name: row.device_name,
      error: row.error,
    }
    const dn = (row.device_name || '').trim()
    if (dn) list[0].name = dn
  } catch (_) {
    /* 静默 */
  }
}

async function initIotMock() {
  iotDeviceStatus.value = mockDeviceStatus()
  iotAllCameras.value = mockAllCameras()
  iotCameraList.value = mockCameraList()
  iotDeviceBindings.value = mockDeviceBindings()
  iotTempHumidity.value = mockTempHumidity24h()
  iotWarehouses.value = mockWarehouses()
  await hydrateIotCameraPreviewStream()
}

onMounted(() => {
  tickClock()
  clockTimer = setInterval(tickClock, 1000)
  opsGmvDriftTimer = setInterval(() => void pollOpsGmvDriftReconcile(), OPS_GMV_DRIFT_POLL_MS)
  void initIotMock()
  /* 不 await：首屏先渲染，图表随接口返回逐项铺满，避免整页「卡死」感 */
  void loadOpsData()
})

onUnmounted(() => {
  if (clockTimer) clearInterval(clockTimer)
  if (opsGmvDriftTimer) {
    clearInterval(opsGmvDriftTimer)
    opsGmvDriftTimer = null
  }
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

.cockpit-smart-map-wrap {
  display: flex;
  flex: 1;
  min-height: 0;
  gap: 8px;
}

.cockpit-smart-map-wrap__chart {
  flex: 0 0 65%;
  max-width: 65%;
  min-width: 0;
  min-height: 220px;
}

.cockpit-smart-map-wrap__aside {
  flex: 0 0 35%;
  max-width: 35%;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
  padding: 4px 2px 4px 10px;
  border-left: 1px solid rgba(34, 211, 238, 0.15);
  font-size: 12px;
  color: rgba(203, 213, 225, 0.92);
}

.cockpit-smart-map-wrap__insights {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.cockpit-smart-map-wrap__insights-body {
  flex: 1;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
}

.cockpit-smart-map-wrap__crumb {
  font-weight: 600;
  font-size: 11px;
  letter-spacing: 0.04em;
  color: rgba(226, 232, 240, 0.95);
}

.cockpit-smart-map-wrap__crumb-sep {
  margin: 0 4px;
  opacity: 0.5;
}

.cockpit-smart-map-wrap__search {
  width: 100%;
}

.cockpit-smart-map-wrap__hint,
.cockpit-smart-map-wrap__empty {
  margin: 0;
  font-size: 11px;
  line-height: 1.45;
  color: rgba(148, 163, 184, 0.88);
}

.cockpit-smart-map-wrap__hint--compact {
  flex-shrink: 0;
  margin-top: 4px;
  font-size: 10px;
  opacity: 0.9;
}

.cockpit-smart-map-wrap__table {
  width: 100%;
}

.cockpit-smart-map-wrap__table :deep(.el-table__row) {
  cursor: pointer;
}

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

  .cockpit-smart-map-wrap {
    flex-direction: column;
  }
  .cockpit-smart-map-wrap__aside {
    width: 100%;
    border-left: none;
    border-top: 1px solid rgba(34, 211, 238, 0.12);
    padding: 10px 0 0;
  }
}
</style>