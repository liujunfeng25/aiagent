<template>
  <div class="cockpit-root">
    <!-- Tab: Default (智能驾驶舱) -->
    <div v-if="activeTab === 'default'" class="cockpit-shell">
      <div class="cockpit-shell__bg" aria-hidden="true" />
      <div class="cockpit-shell__scan" aria-hidden="true" />

      <header class="cockpit-top">
        <div class="cockpit-top__side cockpit-top__side--left">
          <span class="cockpit-top__tag">SMART · DATA · COCKPIT</span>
        </div>
        <div class="cockpit-top__center">
          <div class="cockpit-top__title-line" />
          <h1 class="cockpit-top__title">智能驾驶舱</h1>
          <p class="cockpit-top__sub">数据可视化大屏（演示数据）</p>
          <div class="cockpit-top__title-line cockpit-top__title-line--short" />
        </div>
        <div class="cockpit-top__side cockpit-top__side--right">
          <div class="cockpit-top__clock-wrap">
            <span class="cockpit-top__clock">{{ clockText }}</span>
            <span class="cockpit-top__clock-label">LOCAL</span>
          </div>
        </div>
      </header>

      <div v-if="loadError" class="cockpit-shell__err">{{ loadError }}</div>

      <div class="cockpit-grid">
        <div class="cockpit-grid__cell cockpit-grid__cell--r1c1">
          <PanelRegion :data="regionData" />
        </div>
        <div class="cockpit-grid__cell cockpit-grid__cell--map">
          <CockpitPanel title="车辆分布" title-en="VEHICLE LOCATION">
            <BeijingMap3D :vehicles="vehicles" :drill-adcode="drillAdcode" theme="blue" @drill="onMapDrill" />
          </CockpitPanel>
        </div>
        <div class="cockpit-grid__cell cockpit-grid__cell--r1c3">
          <PanelOrderRank :data="orderRankData" />
        </div>
        <div class="cockpit-grid__cell cockpit-grid__cell--r2c1">
          <PanelOrderTrend :data="orderTrendData" />
        </div>
        <div class="cockpit-grid__cell cockpit-grid__cell--r2c3">
          <PanelGoodsPie :data="goodsData" />
        </div>
        <div class="cockpit-grid__cell cockpit-grid__cell--r3c1">
          <PanelKpi :data="kpiData" />
        </div>
        <div class="cockpit-grid__cell cockpit-grid__cell--r3c2">
          <PanelTrendLine :data="orderTrendData" />
        </div>
        <div class="cockpit-grid__cell cockpit-grid__cell--r3c3">
          <PanelGrowth :kpi="kpiData" />
        </div>
      </div>
    </div>

    <!-- Tab: Blue (经济数据大屏) -->
    <CockpitViewBlue
      v-else-if="activeTab === 'blue'"
      :vehicles="vehicles"
      :order-trend-data="orderTrendData"
      :order-rank-data="orderRankData"
      :goods-data="goodsData"
      :region-data="regionData"
      :kpi-data="kpiData"
      :clock-text="clockText"
      :drill-adcode="drillAdcode"
      :load-error="loadError"
      @drill="onMapDrill"
    />

    <!-- Tab: IoT (物联监控大屏) -->
    <CockpitViewIoT
      v-else-if="activeTab === 'iot'"
      :device-status="iotDeviceStatus"
      :all-cameras="iotAllCameras"
      :camera-list="iotCameraList"
      :device-bindings="iotDeviceBindings"
      :temp-humidity="iotTempHumidity"
      :temp-threshold="TEMP_THRESHOLD"
      :vehicles="vehicles"
      :warehouses="iotWarehouses"
      :clock-text="clockText"
      :load-error="loadError"
    />

    <el-button
      v-if="drillAdcode"
      type="primary"
      class="cockpit-float-back"
      @click="onBackCity"
    >
      返回总览
    </el-button>

    <!-- Bottom Tab Bar -->
    <nav class="cockpit-tab-bar">
      <div class="cockpit-tab-bar__inner">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          :class="['cockpit-tab-bar__item', { 'cockpit-tab-bar__item--active': activeTab === tab.key }]"
          @click="activeTab = tab.key"
        >
          <span class="cockpit-tab-bar__icon">{{ tab.icon }}</span>
          <span class="cockpit-tab-bar__label">{{ tab.label }}</span>
        </button>
      </div>
    </nav>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import CockpitPanel from '../components/cockpit/CockpitPanel.vue'
import BeijingMap3D from '../components/cockpit/BeijingMap3D.vue'
import PanelRegion from '../components/cockpit/PanelRegion.vue'
import PanelOrderRank from '../components/cockpit/PanelOrderRank.vue'
import PanelOrderTrend from '../components/cockpit/PanelOrderTrend.vue'
import PanelGoodsPie from '../components/cockpit/PanelGoodsPie.vue'
import PanelKpi from '../components/cockpit/PanelKpi.vue'
import PanelTrendLine from '../components/cockpit/PanelTrendLine.vue'
import PanelGrowth from '../components/cockpit/PanelGrowth.vue'
import CockpitViewBlue from '../components/cockpit/CockpitViewBlue.vue'
import CockpitViewIoT from '../components/cockpit/CockpitViewIoT.vue'
import { generateMockVehiclesInBeijing } from '../mock/cockpitVehicles.js'
import {
  mockOrdersDailySeries,
  mockOrdersTopMembers,
  mockGoodsTop,
  mockRegionDistribution,
  mockKpi,
} from '../mock/cockpitDashboard.js'
import {
  mockDeviceStatus,
  mockAllCameras,
  mockCameraList,
  mockDeviceBindings,
  mockTempHumidity24h,
  mockWarehouses,
  TEMP_THRESHOLD,
} from '../mock/cockpitIoT.js'

const GEO_URL = '/geo/beijing_110000_full.json'
const API_BASE = '/api/insights/business'

const activeTab = ref('default')
const tabs = [
  { key: 'default', label: '智能驾驶舱', icon: '◈' },
  { key: 'blue', label: '经济数据大屏', icon: '◉' },
  { key: 'iot', label: '物联监控大屏', icon: '◎' },
]

const loadError = ref('')
const drillAdcode = ref('')
const clockText = ref('')

const vehicles = ref([])
const orderTrendData = ref([])
const orderRankData = ref([])
const goodsData = ref([])
const regionData = ref([])
const kpiData = ref({})

const iotDeviceStatus = ref({})
const iotAllCameras = ref([])
const iotCameraList = ref([])
const iotDeviceBindings = ref([])
const iotTempHumidity = ref([])
const iotWarehouses = ref([])

let clockTimer = null

function pad2(n) { return n < 10 ? `0${n}` : `${n}` }

function tickClock() {
  const d = new Date()
  clockText.value = `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())} ${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`
}

async function fetchOrMock(url) {
  try {
    const res = await fetch(url)
    if (!res.ok) throw new Error(res.statusText)
    return await res.json()
  } catch {
    return null
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

onMounted(async () => {
  tickClock()
  clockTimer = setInterval(tickClock, 1000)

  const [geoRes, ordersRes, membersRes, goodsRes, regionRes] = await Promise.allSettled([
    fetch(GEO_URL).then((r) => r.json()),
    fetchOrMock(`${API_BASE}/orders-daily`),
    fetchOrMock(`${API_BASE}/orders-top-members`),
    fetchOrMock(`${API_BASE}/goods-top`),
    fetchOrMock(`${API_BASE}/region-distribution`),
  ])

  if (geoRes.status === 'fulfilled' && geoRes.value) {
    vehicles.value = generateMockVehiclesInBeijing(36, geoRes.value)
  }

  const ordersVal = ordersRes.status === 'fulfilled' ? ordersRes.value : null
  orderTrendData.value = ordersVal?.series?.length ? ordersVal.series : mockOrdersDailySeries()

  const membersVal = membersRes.status === 'fulfilled' ? membersRes.value : null
  orderRankData.value = membersVal?.rows?.length ? membersVal.rows : mockOrdersTopMembers()

  const goodsVal = goodsRes.status === 'fulfilled' ? goodsRes.value : null
  goodsData.value = goodsVal?.rows?.length ? goodsVal.rows : mockGoodsTop()

  const regionVal = regionRes.status === 'fulfilled' ? regionRes.value : null
  regionData.value = regionVal?.rows?.length ? regionVal.rows : mockRegionDistribution()

  if (ordersVal?.summary) {
    kpiData.value = {
      todayOrders: ordersVal.summary.order_count,
      todayGmv: ordersVal.summary.gmv,
      avgOrderAmount: ordersVal.summary.order_count ? +(ordersVal.summary.gmv / ordersVal.summary.order_count).toFixed(2) : 0,
      deliveryRate: 96.5,
      returnRate: 1.8,
      newCustomers: 12,
    }
  } else {
    kpiData.value = mockKpi()
  }

  iotDeviceStatus.value = mockDeviceStatus()
  iotAllCameras.value = mockAllCameras()
  iotCameraList.value = mockCameraList()
  iotDeviceBindings.value = mockDeviceBindings()
  iotTempHumidity.value = mockTempHumidity24h()
  iotWarehouses.value = mockWarehouses()
})

onUnmounted(() => {
  if (clockTimer) clearInterval(clockTimer)
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

/* ── Default Shell ── */
.cockpit-shell {
  position: relative;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  flex: 1;
  min-height: 0;
  padding: 10px 12px 12px;
  color: #e2e8f0;
  overflow: hidden;
}

.cockpit-shell__bg {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  background:
    radial-gradient(ellipse 100% 80% at 50% -30%, rgba(56, 189, 248, 0.10), transparent 45%),
    radial-gradient(ellipse 70% 50% at 100% 50%, rgba(234, 179, 8, 0.03), transparent 50%),
    radial-gradient(ellipse 70% 50% at 0% 50%, rgba(34, 211, 238, 0.05), transparent 50%),
    linear-gradient(180deg, #070b19 0%, #0c1225 38%, #070b19 100%);
}

.cockpit-shell__bg::after {
  content: '';
  position: absolute;
  inset: 0;
  opacity: 0.25;
  background-image:
    linear-gradient(rgba(34, 211, 238, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(34, 211, 238, 0.04) 1px, transparent 1px);
  background-size: 48px 48px;
}

.cockpit-shell__scan {
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  background: linear-gradient(180deg, transparent 0%, rgba(34, 211, 238, 0.025) 48%, rgba(234, 179, 8, 0.015) 49%, transparent 52%);
  background-size: 100% 240%;
  animation: cockpit-scan 10s linear infinite;
  opacity: 0.5;
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
  color: rgba(125, 211, 252, 0.6);
  text-transform: uppercase;
}

.cockpit-top__center { text-align: center; }

.cockpit-top__title-line {
  height: 2px;
  width: min(72%, 200px);
  margin: 0 auto 8px;
  background: linear-gradient(90deg, transparent, rgba(234, 179, 8, 0.8), rgba(34, 211, 238, 0.85), transparent);
  box-shadow: 0 0 10px rgba(34, 211, 238, 0.4);
  border-radius: 2px;
}

.cockpit-top__title-line--short {
  width: min(40%, 120px);
  margin: 8px auto 0;
  opacity: 0.7;
}

.cockpit-top__title {
  font-size: clamp(18px, 2.4vw, 26px);
  font-weight: 700;
  letter-spacing: 0.22em;
  color: #f8fafc;
  text-shadow: 0 0 18px rgba(34, 211, 238, 0.3), 0 0 36px rgba(234, 179, 8, 0.1);
  margin: 0;
  line-height: 1.2;
}

.cockpit-top__sub {
  margin: 6px 0 0;
  font-size: 12px;
  color: rgba(148, 163, 184, 0.9);
  letter-spacing: 0.06em;
}

.cockpit-top__clock-wrap { display: flex; flex-direction: column; align-items: flex-end; gap: 2px; }

.cockpit-top__clock {
  font-family: ui-monospace, 'SF Mono', Menlo, Monaco, Consolas, monospace;
  font-size: 14px;
  font-weight: 600;
  color: #a5f3fc;
  text-shadow: 0 0 8px rgba(34, 211, 238, 0.45);
  letter-spacing: 0.04em;
}

.cockpit-top__clock-label {
  font-size: 9px;
  letter-spacing: 0.35em;
  color: rgba(234, 179, 8, 0.7);
}

.cockpit-top__back {
  flex-shrink: 0;
  background: linear-gradient(180deg, rgba(234, 179, 8, 0.2), rgba(34, 211, 238, 0.25)) !important;
  border: 1px solid rgba(234, 179, 8, 0.4) !important;
  color: #ecfeff !important;
}

.cockpit-shell__err {
  position: relative;
  z-index: 2;
  padding: 8px 12px;
  margin-bottom: 6px;
  border-radius: 6px;
  background: rgba(127, 29, 29, 0.4);
  border: 1px solid rgba(248, 113, 113, 0.4);
  color: #fecaca;
  font-size: 13px;
}

.cockpit-grid {
  position: relative;
  z-index: 2;
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 1fr 1.4fr 1fr;
  grid-template-rows: 1fr 1fr 0.85fr;
  gap: 8px;
}

.cockpit-grid__cell {
  min-height: 0;
  min-width: 0;
  overflow: hidden;
  display: flex;
}

.cockpit-grid__cell > * { flex: 1; min-height: 0; }

.cockpit-grid__cell--r1c1 { grid-column: 1; grid-row: 1; }
.cockpit-grid__cell--map  { grid-column: 2; grid-row: 1 / 3; }
.cockpit-grid__cell--r1c3 { grid-column: 3; grid-row: 1; }
.cockpit-grid__cell--r2c1 { grid-column: 1; grid-row: 2; }
.cockpit-grid__cell--r2c3 { grid-column: 3; grid-row: 2; }
.cockpit-grid__cell--r3c1 { grid-column: 1; grid-row: 3; }
.cockpit-grid__cell--r3c2 { grid-column: 2; grid-row: 3; }
.cockpit-grid__cell--r3c3 { grid-column: 3; grid-row: 3; }

/* ── Bottom Tab Bar ── */
.cockpit-tab-bar {
  position: relative;
  z-index: 10;
  flex-shrink: 0;
  padding: 0 12px;
  background: linear-gradient(180deg, rgba(5, 10, 25, 0.6) 0%, rgba(5, 10, 25, 0.95) 100%);
  border-top: 1px solid rgba(30, 144, 255, 0.2);
}

.cockpit-float-back {
  position: absolute;
  right: 18px;
  bottom: 52px;
  z-index: 20;
  background: linear-gradient(180deg, rgba(30, 144, 255, 0.26), rgba(14, 116, 210, 0.32)) !important;
  border: 1px solid rgba(96, 165, 250, 0.65) !important;
  color: #e0f2fe !important;
  box-shadow: 0 0 12px rgba(30, 144, 255, 0.35);
}

.cockpit-tab-bar__inner {
  display: flex;
  justify-content: center;
  gap: 4px;
  max-width: 500px;
  margin: 0 auto;
}

.cockpit-tab-bar__item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 24px;
  border: none;
  background: transparent;
  color: rgba(140, 170, 220, 0.7);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.3s ease;
  border-bottom: 2px solid transparent;
  position: relative;
}

.cockpit-tab-bar__item:hover {
  color: #e8eef8;
}

.cockpit-tab-bar__item--active {
  color: #e8eef8;
  border-bottom-color: #1e90ff;
  background: linear-gradient(180deg, transparent 0%, rgba(30, 144, 255, 0.08) 100%);
}

.cockpit-tab-bar__item--active::after {
  content: '';
  position: absolute;
  bottom: -1px;
  left: 20%;
  right: 20%;
  height: 2px;
  background: #1e90ff;
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

@media (max-width: 900px) {
  .cockpit-grid {
    grid-template-columns: 1fr;
    grid-template-rows: auto;
  }
  .cockpit-grid__cell--map { grid-column: 1; grid-row: auto; min-height: 360px; }
  .cockpit-grid__cell--r1c1,
  .cockpit-grid__cell--r1c3,
  .cockpit-grid__cell--r2c1,
  .cockpit-grid__cell--r2c3,
  .cockpit-grid__cell--r3c1,
  .cockpit-grid__cell--r3c2,
  .cockpit-grid__cell--r3c3 {
    grid-column: 1;
    grid-row: auto;
    min-height: 200px;
  }
  .cockpit-top { grid-template-columns: 1fr; text-align: center; }
  .cockpit-top__side--left,
  .cockpit-top__side--right { justify-content: center; }
}
</style>
