<template>
  <div class="route-demo">
    <AiPageHeader title="智能排线">
      <template #actions>
        <p class="route-demo__header-note">
          高德地图 JS API 渲染；收货地址经 Web 地理编码至 GCJ-02，再按订单送货顺序对途径点分段调用驾车路径规划（AMap.Driving）并拼接折线，与左侧列表顺序一致。
        </p>
      </template>
    </AiPageHeader>

    <el-card shadow="never" class="route-demo__card">
      <div v-if="loadingDrivers" class="route-demo__loading">加载司机列表…</div>
      <template v-else>
        <p v-if="hint" class="route-demo__hint">{{ hint }}</p>
        <div class="route-demo__toolbar">
          <span class="route-demo__toolbar-label">业务日 {{ businessDate || '—' }}</span>
          <el-select
            v-model="selectedDriverKey"
            class="route-demo__driver-select"
            placeholder="请选择司机"
            filterable
            clearable
            :loading="loadingOrders"
            @change="onDriverChange"
          >
            <el-option
              v-for="d in drivers"
              :key="d.driver_key"
              :label="driverOptionLabel(d)"
              :value="d.driver_key"
            />
          </el-select>
          <el-button type="primary" link @click="loadDrivers">刷新列表</el-button>
        </div>

        <div v-if="selectedDriverKey && orders.length > 0" class="route-demo__grid">
          <div class="route-demo__table-wrap">
            <h3 class="route-demo__h3">今日送货顺序</h3>
            <p class="route-demo__sub">
              {{ customerGroups.length }} 家客户 · {{ orders.length }} 单（列表按客户分组，组内顺序与路线一致）
            </p>
            <div
              v-for="g in customerGroups"
              :key="g.customer_name"
              class="route-demo__cust-block"
            >
              <div class="route-demo__cust-head">
                <span class="route-demo__cust-name">{{ g.customer_name }}</span>
                <span class="route-demo__cust-meta">{{ g.orders.length }} 单</span>
              </div>
              <el-table
                :data="g.orders"
                stripe
                border
                size="small"
                class="route-demo__table route-demo__table--nest"
              >
                <el-table-column label="#" width="48" align="center">
                  <template #default="{ row }">
                    {{ routeSequenceNo(row) }}
                  </template>
                </el-table-column>
                <el-table-column prop="remark" label="remark" min-width="96" show-overflow-tooltip />
                <el-table-column prop="order_sn" label="订单号" min-width="120" show-overflow-tooltip />
                <el-table-column
                  prop="member_address"
                  label="收货地址"
                  min-width="200"
                  :show-overflow-tooltip="addressOverflowTooltip"
                />
              </el-table>
            </div>
          </div>
          <div class="route-demo__map-wrap">
            <h3 class="route-demo__h3">路线图（驾车路径）</h3>
            <p class="route-demo__map-hint">
              途径点标注为客户名称；坐标限定在京津冀范围内解析，雄安地址自动补「河北省」重试。路线按订单顺序分段驾车规划。
            </p>
            <AmapChainRouteMap
              :depot-address="depotAddress"
              :orders="orders"
              :ready="mapReady"
            />
          </div>
        </div>
        <el-empty
          v-else-if="!drivers.length"
          description="今日暂无符合条件的送货订单（需 send_date 为今天且 member_address 非空）"
        >
          <el-button type="primary" @click="loadDrivers">重新加载</el-button>
        </el-empty>
        <div v-else-if="loadingOrders" class="route-demo__loading">加载该司机订单…</div>
        <el-empty
          v-else-if="selectedDriverKey && !orders.length"
          description="该司机今日无符合条件的订单"
        >
          <el-button type="primary" @click="loadOrders">重新加载</el-button>
        </el-empty>
        <el-empty v-else description="请从上方下拉框选择司机，加载该司机今日订单与路线图" />
      </template>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import AiPageHeader from '../components/ui/AiPageHeader.vue'
import AmapChainRouteMap from '../components/smart-split/AmapChainRouteMap.vue'
import { fetchDeliveryRouteDrivers, fetchDeliveryRouteOrders } from '../api/governanceDemo.js'

/** 深色页面下默认 dark tooltip 对比差，收货地址用浅色高对比 */
const addressOverflowTooltip = {
  effect: 'light',
  placement: 'top',
  popperClass: 'route-demo-address-tooltip',
}

const loadingDrivers = ref(true)
const loadingOrders = ref(false)
const hint = ref('')
const depotAddress = ref('')
const businessDate = ref('')
const drivers = ref([])
const unassignedDriverKey = ref('__unassigned__')
const selectedDriverKey = ref('')
const orders = ref([])

const mapReady = computed(
  () =>
    !loadingDrivers.value
    && !loadingOrders.value
    && !!selectedDriverKey.value
    && orders.value.length > 0
    && !!depotAddress.value,
)

/** 按 API 返回顺序（remark）首次出现客户聚组，不拆散路线顺序 */
const customerGroups = computed(() => {
  const list = orders.value || []
  const keys = []
  const map = new Map()
  for (const o of list) {
    const name = String(o.customer_name ?? '—').trim() || '—'
    if (!map.has(name)) {
      keys.push(name)
      map.set(name, [])
    }
    map.get(name).push(o)
  }
  return keys.map((customer_name) => ({
    customer_name,
    orders: map.get(customer_name),
  }))
})

/** 与地图途径点顺序一致的全局序号（1…N） */
function routeSequenceNo(row) {
  const i = orders.value.findIndex((o) => o.id === row.id)
  return i >= 0 ? i + 1 : '—'
}

function driverOptionLabel(d) {
  const n = Number(d.customer_count) || 0
  if (d.driver_key === unassignedDriverKey.value || d.driver_id == null) {
    return `（未指派） · ${n} 客户`
  }
  const plate = (d.car_plate_no || '').trim() || '—'
  const phone = (d.phone || '').trim() || '—'
  return `${plate} · ${phone} · ${n} 客户`
}

async function loadDrivers() {
  loadingDrivers.value = true
  hint.value = ''
  selectedDriverKey.value = ''
  orders.value = []
  try {
    const data = await fetchDeliveryRouteDrivers()
    depotAddress.value = data.depot_address || ''
    businessDate.value = data.business_date || ''
    drivers.value = Array.isArray(data.drivers) ? data.drivers : []
    unassignedDriverKey.value = data.unassigned_driver_key || '__unassigned__'
    if (!drivers.value.length) {
      hint.value = data.demo_note || ''
    }
  } catch (e) {
    ElMessage.error(typeof e === 'string' ? e : '加载失败')
    drivers.value = []
  } finally {
    loadingDrivers.value = false
  }
}

async function loadOrders() {
  const key = selectedDriverKey.value
  if (!key) {
    orders.value = []
    return
  }
  loadingOrders.value = true
  try {
    const data = await fetchDeliveryRouteOrders(key)
    depotAddress.value = data.depot_address || depotAddress.value
    businessDate.value = data.business_date || businessDate.value
    orders.value = Array.isArray(data.orders) ? data.orders : []
    if (!orders.value.length) {
      hint.value = data.demo_note || '该司机今日无符合条件的订单'
    } else {
      hint.value = ''
    }
  } catch (e) {
    ElMessage.error(typeof e === 'string' ? e : '加载订单失败')
    orders.value = []
  } finally {
    loadingOrders.value = false
  }
}

function onDriverChange() {
  hint.value = ''
  orders.value = []
  if (selectedDriverKey.value) {
    loadOrders()
  }
}

onMounted(loadDrivers)
</script>

<style scoped>
.route-demo {
  max-width: 1400px;
  margin: 0 auto;
}
.route-demo__header-note {
  margin: 0;
  max-width: min(56ch, 52vw);
  font-size: 11px;
  line-height: 1.45;
  font-weight: 400;
  color: var(--sx-text-muted, #94a3b8);
  text-align: right;
}
@media (max-width: 720px) {
  .route-demo__header-note {
    max-width: none;
    text-align: left;
  }
}
.route-demo__card {
  border-radius: 12px;
  border: 1px solid var(--sx-glass-border);
  background: var(--sx-glass-panel, rgba(15, 23, 42, 0.45));
}
.route-demo__loading {
  padding: 24px;
  text-align: center;
  color: var(--sx-text-muted);
}
.route-demo__hint {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--sx-text-muted);
}
.route-demo__toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.route-demo__toolbar-label {
  font-size: 13px;
  color: var(--sx-text-muted);
}
.route-demo__driver-select {
  min-width: 280px;
}
.route-demo__grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  align-items: start;
}
@media (max-width: 1100px) {
  .route-demo__grid {
    grid-template-columns: 1fr;
  }
}
.route-demo__h3 {
  margin: 0 0 8px;
  font-size: 15px;
  color: var(--sx-text-title);
}
.route-demo__sub {
  margin: 0 0 10px;
  font-size: 12px;
  color: var(--sx-text-muted);
}
.route-demo__table {
  width: 100%;
}
.route-demo__table--nest {
  margin-bottom: 14px;
}
.route-demo__cust-block:last-child .route-demo__table--nest {
  margin-bottom: 0;
}
.route-demo__cust-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin: 0 0 6px;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(30, 41, 59, 0.55);
  border: 1px solid rgba(94, 234, 212, 0.15);
}
.route-demo__cust-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--sx-text-title, #e2e8f0);
}
.route-demo__cust-meta {
  font-size: 12px;
  color: var(--sx-text-muted, #94a3b8);
}
.route-demo__map-wrap {
  min-width: 0;
}
.route-demo__map-hint {
  margin: 0 0 10px;
  font-size: 12px;
  line-height: 1.45;
  color: var(--sx-text-muted, #94a3b8);
}
</style>

<style>
/* Teleport 到 body，需非 scoped；与食迅深色页面对比 */
.route-demo-address-tooltip {
  max-width: min(520px, 92vw) !important;
  padding: 10px 14px !important;
  font-size: 13px !important;
  line-height: 1.55 !important;
  color: #0f172a !important;
  background: #f8fafc !important;
  border: 1px solid #cbd5e1 !important;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.35) !important;
}
.route-demo-address-tooltip.el-popper.is-light,
.route-demo-address-tooltip.el-popper.is-light > .el-popper__arrow::before {
  border-color: #cbd5e1 !important;
}
.route-demo-address-tooltip.el-popper.is-light > .el-popper__arrow::before {
  background: #f8fafc !important;
}
</style>
