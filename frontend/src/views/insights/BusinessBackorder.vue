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
    <div class="range-hint-row">
      <span v-if="metaHint" class="range-hint">{{ metaHint }}</span>
      <span v-else class="range-hint range-hint--muted">选择日期后点击「刷新」查看统计区间</span>
      <el-tooltip placement="top" :show-after="200" :max-width="320">
        <template #content>
          <div class="boss-tip-text">
            本页统计来自公司业务系统里登记的缺货、补货（背单）记录：按单据生成日期汇总笔数与涉及金额，最长可查近一年。用于观察缺货压力变化，具体执行以仓库与采购流程为准。
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
          <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-row :gutter="16" class="kpi-row">
      <el-col :span="8">
        <div class="kpi-tile">
          <div class="kpi-value">{{ fmtInt(summary.backorder_count) }}</div>
          <div class="kpi-label">区间背单数</div>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="kpi-tile">
          <div class="kpi-value">{{ fmtMoney(summary.amount_sum) }}</div>
          <div class="kpi-label">区间金额合计（元）</div>
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
        <span class="card-title">缺货 / 背单走势</span>
        <span class="card-hint">按背单生成日期汇总，最长近一年</span>
      </template>
      <div ref="chartRef" class="chart-box" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { InfoFilled } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { backorderDaily } from '../../api/insightsBusiness'

const dateRange = ref([])
const loading = ref(false)
const errorMsg = ref('')
const series = ref([])
const metaHint = ref('')
const summary = reactive({ backorder_count: 0, amount_sum: 0 })

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
  const cnts = series.value.map((r) => r.backorder_count ?? 0)
  const amts = series.value.map((r) => r.amount_sum ?? 0)
  chartInst.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['背单数', '金额'], bottom: 0 },
    grid: { left: 48, right: 48, top: 24, bottom: 56 },
    xAxis: { type: 'category', data: days, axisLabel: { rotate: 28 } },
    yAxis: [
      { type: 'value', name: '笔数', splitLine: { lineStyle: { type: 'dashed' } } },
      { type: 'value', name: '元', splitLine: { show: false } },
    ],
    series: [
      { name: '背单数', type: 'bar', data: cnts, itemStyle: { color: '#f59e0b' } },
      { name: '金额', type: 'line', smooth: true, yAxisIndex: 1, data: amts, itemStyle: { color: '#ef4444' } },
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

async function load() {
  errorMsg.value = ''
  loading.value = true
  const dr = dateRange.value
  const params =
    dr && dr.length === 2 ? { start_date: dr[0], end_date: dr[1] } : {}
  try {
    const res = await backorderDaily(params)
    series.value = res.series || []
    Object.assign(summary, res.summary || { backorder_count: 0, amount_sum: 0 })
    metaHint.value = `统计区间 ${res.start_date} ~ ${res.end_date}（最长 ${res.max_range_days || 366} 天）`
    await nextTick()
    buildChart()
  } catch (e) {
    errorMsg.value = parseErr(e)
    series.value = []
    metaHint.value = ''
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  dateRange.value = defaultRange()
  load()
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
  color: #64748b;
}
.range-hint--muted {
  color: #94a3b8;
}
.source-tip-hit {
  display: inline-flex;
  align-items: center;
  cursor: help;
  outline: none;
}
.source-tip-icon {
  color: #94a3b8;
  font-size: 16px;
}
.source-tip-hit:hover .source-tip-icon,
.source-tip-hit:focus-visible .source-tip-icon {
  color: #64748b;
}
.boss-tip-text {
  line-height: 1.55;
  font-size: 13px;
}
.filter-card {
  border-radius: 12px;
  margin-bottom: 16px;
}
.kpi-row {
  margin-bottom: 16px;
}
.kpi-tile {
  background: linear-gradient(180deg, #fffbeb 0%, #fef3c7 100%);
  border: 1px solid #fde68a;
  border-radius: 12px;
  padding: 16px;
  text-align: center;
}
.kpi-value {
  font-size: 22px;
  font-weight: 700;
  color: #78350f;
}
.kpi-label {
  margin-top: 6px;
  font-size: 13px;
  color: #92400e;
}
.chart-card {
  border-radius: 12px;
}
.card-title {
  font-weight: 600;
  color: #334155;
}
.card-hint {
  margin-left: 12px;
  font-size: 12px;
  color: #94a3b8;
  font-weight: normal;
}
.chart-box {
  width: 100%;
  height: 360px;
}
</style>
