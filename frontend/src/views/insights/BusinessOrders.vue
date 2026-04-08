<template>
  <div class="biz-insight">
    <el-alert
      v-if="errorMsg"
      type="warning"
      :closable="false"
      class="insight-alert"
      :title="errorMsg"
      show-icon
    />
    <div v-if="metaHint" class="range-hint-row">
      <span class="range-hint">{{ metaHint }}</span>
      <el-tooltip placement="top" :show-after="200" :max-width="320">
        <template #content>
          <div class="boss-tip-text">
            本页数字来自公司日常在用的订货与结算系统：按客户实际下单日期汇总订单笔数和成交金额；下方会员排名为同一时间段内各客户成交总额从高到低排列，与业务台账口径一致。
          </div>
        </template>
        <span class="source-tip-hit" tabindex="0" role="button" aria-label="数据来源说明">
          <el-icon class="source-tip-icon"><InfoFilled /></el-icon>
        </span>
      </el-tooltip>
    </div>

    <el-card shadow="never" class="filter-card">
      <el-form inline class="filter-form" @submit.prevent>
        <el-form-item label="日期范围">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始"
            end-placeholder="结束"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="loadAll">刷新</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-row :gutter="16" class="kpi-row">
      <el-col :span="8">
        <div class="kpi-tile">
          <div class="kpi-value">{{ fmtInt(summary.order_count) }}</div>
          <div class="kpi-label">区间订单数</div>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="kpi-tile">
          <div class="kpi-value">{{ fmtMoney(summary.gmv) }}</div>
          <div class="kpi-label">区间成交额（元）</div>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="kpi-tile">
          <div class="kpi-value">{{ seriesDays }}</div>
          <div class="kpi-label">有数据天数</div>
        </div>
      </el-col>
    </el-row>

    <el-card class="chart-card" shadow="never">
      <template #header>
        <span class="card-title">订单与成交额走势</span>
        <span class="card-hint">按下单时间、订单金额汇总，最长可查近一年</span>
      </template>
      <div ref="chartRef" class="chart-box" />
    </el-card>

    <el-card class="table-card" shadow="never">
      <template #header>
        <span class="card-title">会员成交额 Top</span>
      </template>
      <el-table :data="topRows" stripe max-height="320" size="small" empty-text="暂无数据">
        <el-table-column prop="member_name" label="会员" min-width="120" show-overflow-tooltip />
        <el-table-column prop="member_id" label="ID" width="90" />
        <el-table-column prop="order_count" label="订单数" width="100" />
        <el-table-column prop="gmv" label="成交额" width="120">
          <template #default="{ row }">{{ fmtMoney(row.gmv) }}</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { InfoFilled } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { ordersDaily, ordersTopMembers } from '../../api/insightsBusiness'

const dateRange = ref([])
const loading = ref(false)
const errorMsg = ref('')
const series = ref([])
const topRows = ref([])
const metaHint = ref('')
const summary = reactive({ order_count: 0, gmv: 0 })

const chartRef = ref(null)
let chartInst = null
let chartResizeObserver = null

const seriesDays = computed(() => series.value.filter((r) => r.day).length)

function defaultRange() {
  const end = new Date()
  const start = new Date()
  start.setDate(start.getDate() - 29)
  const f = (d) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  return [f(start), f(end)]
}

function fmtInt(n) {
  if (n == null || Number.isNaN(Number(n))) return '—'
  return Number(n).toLocaleString('zh-CN')
}

function fmtMoney(n) {
  if (n == null || Number.isNaN(Number(n))) return '—'
  return Number(n).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function parseErr(e) {
  if (typeof e === 'string') return e
  if (e && e.detail) {
    return Array.isArray(e.detail) ? e.detail.map((x) => x.msg || x).join('; ') : String(e.detail)
  }
  return String((e && e.message) || e || '请求失败')
}

function buildChart() {
  if (!chartRef.value) return
  if (!chartInst) chartInst = echarts.init(chartRef.value)
  const days = series.value.map((r) => String(r.day || '').slice(0, 10))
  const counts = series.value.map((r) => r.order_count ?? 0)
  const gmvs = series.value.map((r) => r.gmv ?? 0)
  const axisLabel = 'rgba(226, 232, 240, 0.95)'
  chartInst.setOption({
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.94)',
      borderColor: 'rgba(34, 211, 238, 0.35)',
      textStyle: { color: '#e2e8f0', fontSize: 12 },
    },
    legend: { data: ['订单数', '成交额'], bottom: 0, textStyle: { color: axisLabel, fontWeight: 500 } },
    grid: { left: 48, right: 48, top: 24, bottom: 56 },
    xAxis: {
      type: 'category',
      data: days,
      axisLabel: { rotate: 28, color: axisLabel },
      axisLine: { lineStyle: { color: 'rgba(34,211,238,0.2)' } },
    },
    yAxis: [
      {
        type: 'value',
        name: '单数',
        nameTextStyle: { color: axisLabel },
        axisLabel: { color: axisLabel },
        splitLine: { lineStyle: { type: 'dashed', color: 'rgba(34,211,238,0.08)' } },
      },
      {
        type: 'value',
        name: '元',
        nameTextStyle: { color: axisLabel },
        axisLabel: { color: axisLabel },
        splitLine: { show: false },
      },
    ],
    series: [
      { name: '订单数', type: 'bar', data: counts, itemStyle: { color: '#3b82f6' } },
      { name: '成交额', type: 'line', smooth: true, yAxisIndex: 1, data: gmvs, itemStyle: { color: '#10b981' } },
    ],
  })
  fitChartToContainer()
}

function ensureChartResizeObserver() {
  chartResizeObserver?.disconnect()
  const el = chartRef.value
  if (!el || !chartInst) return
  chartResizeObserver = new ResizeObserver(() => chartInst?.resize())
  chartResizeObserver.observe(el)
}

function fitChartToContainer() {
  nextTick(() => {
    requestAnimationFrame(() => {
      chartInst?.resize()
      ensureChartResizeObserver()
    })
  })
}

function resize() {
  if (chartInst) chartInst.resize()
}

async function loadAll() {
  errorMsg.value = ''
  loading.value = true
  const dr = dateRange.value
  const params =
    dr && dr.length === 2 ? { start_date: dr[0], end_date: dr[1] } : {}
  try {
    const [d1, d2] = await Promise.all([ordersDaily(params), ordersTopMembers({ ...params, limit: 15 })])
    series.value = d1.series || []
    Object.assign(summary, d1.summary || { order_count: 0, gmv: 0 })
    topRows.value = d2.rows || []
    metaHint.value = `统计区间 ${d1.start_date} ~ ${d1.end_date}（服务端最长 ${d1.max_range_days || 366} 天）`
    await nextTick()
    buildChart()
  } catch (e) {
    errorMsg.value = parseErr(e)
    series.value = []
    topRows.value = []
    metaHint.value = ''
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  dateRange.value = defaultRange()
  loadAll()
  window.addEventListener('resize', resize)
})

onUnmounted(() => {
  window.removeEventListener('resize', resize)
  chartResizeObserver?.disconnect()
  chartResizeObserver = null
  if (chartInst) {
    chartInst.dispose()
    chartInst = null
  }
})
</script>

<style scoped>
.biz-insight {
  padding-bottom: 16px;
}
.insight-alert {
  margin-bottom: 12px;
}
.range-hint-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px 10px;
  margin: 0 0 12px;
}
.range-hint {
  font-size: 13px;
  font-weight: 500;
  color: var(--sx-text-readable-muted);
  text-shadow: var(--sx-text-shadow-readable);
}
.source-tip-hit {
  display: inline-flex;
  align-items: center;
  cursor: help;
  outline: none;
}
.source-tip-icon {
  color: #7dd3fc;
  font-size: 16px;
}
.source-tip-hit:hover .source-tip-icon,
.source-tip-hit:focus-visible .source-tip-icon {
  color: #bae6fd;
}
.boss-tip-text {
  line-height: 1.55;
  font-size: 13px;
}
.filter-card {
  border-radius: var(--sx-radius-panel);
  margin-bottom: 16px;
  border: 1px solid var(--sx-glass-border);
  background: var(--sx-content-card-bg);
  box-shadow: var(--sx-panel-shadow);
  backdrop-filter: blur(12px);
}
.filter-card :deep(.el-card__body) {
  background: transparent;
}
/* 与 .main 内全域表单标签色一致（勿再用浅底+浅字） */
.filter-card :deep(.el-form-item__label) {
  color: var(--sx-text-readable-muted) !important;
  font-weight: 600;
}
.filter-card :deep(.el-date-editor) {
  --el-input-text-color: var(--sx-text-body);
  --el-input-bg-color: rgba(15, 23, 42, 0.75);
  --el-input-border-color: var(--sx-edge-cyan-mid);
}
.filter-card :deep(.el-range-separator) {
  color: var(--sx-text-readable-muted);
}
.filter-form {
  margin-bottom: 0;
}
.kpi-row {
  margin-bottom: 16px;
}
.kpi-tile {
  background: rgba(12, 18, 40, 0.82);
  border: 1px solid var(--sx-glass-border);
  border-radius: var(--sx-radius-panel);
  padding: 16px;
  text-align: center;
  backdrop-filter: blur(8px);
}
.kpi-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--sx-text-bright);
}
.kpi-label {
  margin-top: 8px;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--sx-text-body);
  text-shadow: var(--sx-text-shadow-readable);
}
.chart-card,
.table-card {
  border-radius: var(--sx-radius-panel);
  margin-bottom: 16px;
}
.chart-card :deep(.el-card__header),
.table-card :deep(.el-card__header) {
  border-bottom-color: var(--sx-edge-cyan-mid);
}
.card-title {
  font-weight: 600;
  color: var(--sx-text-title);
}
.card-hint {
  margin-left: 12px;
  font-size: 12px;
  color: var(--sx-text-readable-dim);
  font-weight: normal;
}
.chart-box {
  width: 100%;
  height: 360px;
}
</style>
