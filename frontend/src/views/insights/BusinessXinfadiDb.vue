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
            本曲线来自公司内部经营系统里「按日汇总」的新发地价格指数（日均高、低与样本量），由业务侧定期写入，与左侧「新发地批发价」中按品种逐条抓取的明细可能口径、时点不完全一致，适合看整体价格带走势；重大决策请与业务数据负责人核对。
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

    <el-card class="chart-card" shadow="never">
      <template #header>
        <span class="card-title">库内新发地价格指数（日均）</span>
        <span class="card-hint">公司内部按日汇总的新发地价格指数；与上方「新发地批发价」明细抓取口径可能略有差异</span>
      </template>
      <div ref="chartRef" class="chart-box" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { InfoFilled } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { xinfadiSummarySeries } from '../../api/insightsBusiness'

const dateRange = ref([])
const loading = ref(false)
const errorMsg = ref('')
const series = ref([])
const metaHint = ref('')

const chartRef = ref(null)
let chartInst = null
/** Tab 内隐藏时 ECharts 会以 0 宽初始化；显示后需 resize，并用 ResizeObserver 跟布局变化 */
let chartResizeObserver = null

function defaultRange() {
  const end = new Date()
  const start = new Date()
  start.setDate(start.getDate() - 29)
  const f = (d) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  return [f(start), f(end)]
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
  const days = series.value.map((r) => (r.day || '').toString().slice(0, 10))
  const avg = series.value.map((r) => r.avg_price ?? null)
  const minP = series.value.map((r) => r.min_price ?? null)
  const maxP = series.value.map((r) => r.max_price ?? null)
  chartInst.setOption({
    tooltip: {
      trigger: 'axis',
      formatter(params) {
        if (!params?.length) return ''
        const i = params[0].dataIndex
        const row = series.value[i] || {}
        const q = row.quantity != null ? `样本量 ${row.quantity}` : ''
        return [
          params[0].axisValue,
          ...params.map((p) => `${p.marker}${p.seriesName}: ${p.data != null ? Number(p.data).toFixed(2) : '—'}`),
          q,
        ].join('<br/>')
      },
    },
    legend: { data: ['均价', '最低价', '最高价'], bottom: 0 },
    grid: { left: 56, right: 24, top: 24, bottom: 56 },
    xAxis: { type: 'category', data: days, axisLabel: { rotate: 28 } },
    yAxis: { type: 'value', name: '价格', splitLine: { lineStyle: { type: 'dashed' } } },
    series: [
      { name: '均价', type: 'line', smooth: true, data: avg, itemStyle: { color: '#2563eb' } },
      { name: '最低价', type: 'line', smooth: true, data: minP, itemStyle: { color: '#10b981' } },
      { name: '最高价', type: 'line', smooth: true, data: maxP, itemStyle: { color: '#f97316' } },
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
  chartInst?.resize()
}

async function load() {
  errorMsg.value = ''
  loading.value = true
  const dr = dateRange.value
  const params =
    dr && dr.length === 2 ? { start_date: dr[0], end_date: dr[1] } : {}
  try {
    const res = await xinfadiSummarySeries(params)
    series.value = res.series || []
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
  chartInst?.dispose()
  chartInst = null
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
  height: 380px;
}
</style>
