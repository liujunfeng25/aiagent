<template>
  <div class="split-demo">
    <AiPageHeader
      title="智能分单系统"
      subtitle="内置多因子智能调度引擎：融合历史履约、价格信号与地理可达性，由算法在多目标约束下自动求解供货组合；输出可解释、可追溯，确认后同步协同待办（本地留存）。"
    />

    <el-alert
      type="info"
      show-icon
      :closable="false"
      class="split-demo__alert"
      title="使用说明"
      description="可多选订单后「智能分单」：结果仍按供货方分组（表格含订单号）。可限制每品最多供货方数。"
    />

    <el-card shadow="never" class="split-demo__card">
      <div class="split-demo__body">
        <div
          v-if="loading"
          class="split-demo__loading-mask"
          role="status"
          aria-live="polite"
        >
          <div
            class="split-demo__loading-mask-bg"
            :style="{ backgroundImage: `url(${smartSplitLoadingBg})` }"
            aria-hidden="true"
          />
          <div class="split-demo__loading-mask-inner">
            <el-icon class="split-demo__loading-icon is-loading" :size="36">
              <Loading />
            </el-icon>
            <p class="split-demo__loading-text">算法引擎正在加载......</p>
          </div>
        </div>

        <div v-show="!loading" class="split-demo__body-content">
        <template v-if="seed.orders?.length">
          <div
            v-if="!selectableOrders.length"
            class="split-demo__all-confirmed-hint"
          >
            当前抽样订单均已确认分单；可点击「重新加载」刷新列表。
          </div>
          <div class="split-demo__toolbar-rows">
            <div class="split-demo__field split-demo__field--order">
              <span class="split-demo__label">选择订单（可多选）</span>
              <div class="split-demo__order-tools">
                <el-select
                  v-model="selectedOrderIds"
                  multiple
                  filterable
                  collapse-tags
                  collapse-tags-tooltip
                  :max-collapse-tags="2"
                  placeholder="已确认分单的订单不会出现"
                  class="split-demo__order-select"
                  popper-class="split-demo__order-select-dropdown"
                  :fit-input-width="false"
                  :disabled="!selectableOrders.length"
                  @change="onOrdersSelectionChange"
                >
                  <el-option
                    v-for="o in selectableOrders"
                    :key="o.id"
                    :label="orderOptionLabel(o)"
                    :value="o.id"
                  />
                </el-select>
                <div class="split-demo__order-quick">
                  <el-button
                    type="primary"
                    link
                    :disabled="!selectableOrders.length"
                    @click="selectAllSelectableOrders"
                  >
                    全选
                  </el-button>
                  <el-button
                    type="primary"
                    link
                    :disabled="!selectedOrderIds.length"
                    @click="clearOrderSelection"
                  >
                    清空
                  </el-button>
                </div>
              </div>
            </div>
            <div class="split-demo__toolbar-row2">
              <el-button
                type="primary"
                :disabled="analyzing || !selectableOrders.length || !selectedOrders.length"
                @click="runSmartSplit"
              >
                智能分单
              </el-button>
              <div class="split-demo__field split-demo__field--compact">
                <span class="split-demo__label">每品最多供货方</span>
                <el-select v-model="suppliersCap" class="split-demo__cap-select" :disabled="analyzing">
                  <el-option :value="1" label="1 家" />
                  <el-option :value="2" label="2 家" />
                  <el-option :value="3" label="3 家" />
                </el-select>
              </div>
              <div class="split-demo__field split-demo__field--grow">
                <span class="split-demo__label">分配策略</span>
                <el-radio-group v-model="strategy" class="split-demo__radios">
                  <el-radio-button
                    v-for="s in seed.strategies"
                    :key="s.key"
                    :label="s.key"
                  >
                    {{ s.label }}
                  </el-radio-button>
                </el-radio-group>
              </div>
            </div>
          </div>

          <div v-if="selectedOrders.length" class="split-demo__summary">
            <span><strong>已选 {{ selectedOrders.length }} 单</strong></span>
            <span
              v-for="o in selectedOrders"
              :key="o.id"
              class="split-demo__summary-chip"
            >
              {{ o.order_sn }} · {{ o.customer_name }}
            </span>
          </div>

          <template v-if="groupedResults.length">
            <div class="split-demo__result">
              <div class="split-demo__result-head">
                <h3 class="split-demo__h3">分单结果</h3>
                <p class="split-demo__result-tech">
                  食迅智能分单引擎 · 多因子加权 · 最大余额法整数拆分 · 可限每品供货方数 · 高德直线运距
                </p>
              </div>
              <div
                v-for="grp in groupedResults"
                :key="grp.supplier_key"
                class="split-demo__group"
              >
                <div class="split-demo__group-head">
                  <span class="split-demo__group-title">{{ grp.supplier_name }}</span>
                  <span class="split-demo__group-addr">{{ grp.supplier_address }}</span>
                </div>
                <el-table
                  :data="grp.rows"
                  stripe
                  border
                  size="small"
                  class="split-demo__table"
                >
                  <el-table-column
                    v-if="showOrderColumn"
                    prop="source_order_sn"
                    label="订单号"
                    min-width="120"
                    show-overflow-tooltip
                  />
                  <el-table-column prop="goods_name" label="商品" min-width="160" show-overflow-tooltip />
                  <el-table-column label="评分" width="72" align="center">
                    <template #default="{ row }">
                      {{ row.supplier_rating != null ? `${row.supplier_rating}★` : '—' }}
                    </template>
                  </el-table-column>
                  <el-table-column label="报价(元)" width="100" align="right">
                    <template #default="{ row }">
                      {{ row.unit_quote != null ? row.unit_quote : '—' }}
                    </template>
                  </el-table-column>
                  <el-table-column label="运距(km)" width="92" align="right">
                    <template #default="{ row }">
                      {{ row.distance_km != null ? row.distance_km : '—' }}
                    </template>
                  </el-table-column>
                  <el-table-column
                    label="本行加权占比(%)"
                    width="118"
                    align="right"
                    show-overflow-tooltip
                  >
                    <template #header>
                      <span title="与整数拆分前权重一致，四舍五入后可能与件数比例略有差异">本行加权占比(%)</span>
                    </template>
                    <template #default="{ row }">
                      {{ row.alloc_share_pct != null ? row.alloc_share_pct : '—' }}
                    </template>
                  </el-table-column>
                  <el-table-column
                    label="本品报价与运距对比"
                    min-width="220"
                  >
                    <template #header>
                      <span
                        :title="
                          seed.strict_supplier_goods
                            ? '本行各供方有效报价及运距（由业务数据算出）'
                            : '演示报价下的比价参考（截断显示）'
                        "
                        >本品报价与运距对比</span
                      >
                    </template>
                    <template #default="{ row }">
                      <el-tooltip
                        v-if="row.peer_quotes_text"
                        :content="row.peer_quotes_text"
                        effect="dark"
                        placement="top"
                        :show-after="200"
                        popper-class="split-demo__peer-tooltip-popper"
                      >
                        <span class="split-demo__peer-ellipsis">{{
                          row.peer_quotes_text
                        }}</span>
                      </el-tooltip>
                      <span v-else class="split-demo__peer-ellipsis">—</span>
                    </template>
                  </el-table-column>
                  <el-table-column prop="need_qty" label="本品需求合计" width="120" align="right" />
                  <el-table-column prop="qty" label="本单分配量" width="110" align="right" />
                  <el-table-column prop="unit" label="单位" width="72" align="center" />
                </el-table>
              </div>
              <div class="split-demo__confirm-row">
                <el-button
                  type="success"
                  :loading="confirming"
                  :disabled="analyzing || !resultRows.length"
                  @click="onConfirmSplit"
                >
                  确认分单
                </el-button>
              </div>
            </div>
          </template>
        </template>

        <el-empty
          v-else
          description="暂无可用订单（需配置业务库且订单含多条明细行）"
        >
          <el-button type="primary" @click="loadSeed">重新加载</el-button>
        </el-empty>

        </div>
      </div>

      <teleport to="body">
        <transition name="fade">
          <div v-if="analyzing" class="split-demo__overlay" role="status" aria-live="polite">
            <div class="split-demo__overlay-card">
              <div class="split-demo__pulse" />
              <p class="split-demo__overlay-title">{{ analyzeStepText }}</p>
              <el-progress :percentage="analyzeProgress" :show-text="false" />
              <p class="split-demo__overlay-sub">智能分单引擎</p>
            </div>
          </div>
        </transition>
      </teleport>
    </el-card>

  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import AiPageHeader from '../components/ui/AiPageHeader.vue'
import smartSplitLoadingBg from '../assets/smart-split-loading-bg.png'
import {
  fetchSmartSplitSeed,
  confirmSmartSplit,
  fetchSmartSplitConfirmed,
} from '../api/governanceDemo.js'

const ANALYZE_STEPS = [
  '智能分析中…',
  '正在读取供应商报价…',
  '正在计算距离权重…',
  '正在综合评分排序…',
  '分配方案生成中…',
]
const STEP_MS = 720
const ORDER_LABEL_MAX = 56
const PEER_QUOTES_MAX = 8

const loading = ref(true)
const seed = ref({
  orders: [],
  suppliers: [],
  strategies: [],
  demo_note: '',
  strict_supplier_goods: false,
})
const selectedOrderIds = ref([])
const suppliersCap = ref(2)
const strategy = ref('composite')
const analyzing = ref(false)
const analyzeStepText = ref(ANALYZE_STEPS[0])
const analyzeProgress = ref(0)
const resultRows = ref([])
const confirming = ref(false)
const blockedOrderIds = ref(new Set())
const blockedOrderSns = ref(new Set())

const selectableOrders = computed(() => {
  const orders = seed.value.orders || []
  const idSet = blockedOrderIds.value
  const snSet = blockedOrderSns.value
  return orders.filter((o) => {
    const id = Number(o.id)
    const sn = String(o.order_sn ?? '').trim()
    if (Number.isFinite(id) && idSet.has(id)) return false
    if (sn && snSet.has(sn)) return false
    return true
  })
})

const selectedOrders = computed(() => {
  const list = selectableOrders.value
  const idSet = new Set(selectedOrderIds.value)
  return list.filter((o) => idSet.has(o.id))
})

const showOrderColumn = computed(() => {
  const sns = resultRows.value.map((r) => r.source_order_sn).filter(Boolean)
  return new Set(sns).size > 1
})

watch(
  selectableOrders,
  (list) => {
    const valid = new Set(list.map((o) => o.id))
    const next = selectedOrderIds.value.filter((id) => valid.has(id))
    if (next.length === 0 && list.length) {
      selectedOrderIds.value = [list[0].id]
    } else {
      selectedOrderIds.value = next
    }
  },
  { immediate: true },
)

const groupedResults = computed(() => {
  const m = new Map()
  for (const row of resultRows.value) {
    const key = row.supplier_key
    if (!m.has(key)) {
      m.set(key, {
        supplier_key: key,
        supplier_name: row.supplier_name,
        supplier_address: row.supplier_address,
        rows: [],
      })
    }
    m.get(key).rows.push(row)
  }
  return Array.from(m.values())
})

function orderOptionLabel(o) {
  const sn = String(o?.order_sn ?? '')
  const cn = String(o?.customer_name ?? '')
  const tail = cn.length > ORDER_LABEL_MAX ? `${cn.slice(0, ORDER_LABEL_MAX)}…` : cn
  return `${sn} · ${tail}`
}

function allocateInteger(total, weights) {
  const n = weights.length
  if (n === 0 || total <= 0) return []
  const s = weights.reduce((a, b) => a + b, 0)
  if (s <= 0) return weights.map(() => 0)
  const raw = weights.map((w) => (total * w) / s)
  const floors = raw.map((x) => Math.floor(x))
  let rem = total - floors.reduce((a, b) => a + b, 0)
  const frac = raw.map((r, i) => ({ i, f: r - floors[i] }))
  frac.sort((a, b) => b.f - a.f)
  for (let k = 0; k < rem; k += 1) {
    floors[frac[k % n].i] += 1
  }
  return floors
}

function lineGoodsQuoteKey(line) {
  if (line.goods_id != null && line.goods_id !== '') return String(line.goods_id)
  return line.goods_name
}

function lineQuoteOrNull(line, s) {
  const k = lineGoodsQuoteKey(line)
  const v = s.quote_by_goods?.[k]
  if (v != null && Number(v) > 0) return Number(v)
  return null
}

function effectiveDistanceKm(order, s) {
  const m = order?.supplier_distance_km
  const sid = String(s.id)
  if (m && typeof m[sid] === 'number' && !Number.isNaN(m[sid])) {
    return Math.max(m[sid], 0.5)
  }
  return Math.max(Number(s.distance_km) || 1, 0.5)
}

function buildWeights(line, suppliers, strat, order) {
  return suppliers.map((s) => {
    const qn = lineQuoteOrNull(line, s)
    if (qn == null) return 0
    const quote = qn
    const km = order ? effectiveDistanceKm(order, s) : Math.max(Number(s.distance_km) || 1, 0.5)
    let w = 1
    if (strat === 'composite') {
      const r = Number(s.rating) || 3
      w =
        Math.pow(Math.max(r, 0.1), 1.2) *
        (1 / Math.max(quote, 1e-6)) *
        (1 / Math.max(km, 1e-6))
    } else if (strat === 'rating') {
      const r = Number(s.rating) || 3
      w = r * r
    } else if (strat === 'price') {
      w = 1 / Math.max(quote, 1e-6)
    } else {
      w = 1 / Math.max(km, 1e-6)
    }
    return w
  })
}

function lineScoreForSupplier(line, s, order, strat) {
  const qn = lineQuoteOrNull(line, s)
  if (qn == null) return 0
  const quote = qn
  const r = Number(s.rating) || 3
  const km = effectiveDistanceKm(order, s)
  const wqty = Math.max(1, Math.round(Number(line.qty) || 0))
  let unit = 1
  if (strat === 'composite') {
    unit =
      Math.pow(Math.max(r, 0.1), 1.2) *
      (1 / Math.max(quote, 1e-6)) *
      (1 / Math.max(km, 1e-6))
  } else if (strat === 'rating') {
    unit = r * r
  } else if (strat === 'price') {
    unit = 1 / Math.max(quote, 1e-6)
  } else {
    unit = 1 / Math.max(km, 1e-6)
  }
  return wqty * unit
}

function pickTopSuppliers(order, suppliers, strat, n = 3) {
  const sups = suppliers || []
  if (!order?.lines?.length || !sups.length) return []
  let pool = sups
  const quoted = sups.filter((s) =>
    order.lines.some((line) => lineQuoteOrNull(line, s) != null),
  )
  if (quoted.length) pool = quoted
  else return []
  const scored = pool.map((s) => {
    let score = 0
    for (const line of order.lines) {
      score += lineScoreForSupplier(line, s, order, strat)
    }
    return { s, score }
  })
  scored.sort((a, b) => b.score - a.score)
  const out = scored.slice(0, n).map((x) => x.s)
  return out.length ? out : pool.slice(0, Math.min(n, pool.length))
}

function suppliersForLineAllocation(order, line, pickedPool, allSuppliers, strat, n = 3) {
  let pool = (allSuppliers || []).filter((s) => lineQuoteOrNull(line, s) != null)
  if (!pool.length) return []
  const scored = pool.map((s) => ({
    s,
    score: lineScoreForSupplier(line, s, order, strat),
  }))
  scored.sort((a, b) => b.score - a.score)
  const out = scored.slice(0, n).map((x) => x.s)
  return out.length ? out : pool.slice(0, Math.min(n, pool.length))
}

function buildPeerQuotesText(line, order, highlightSupplierId) {
  const all = seed.value.suppliers || []
  const rows = all
    .map((s) => {
      const q = lineQuoteOrNull(line, s)
      if (q == null) return null
      const km = effectiveDistanceKm(order, s)
      return { s, q, km }
    })
    .filter(Boolean)
  rows.sort((a, b) => a.q - b.q || a.km - b.km)
  if (!rows.length) return '无有效报价'
  const parts = []
  const lim = Math.min(rows.length, PEER_QUOTES_MAX)
  for (let i = 0; i < lim; i += 1) {
    const { s, q, km } = rows[i]
    const base = `${s.name}:${Number(q).toFixed(2)}元·${Number(km).toFixed(1)}km`
    const mark = String(s.id) === String(highlightSupplierId) ? `【${base}】` : base
    parts.push(mark)
  }
  if (rows.length > PEER_QUOTES_MAX) {
    parts.push(`…共${rows.length}家`)
  }
  if (rows.length === 1) {
    return `${parts[0]}（仅一家有效报价）`
  }
  return parts.join(' / ')
}

function computeRows(order, picked, strat, nCap) {
  const rows = []
  const allSups = seed.value.suppliers || []
  if (!order?.lines?.length || !allSups.length) return rows
  const n = Math.min(Math.max(Number(nCap) || 2, 1), 3)

  for (const line of order.lines) {
    const lineSups = suppliersForLineAllocation(order, line, picked, allSups, strat, n)
    if (!lineSups.length) continue
    const Q = Math.max(1, Math.round(Number(line.qty) || 0))
    const weights = buildWeights(line, lineSups, strat, order)
    const sumW = weights.reduce((a, b) => a + b, 0)
    const parts = allocateInteger(Q, weights)
    lineSups.forEach((s, i) => {
      const q = parts[i] || 0
      if (q <= 0) return
      if (lineQuoteOrNull(line, s) == null) return
      const uq = lineQuoteOrNull(line, s)
      const dkm = effectiveDistanceKm(order, s)
      const pct = sumW > 0 ? (weights[i] / sumW) * 100 : 0
      rows.push({
        goods_name: line.goods_name,
        goods_id: line.goods_id ?? null,
        supplier_key: String(s.id),
        supplier_name: s.name,
        supplier_address: s.address || '—',
        supplier_rating: s.rating != null ? Number(s.rating) : null,
        unit_quote: uq != null ? Number(uq) : null,
        distance_km: Math.round(dkm * 100) / 100,
        alloc_share_pct: Math.round(pct * 100) / 100,
        peer_quotes_text: buildPeerQuotesText(line, order, s.id),
        need_qty: Q,
        qty: q,
        unit: line.unit_hint || '斤',
        source_order_id: order.id,
        source_order_sn: String(order.order_sn ?? order.id),
      })
    })
  }
  return rows
}

function onOrdersSelectionChange() {
  resultRows.value = []
}

function selectAllSelectableOrders() {
  selectedOrderIds.value = selectableOrders.value.map((o) => o.id)
  onOrdersSelectionChange()
}

function clearOrderSelection() {
  selectedOrderIds.value = []
  onOrdersSelectionChange()
}

async function loadConfirmed() {
  try {
    const data = await fetchSmartSplitConfirmed(100)
    const ids = Array.isArray(data.blocked_order_ids) ? data.blocked_order_ids : []
    const sns = Array.isArray(data.blocked_order_sns) ? data.blocked_order_sns : []
    blockedOrderIds.value = new Set(ids.map((x) => Number(x)).filter((n) => Number.isFinite(n)))
    blockedOrderSns.value = new Set(
      sns.map((s) => String(s).trim()).filter(Boolean),
    )
  } catch {
    blockedOrderIds.value = new Set()
    blockedOrderSns.value = new Set()
  }
}

async function loadSeed() {
  loading.value = true
  resultRows.value = []
  try {
    const data = await fetchSmartSplitSeed()
    seed.value = {
      orders: Array.isArray(data.orders) ? data.orders : [],
      suppliers: Array.isArray(data.suppliers) ? data.suppliers : [],
      strategies: Array.isArray(data.strategies) ? data.strategies : [],
      demo_note: data.demo_note || '',
      strict_supplier_goods: !!data.strict_supplier_goods,
    }
    if (data.warning && seed.value.orders.length === 0) {
      ElMessage.warning(data.demo_note || '暂无可加载数据')
    } else if (data.warning && seed.value.orders.length && !seed.value.suppliers.length) {
      ElMessage.warning(data.demo_note || '供货方主数据不足，无法分单')
    }
    if (data.strategies?.length) {
      const has = data.strategies.some((x) => x.key === strategy.value)
      if (!has) {
        strategy.value = data.strategies[0].key
      }
    }
    await loadConfirmed()
  } catch (e) {
    ElMessage.error(typeof e === 'string' ? e : '加载失败')
    seed.value = {
      orders: [],
      suppliers: [],
      strategies: [],
      demo_note: '',
      strict_supplier_goods: false,
    }
    blockedOrderIds.value = new Set()
    blockedOrderSns.value = new Set()
    selectedOrderIds.value = []
  } finally {
    loading.value = false
  }
}

async function runSmartSplit() {
  const orders = selectedOrders.value
  if (!orders.length) {
    ElMessage.info('请先选择订单')
    return
  }
  if (!seed.value.suppliers?.length) {
    ElMessage.warning('无可用供货方主数据')
    return
  }

  analyzing.value = true
  analyzeProgress.value = 0
  for (let i = 0; i < ANALYZE_STEPS.length; i += 1) {
    analyzeStepText.value = ANALYZE_STEPS[i]
    analyzeProgress.value = Math.round(((i + 1) / ANALYZE_STEPS.length) * 100)
    await new Promise((r) => setTimeout(r, STEP_MS))
  }

  const cap = Math.min(Math.max(Number(suppliersCap.value) || 2, 1), 3)
  const merged = []
  for (const order of orders) {
    const picked = pickTopSuppliers(order, seed.value.suppliers, strategy.value, cap)
    merged.push(...computeRows(order, picked, strategy.value, cap))
  }
  resultRows.value = merged
  analyzing.value = false
  analyzeProgress.value = 100
  if (!resultRows.value.length) {
    ElMessage.warning('未生成分配行')
  } else {
    ElMessage.success(`已生成 ${orders.length} 单合并分配方案`)
  }
}

function lineItemForPayload(r) {
  return {
    goods_name: r.goods_name,
    goods_id: r.goods_id,
    need_qty: r.need_qty,
    qty: r.qty,
    unit: r.unit,
    supplier_rating: r.supplier_rating,
    unit_quote: r.unit_quote,
    distance_km: r.distance_km,
    alloc_share_pct: r.alloc_share_pct,
    peer_quotes_text: r.peer_quotes_text,
    order_sn: r.source_order_sn,
  }
}

function flatLineForPayload(r) {
  return {
    goods_name: r.goods_name,
    goods_id: r.goods_id,
    supplier_name: r.supplier_name,
    supplier_address: r.supplier_address,
    need_qty: r.need_qty,
    qty: r.qty,
    unit: r.unit,
    supplier_rating: r.supplier_rating,
    unit_quote: r.unit_quote,
    distance_km: r.distance_km,
    alloc_share_pct: r.alloc_share_pct,
    peer_quotes_text: r.peer_quotes_text,
    order_sn: r.source_order_sn,
  }
}

function groupedFromRows(rows) {
  const m = new Map()
  for (const r of rows) {
    const key = r.supplier_key
    if (!m.has(key)) {
      m.set(key, {
        supplier_name: r.supplier_name,
        supplier_address: r.supplier_address,
        rows: [],
      })
    }
    m.get(key).rows.push(r)
  }
  return Array.from(m.values()).map((g) => ({
    supplier_name: g.supplier_name,
    supplier_address: g.supplier_address,
    lines: g.rows.map((r) => lineItemForPayload(r)),
  }))
}

async function onConfirmSplit() {
  if (!resultRows.value.length) {
    ElMessage.info('请先生成分配方案')
    return
  }
  const byOrder = new Map()
  for (const r of resultRows.value) {
    const oid = r.source_order_id
    if (oid == null) continue
    if (!byOrder.has(oid)) byOrder.set(oid, [])
    byOrder.get(oid).push(r)
  }
  if (!byOrder.size) {
    ElMessage.info('分配行缺少订单信息')
    return
  }
  confirming.value = true
  try {
    for (const [orderId, rows] of byOrder) {
      const order = seed.value.orders.find((o) => o.id === orderId)
      if (!order) {
        ElMessage.error(`未找到订单 ${orderId}`)
        return
      }
      const grouped = groupedFromRows(rows)
      await confirmSmartSplit({
        order_id: orderId,
        order_sn: String(order.order_sn ?? orderId),
        customer_name: String(order.customer_name ?? '—'),
        customer_address: String(order.member_address ?? '').trim(),
        strategy: strategy.value,
        demo_note: seed.value.demo_note || '',
        lines: rows.map((r) => flatLineForPayload(r)),
        grouped,
      })
    }
    resultRows.value = []
    ElMessage.success('已确认并存入协同待办')
    await loadConfirmed()
  } catch (e) {
    const msg = typeof e === 'string' ? e : '确认失败'
    if (msg.includes('已确认分单') || msg.includes('不可重复')) {
      ElMessage.warning(msg)
    } else {
      ElMessage.error(msg)
    }
  } finally {
    confirming.value = false
  }
}

onMounted(loadSeed)
</script>

<style scoped>
.split-demo {
  max-width: 1280px;
  margin: 0 auto;
}
.split-demo__alert {
  margin-bottom: 14px;
}
.split-demo__card {
  border-radius: 12px;
  border: 1px solid var(--sx-glass-border);
  background: var(--sx-glass-panel, rgba(15, 23, 42, 0.45));
}
.split-demo__body {
  position: relative;
  min-height: 280px;
}
.split-demo__loading-mask {
  position: absolute;
  inset: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 280px;
  border-radius: inherit;
  overflow: hidden;
}
.split-demo__loading-mask-bg {
  position: absolute;
  inset: 0;
  z-index: 0;
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
  opacity: 1;
  transform: scale(1.02);
}
.split-demo__loading-mask::after {
  content: '';
  position: absolute;
  inset: 0;
  z-index: 1;
  /* 轻罩一层保证文字可读，避免把底图压成「看不见」 */
  background: linear-gradient(
    180deg,
    rgba(2, 6, 23, 0.25) 0%,
    rgba(15, 23, 42, 0.45) 100%
  );
  pointer-events: none;
}
.split-demo__loading-mask-inner {
  position: relative;
  z-index: 2;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 18px;
  padding: 32px 40px;
  border-radius: 14px;
  border: 1px solid rgba(94, 234, 212, 0.28);
  background: rgba(15, 23, 42, 0.82);
  backdrop-filter: blur(12px);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.4);
}
.split-demo__loading-text {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #f1f5f9;
  letter-spacing: 0.12em;
}
.split-demo__loading-icon {
  color: #5eead4;
}
.split-demo__peer-ellipsis {
  display: block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: help;
}
.split-demo__all-confirmed-hint {
  margin-bottom: 12px;
  padding: 10px 12px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--sx-text-muted, #94a3b8);
  border-radius: 8px;
  border: 1px solid rgba(251, 191, 36, 0.28);
  background: rgba(120, 53, 15, 0.12);
}
.split-demo__toolbar-rows {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-bottom: 16px;
}
.split-demo__field--order {
  width: 100%;
  max-width: 720px;
}
.split-demo__order-tools {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
}
.split-demo__order-select {
  flex: 1;
  min-width: min(100%, 240px);
}
.split-demo__order-quick {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}
.split-demo__toolbar-row2 {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 14px 20px;
}
.split-demo__radios {
  flex-wrap: wrap;
}
.split-demo__field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.split-demo__field--grow {
  flex: 1;
  min-width: 200px;
}
.split-demo__label {
  font-size: 12px;
  color: var(--sx-text-muted);
  letter-spacing: 0.06em;
}
.split-demo__summary {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 20px;
  font-size: 13px;
  color: var(--sx-text-readable-dim, #cbd5e1);
  margin-bottom: 18px;
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.35);
  border: 1px solid rgba(148, 163, 184, 0.2);
}
.split-demo__summary-addr {
  flex: 1 1 100%;
  min-width: min(100%, 280px);
  line-height: 1.45;
}
.split-demo__summary-chip {
  font-size: 12px;
  color: var(--sx-text-readable-dim, #cbd5e1);
  padding: 4px 10px;
  border-radius: 8px;
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(15, 23, 42, 0.35);
}
.split-demo__field--compact {
  min-width: 120px;
}
.split-demo__cap-select {
  width: 100px;
}
.split-demo__h3 {
  margin: 0 0 10px;
  font-size: 15px;
  color: var(--sx-text-title);
}
.split-demo__result {
  margin-bottom: 24px;
}
.split-demo__result-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px 20px;
  margin-bottom: 10px;
}
.split-demo__result-head .split-demo__h3 {
  margin: 0;
}
.split-demo__result-tech {
  margin: 0;
  flex: 1;
  min-width: min(100%, 240px);
  font-size: 11px;
  line-height: 1.55;
  color: var(--sx-text-muted, #94a3b8);
  letter-spacing: 0.06em;
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid rgba(94, 234, 212, 0.18);
  background: rgba(15, 23, 42, 0.45);
}
.split-demo__group {
  margin-bottom: 16px;
}
.split-demo__group-head {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 10px;
  margin-bottom: 6px;
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.5);
  border: 1px solid rgba(148, 163, 184, 0.22);
}
.split-demo__group-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--sx-text-title);
}
.split-demo__group-addr {
  font-size: 12px;
  color: var(--sx-text-muted);
  line-height: 1.4;
}
.split-demo__table {
  width: 100%;
}
.split-demo__confirm-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px 16px;
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px solid rgba(148, 163, 184, 0.18);
}

.split-demo__overlay {
  position: fixed;
  inset: 0;
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(2, 6, 23, 0.72);
  backdrop-filter: blur(6px);
}
.split-demo__overlay-card {
  width: min(400px, 90vw);
  padding: 28px 24px;
  border-radius: 16px;
  border: 1px solid rgba(250, 204, 21, 0.25);
  background: rgba(15, 23, 42, 0.95);
  box-shadow: 0 0 40px rgba(251, 191, 36, 0.12);
}
.split-demo__pulse {
  width: 48px;
  height: 48px;
  margin: 0 auto 16px;
  border-radius: 50%;
  border: 2px solid rgba(34, 211, 238, 0.5);
  animation: split-demo-pulse 1.1s ease-in-out infinite;
}
@keyframes split-demo-pulse {
  0% {
    transform: scale(0.92);
    box-shadow: 0 0 0 0 rgba(34, 211, 238, 0.35);
  }
  50% {
    transform: scale(1);
    box-shadow: 0 0 24px 6px rgba(251, 191, 36, 0.2);
  }
  100% {
    transform: scale(0.92);
    box-shadow: 0 0 0 0 rgba(34, 211, 238, 0.35);
  }
}
.split-demo__overlay-title {
  margin: 0 0 14px;
  text-align: center;
  font-size: 16px;
  font-weight: 600;
  color: #f8fafc;
  letter-spacing: 0.02em;
}
.split-demo__overlay-sub {
  margin: 12px 0 0;
  text-align: center;
  font-size: 11px;
  color: rgba(148, 163, 184, 0.9);
  letter-spacing: 0.08em;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>

<style>
/* Teleport 到 body 的 tooltip，需非 scoped 覆盖 Element Plus 浅色气泡 */
.split-demo__peer-tooltip-popper.el-popper {
  max-width: min(560px, 92vw) !important;
  padding: 12px 14px !important;
  line-height: 1.55 !important;
  white-space: normal !important;
  word-break: break-word !important;
  color: #f1f5f9 !important;
  background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%) !important;
  border: 1px solid rgba(94, 234, 212, 0.28) !important;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.45) !important;
}
.split-demo__peer-tooltip-popper.el-popper .el-popper__arrow::before {
  background: #1e293b !important;
  border: 1px solid rgba(94, 234, 212, 0.28) !important;
}

/* 订单多选下拉 teleport 到 body：加深选项字色，避免浅灰难读 */
.split-demo__order-select-dropdown .el-select-dropdown__item {
  color: #1e293b;
  font-weight: 500;
}
.split-demo__order-select-dropdown .el-select-dropdown__item.is-hovering {
  color: #0f172a;
  font-weight: 600;
}
.split-demo__order-select-dropdown .el-select-dropdown__item.is-selected {
  color: var(--el-color-primary);
  font-weight: 600;
}
</style>
