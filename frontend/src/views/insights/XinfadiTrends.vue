<template>
  <div class="xfd-trends">
    <el-skeleton v-if="bootLoading" :rows="6" animated />

    <template v-else>
      <el-card v-if="sentiment.has_data || sentiment.message" class="sentiment-card" shadow="never">
        <div class="sentiment-row">
          <div class="sentiment-label">整体价格景气度</div>
          <div class="sentiment-main">
            <span v-if="sentiment.change_pct != null" class="sentiment-pct" :class="sentDirClass">
              {{ sentiment.direction === 'up' ? '↑' : sentiment.direction === 'down' ? '↓' : '→' }}
              {{ Math.abs(sentiment.change_pct).toFixed(2) }}%
            </span>
            <span v-else class="sentiment-muted">—</span>
            <span class="sentiment-msg">{{ sentiment.message }}</span>
          </div>
        </div>
      </el-card>

      <el-card class="filter-card" shadow="never">
        <el-form :inline="true" class="filter-form" @submit.prevent>
          <el-form-item label="日期范围">
            <el-date-picker
              v-model="dateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始"
              end-placeholder="结束"
              value-format="YYYY-MM-DD"
              :disabled-date="disabledDate"
            />
          </el-form-item>
          <el-form-item label="品名（精确匹配）">
            <el-select
              v-model="selectedProds"
              multiple
              filterable
              remote
              :remote-method="onProductRemoteQuery"
              :loading="productSearchLoading"
              reserve-keyword
              collapse-tags
              collapse-tags-tooltip
              placeholder="输入关键字搜索（全库匹配）"
              style="min-width: 280px"
              @visible-change="onProductDropdownVisible"
            >
              <el-option v-for="n in productOptions" :key="n" :label="n" :value="n" />
            </el-select>
          </el-form-item>
          <el-form-item label="一级分类（可选）">
            <el-input v-model="cat1" clearable placeholder="留空不限" style="width: 140px" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="chartLoading" @click="loadChart">刷新图表</el-button>
            <el-button
              type="success"
              plain
              :disabled="backfillRunning"
              @click="openBackfillDialog"
            >
              补全缺失缓存
            </el-button>
          </el-form-item>
        </el-form>
        <div class="quick-picks">
          <span class="qp-label">常用品类快捷添加：</span>
          <el-button
            v-for="p in QUICK_PRESETS"
            :key="p.label"
            size="small"
            round
            @click="addQuickPreset(p)"
          >
            {{ p.label }}
          </el-button>
        </div>
      </el-card>

      <div class="range-hint-row">
        <span class="range-hint">可选日期须在本系统已保存的行情范围内；图表按所选品种展示批发均价走势。</span>
        <el-tooltip placement="top" :show-after="200" :max-width="320">
          <template #content>
            <div class="boss-tip-text">
              本页展示新发地批发市场的公开批发报价，由系统按日抓取并保存在本机，供内部参考；「整体价格景气度」仅在两天都有报价的一级品类上比较均价变化。与订货、收银系统无关，不等同于采购结算价。
            </div>
          </template>
          <span class="source-tip-hit" tabindex="0" role="button" aria-label="数据来源说明">
            <el-icon class="source-tip-icon"><InfoFilled /></el-icon>
          </span>
        </el-tooltip>
      </div>

      <el-row :gutter="16" class="kpi-row">
        <el-col :span="6">
          <div class="kpi-tile">
            <div class="kpi-value">{{ kpi.calendarDays }}</div>
            <div class="kpi-label">统计天数</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="kpi-tile">
            <div class="kpi-value">{{ kpi.daysWithPoint }}</div>
            <div class="kpi-label">有报价点数</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="kpi-tile">
            <div class="kpi-value">{{ kpi.prodCount }}</div>
            <div class="kpi-label">品种数</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="kpi-tile">
            <div class="kpi-value">{{ kpi.lastDayAvgText }}</div>
            <div class="kpi-label">区间末日均（所选品种）</div>
          </div>
        </el-col>
      </el-row>

      <el-card class="chart-card" shadow="never">
        <template #header>
          <span class="card-title">批发均价走势</span>
          <span class="card-hint">无数据日为断点，悬停可见「无数据」</span>
        </template>
        <div ref="chartRef" class="chart-box" />
      </el-card>

      <el-collapse v-model="detailCollapse" class="detail-collapse">
        <el-collapse-item title="数据明细（运营 / 分析用，默认折叠）" name="detail">
          <el-table :data="detailRows" stripe max-height="360" size="small">
            <el-table-column prop="发布日期" label="日期" width="110" />
            <el-table-column prop="品名" label="品名" min-width="100" show-overflow-tooltip />
            <el-table-column prop="一级分类" label="一级分类" width="100" show-overflow-tooltip />
            <el-table-column prop="平均价" label="平均价" width="88" />
            <el-table-column prop="最低价" label="最低价" width="88" />
            <el-table-column prop="最高价" label="最高价" width="88" />
            <el-table-column prop="产地" label="产地" min-width="90" show-overflow-tooltip />
            <el-table-column prop="单位" label="单位" width="70" />
          </el-table>
        </el-collapse-item>
      </el-collapse>

      <el-dialog
        v-model="backfillDialogVisible"
        title="批量补抓行情"
        width="640px"
        destroy-on-close
        append-to-body
        class="backfill-dialog"
        @closed="onBackfillDialogClosed"
      >
        <div class="backfill-dialog-inner">
        <p class="bf-hint">
          按当前<strong>日期范围</strong>扫描：没有本地 JSON 文件的日期将<strong>依次</strong>调用新发地接口抓取并落盘（与「报价抓取」同源逻辑）。
          进行中时请勿在其它页面发起单日抓取。
        </p>
        <div class="bf-progress-wrap">
          <el-progress
            :percentage="Math.min(100, Math.round(backfillStatus.progress_pct || 0))"
            :status="backfillProgressStatus"
            :stroke-width="10"
          />
          <div class="bf-meta">
            <span v-if="backfillStatus.total"> {{ backfillStatus.processed || 0 }} / {{ backfillStatus.total }} 日 </span>
            <span v-if="backfillStatus.current" class="bf-current">当前：{{ backfillStatus.current }}</span>
          </div>
        </div>
        <div ref="terminalRef" class="terminal">
          <pre class="terminal-pre">{{ (backfillStatus.logs || []).join('\n') }}</pre>
        </div>
        </div>
        <template #footer>
          <el-button @click="backfillDialogVisible = false">关闭</el-button>
          <el-button
            type="primary"
            :loading="backfillStartLoading"
            :disabled="backfillRunning"
            @click="confirmStartBackfill"
          >
            {{ backfillRunning ? '抓取中…' : '开始补抓' }}
          </el-button>
        </template>
      </el-dialog>
    </template>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { InfoFilled } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import {
  getAnalyticsDates,
  getMarketSentiment,
  getProductHints,
  getTimeseries,
  postBackfill,
  getBackfillStatus,
  postBackfillDismiss,
} from '../../api/xinfadiAnalytics'

/** 常用品类快捷：与缓存品名精确一致 */
const QUICK_PRESETS = [
  { label: '大白菜', names: ['大白菜'] },
  { label: '小白菜', names: ['小白菜'] },
  { label: '圆白菜', names: ['圆白菜'] },
  { label: '娃娃菜', names: ['娃娃菜'] },
]

const bootLoading = ref(true)
const chartLoading = ref(false)
const chartRef = ref(null)
let chartInst = null
/** Tab 内隐藏时画布宽为 0；显示后需 resize + ResizeObserver */
let chartResizeObserver = null

const cachedDates = ref([])
const dateRange = ref([])
const selectedProds = ref([])
const productOptions = ref([])
const productSearchLoading = ref(false)
let productSearchTimer = null
const cat1 = ref('')
const sentiment = reactive({
  has_data: false,
  message: '',
  change_pct: null,
  direction: 'flat',
})

const tsData = ref(null)
const detailRows = ref([])
const detailCollapse = ref([])

const backfillDialogVisible = ref(false)
const backfillStatus = ref({
  running: false,
  finished: false,
  total: 0,
  processed: 0,
  success: 0,
  current: null,
  progress_pct: 0,
  logs: [],
})
const backfillStartLoading = ref(false)
const terminalRef = ref(null)
let backfillPollTimer = null

const backfillRunning = computed(() => !!backfillStatus.value.running)

const backfillProgressStatus = computed(() => {
  if (backfillStatus.value.running) return undefined
  if (backfillStatus.value.finished && (backfillStatus.value.success || 0) > 0) return 'success'
  if (backfillStatus.value.finished) return 'warning'
  return undefined
})

const kpi = reactive({
  calendarDays: 0,
  daysWithPoint: 0,
  prodCount: 0,
  lastDayAvgText: '—',
})

const sentDirClass = computed(() => {
  if (sentiment.direction === 'up') return 'dir-up'
  if (sentiment.direction === 'down') return 'dir-down'
  return 'dir-flat'
})

function disabledDate(d) {
  if (!cachedDates.value.length) return false
  const s = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  const min = cachedDates.value[0]
  const max = cachedDates.value[cachedDates.value.length - 1]
  return s < min || s > max
}

async function mergeProductHintsQuery(q) {
  productSearchLoading.value = true
  try {
    const lim = (q || '').trim() ? 800 : 800
    const res = await getProductHints({ q: q || '', limit: lim })
    const fromServer = res.names || []
    const sel = [...selectedProds.value]
    const merged = new Set([...sel, ...fromServer])
    productOptions.value = [...merged].sort((a, b) => a.localeCompare(b, 'zh-CN'))
  } catch (e) {
    console.error(e)
  } finally {
    productSearchLoading.value = false
  }
}

function onProductRemoteQuery(raw) {
  const q = (raw || '').trim()
  if (productSearchTimer) clearTimeout(productSearchTimer)
  productSearchTimer = setTimeout(() => mergeProductHintsQuery(q), 280)
}

function onProductDropdownVisible(visible) {
  if (visible && productOptions.value.length === 0) {
    mergeProductHintsQuery('')
  }
}

function addPreset(name) {
  if (!productOptions.value.includes(name)) {
    productOptions.value = [...productOptions.value, name].sort((a, b) => a.localeCompare(b, 'zh-CN'))
  }
  if (!selectedProds.value.includes(name)) {
    selectedProds.value = [...selectedProds.value, name]
  }
}

function addQuickPreset(preset) {
  const opts = new Set(productOptions.value)
  const hit = preset.names.find((n) => opts.has(n)) || preset.names[0]
  addPreset(hit)
}

function defaultDateRange() {
  const dates = cachedDates.value
  if (!dates.length) {
    const end = new Date()
    end.setDate(end.getDate() - 1)
    const start = new Date(end)
    start.setDate(start.getDate() - 29)
    return [fmt(start), fmt(end)]
  }
  const max = dates[dates.length - 1]
  const maxD = parseYmd(max)
  const startD = new Date(maxD)
  startD.setDate(startD.getDate() - 29)
  const minAvail = parseYmd(dates[0])
  if (startD < minAvail) {
    return [dates[0], max]
  }
  return [fmt(startD), max]
}

function parseYmd(s) {
  const [y, m, d] = s.split('-').map(Number)
  return new Date(y, m - 1, d)
}

function fmt(d) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function pickDefaultProds() {
  const set = new Set(productOptions.value)
  const picked = []
  for (const qp of QUICK_PRESETS) {
    const hit = qp.names.find((n) => set.has(n))
    if (hit) picked.push(hit)
  }
  if (picked.length) {
    selectedProds.value = picked
    return
  }
  if (productOptions.value.length) {
    selectedProds.value = productOptions.value.slice(0, 2)
  } else {
    selectedProds.value = []
  }
}

function fmtPrice(x) {
  if (x == null || x === '' || Number.isNaN(Number(x))) return '—'
  return Number(x).toFixed(2)
}

function updateKpi(meta, series, calendarDates) {
  kpi.calendarDays = calendarDates?.length || 0
  kpi.daysWithPoint = meta?.points_with_value ?? 0
  kpi.prodCount = meta?.prod_count ?? 0
  if (!series?.length || !calendarDates?.length) {
    kpi.lastDayAvgText = '—'
    return
  }
  const lastIdx = calendarDates.length - 1
  const parts = []
  for (const ser of series) {
    const v = ser.avg?.[lastIdx]
    if (v != null) parts.push(v)
  }
  if (!parts.length) {
    kpi.lastDayAvgText = '—'
    return
  }
  const m = parts.reduce((a, b) => a + b, 0) / parts.length
  kpi.lastDayAvgText = m.toFixed(2)
}

function buildChartOption(calendarDates, seriesList) {
  const axisLabel = 'rgba(226, 232, 240, 0.95)'
  const colors = ['#2563eb', '#0891b2', '#7c3aed', '#db2777', '#ca8a04', '#16a34a']
  const series = (seriesList || []).map((ser, idx) => ({
    name: ser.name,
    type: 'line',
    smooth: true,
    connectNulls: false,
    showSymbol: true,
    symbolSize: 5,
    lineStyle: { width: 2 },
    itemStyle: { color: colors[idx % colors.length] },
    areaStyle: {
      color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
        { offset: 0, color: `${colors[idx % colors.length]}33` },
        { offset: 1, color: `${colors[idx % colors.length]}05` },
      ]),
    },
    data: (ser.avg || []).map((v) => (v == null ? null : v)),
  }))

  return {
    color: colors,
    textStyle: { fontFamily: 'system-ui, sans-serif', color: axisLabel },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.94)',
      borderColor: 'rgba(34, 211, 238, 0.35)',
      textStyle: { color: '#e2e8f0', fontSize: 12 },
      formatter(params) {
        if (!params?.length) return ''
        const axis = params[0].axisValue
        const lines = [`<strong>${axis}</strong>`]
        for (const p of params) {
          const v = p.value
          if (v == null || v === '' || Number.isNaN(v)) {
            lines.push(`${p.marker}${p.seriesName}：无数据`)
          } else {
            const ser = seriesList.find((s) => s.name === p.seriesName)
            const i = calendarDates.indexOf(axis)
            const lo = ser?.low?.[i]
            const hi = ser?.high?.[i]
            let extra = ''
            if (lo != null && hi != null) {
              extra = `（低 ${fmtPrice(lo)} / 高 ${fmtPrice(hi)}）`
            }
            const nMerge = ser?.n?.[i] ?? 0
            const mergeHint =
              nMerge > 1 ? ` <span style="color:#94a3b8;font-size:12px">· 当日${nMerge}条报价均价合并</span>` : ''
            lines.push(`${p.marker}${p.seriesName}：${fmtPrice(v)}${extra}${mergeHint}`)
          }
        }
        return lines.join('<br/>')
      },
    },
    legend: {
      top: 8,
      type: 'scroll',
      textStyle: { color: axisLabel, fontSize: 12 },
      pageTextStyle: { color: axisLabel },
      pageIconColor: '#94a3b8',
      pageIconInactiveColor: '#475569',
    },
    grid: { left: 48, right: 24, top: 48, bottom: 80 },
    toolbox: {
      right: 16,
      iconStyle: { borderColor: 'rgba(148, 163, 184, 0.65)' },
      emphasis: { iconStyle: { borderColor: '#e2e8f0' } },
      feature: {
        saveAsImage: { title: '导出图片', name: '新发地均价走势' },
        dataZoom: { title: { zoom: '区域缩放', back: '还原' } },
      },
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: calendarDates,
      axisLabel: { rotate: 28, fontSize: 11, color: axisLabel },
      axisLine: { lineStyle: { color: 'rgba(34, 211, 238, 0.2)' } },
    },
    yAxis: {
      type: 'value',
      name: '元',
      nameTextStyle: { color: axisLabel },
      axisLabel: { color: axisLabel },
      splitLine: { lineStyle: { type: 'dashed', color: 'rgba(34, 211, 238, 0.08)' } },
    },
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      {
        type: 'slider',
        start: 0,
        end: 100,
        height: 22,
        bottom: 12,
        textStyle: { color: axisLabel },
        borderColor: 'rgba(56, 189, 248, 0.25)',
        handleStyle: { color: 'rgba(125, 211, 252, 0.85)' },
        dataBackground: {
          lineStyle: { color: 'rgba(56, 189, 248, 0.2)' },
          areaStyle: { color: 'rgba(56, 189, 248, 0.08)' },
        },
        selectedDataBackground: {
          lineStyle: { color: 'rgba(56, 189, 248, 0.45)' },
          areaStyle: { color: 'rgba(56, 189, 248, 0.18)' },
        },
      },
    ],
    series,
  }
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

function renderChart() {
  if (!chartRef.value || !tsData.value) return
  const { calendar_dates: cal, series: ser } = tsData.value
  if (!chartInst) chartInst = echarts.init(chartRef.value)
  chartInst.setOption(buildChartOption(cal || [], ser || []), true)
  fitChartToContainer()
}

function clearBackfillPoll() {
  if (backfillPollTimer) {
    clearInterval(backfillPollTimer)
    backfillPollTimer = null
  }
}

function resetBackfillDisplayIdle() {
  backfillStatus.value = {
    running: false,
    finished: false,
    total: 0,
    processed: 0,
    success: 0,
    current: null,
    progress_pct: 0,
    logs: [
      '提示：补抓只按「日期范围」检查缺失的本地 JSON，与当前选择的品名无关。',
      '点击下方「开始补抓」将先检测缺口，再逐日抓取。',
    ],
  }
}

function scrollTerminalToBottom() {
  nextTick(() => {
    const el = terminalRef.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

async function refreshAfterBackfill() {
  try {
    const dRes = await getAnalyticsDates()
    cachedDates.value = dRes.dates || []
    const sRes = await getMarketSentiment()
    Object.assign(sentiment, sRes)
    if (selectedProds.value.length) await loadChart()
  } catch (e) {
    console.error(e)
  }
}

async function openBackfillDialog() {
  if (!dateRange.value || dateRange.value.length !== 2) {
    ElMessage.warning('请先选择日期范围')
    return
  }
  backfillDialogVisible.value = true
  clearBackfillPoll()
  resetBackfillDisplayIdle()
  try {
    await postBackfillDismiss()
    const s = await getBackfillStatus()
    if (s.running) {
      backfillStatus.value = s
      scrollTerminalToBottom()
      backfillPollTimer = setInterval(async () => {
        const st = await getBackfillStatus()
        backfillStatus.value = st
        scrollTerminalToBottom()
        if (!st.running && st.finished) {
          clearBackfillPoll()
          await postBackfillDismiss()
          await refreshAfterBackfill()
          ElMessage.success('补抓结束，图表已刷新')
        }
      }, 450)
    }
  } catch (e) {
    ElMessage.error(typeof e === 'string' ? e : '读取补数状态失败')
  }
}

function onBackfillDialogClosed() {
  clearBackfillPoll()
  postBackfillDismiss().catch(() => {})
  resetBackfillDisplayIdle()
}

async function confirmStartBackfill() {
  if (!dateRange.value || dateRange.value.length !== 2) {
    ElMessage.warning('请先选择日期范围')
    return
  }
  backfillStartLoading.value = true
  clearBackfillPoll()
  try {
    const res = await postBackfill({
      start_date: dateRange.value[0],
      end_date: dateRange.value[1],
    })
    if (res.error) {
      ElMessage.error(res.error)
      resetBackfillDisplayIdle()
      backfillStatus.value.logs = [String(res.error)]
      return
    }
    if (res.started === false) {
      ElMessage.info(res.message || '无需补抓')
      resetBackfillDisplayIdle()
      backfillStatus.value.logs = [res.message || '所选区间内没有缺失的本地缓存，无需补抓']
      return
    }
    ElMessage.success(res.message || '已开始补抓')
    const st0 = await getBackfillStatus()
    backfillStatus.value = st0
    scrollTerminalToBottom()
    backfillPollTimer = setInterval(async () => {
      const st = await getBackfillStatus()
      backfillStatus.value = st
      scrollTerminalToBottom()
      if (!st.running && st.finished) {
        clearBackfillPoll()
        await postBackfillDismiss()
        await refreshAfterBackfill()
        ElMessage.success('补抓结束，图表已刷新')
      }
    }, 450)
  } catch (e) {
    ElMessage.error(typeof e === 'string' ? e : '启动失败')
    resetBackfillDisplayIdle()
    backfillStatus.value.logs = [typeof e === 'string' ? e : '启动失败']
  } finally {
    backfillStartLoading.value = false
  }
}

async function loadChart() {
  if (!dateRange.value || dateRange.value.length !== 2) {
    ElMessage.warning('请选择日期范围')
    return
  }
  if (!selectedProds.value.length) {
    ElMessage.warning('请至少选择一个品名，可使用上方快捷添加')
    return
  }
  chartLoading.value = true
  try {
    const res = await getTimeseries({
      start_date: dateRange.value[0],
      end_date: dateRange.value[1],
      prod_names: selectedProds.value,
      cat1: cat1.value,
    })
    tsData.value = res
    detailRows.value = res.details || []
    updateKpi(res.meta, res.series, res.calendar_dates)
    await nextTick()
    renderChart()
  } catch (e) {
    ElMessage.error(typeof e === 'string' ? e : e?.message || '加载失败')
  } finally {
    chartLoading.value = false
  }
}

function onResize() {
  chartInst?.resize()
}

onMounted(async () => {
  window.addEventListener('resize', onResize)
  try {
    const [dRes, sRes] = await Promise.all([
      getAnalyticsDates(),
      getMarketSentiment(),
    ])
    cachedDates.value = dRes.dates || []
    Object.assign(sentiment, sRes)
    await mergeProductHintsQuery('')
    dateRange.value = defaultDateRange()
    pickDefaultProds()
    if (selectedProds.value.length) {
      await loadChart()
    }
  } catch (e) {
    console.error(e)
    ElMessage.error('初始化数据失败')
  } finally {
    bootLoading.value = false
    await nextTick()
    if (selectedProds.value.length) renderChart()
  }
})

onUnmounted(() => {
  if (productSearchTimer) clearTimeout(productSearchTimer)
  clearBackfillPoll()
  window.removeEventListener('resize', onResize)
  chartResizeObserver?.disconnect()
  chartResizeObserver = null
  chartInst?.dispose()
  chartInst = null
})

watch(
  () => selectedProds.value.join(','),
  () => {
    nextTick(() => chartInst?.resize())
  }
)
</script>

<style scoped>
.xfd-trends {
  --insight-card-radius: 12px;
  --insight-muted: #64748b;
}

.sentiment-card {
  margin-bottom: 16px;
  border-radius: var(--insight-card-radius);
  border: 1px solid #e2e8f0;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
}
.sentiment-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px 24px;
}
.sentiment-label {
  font-size: 13px;
  font-weight: 600;
  color: #334155;
  letter-spacing: 0.02em;
}
.sentiment-main {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 12px;
}
.sentiment-pct {
  font-size: 28px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.sentiment-pct.dir-up { color: #dc2626; }
.sentiment-pct.dir-down { color: #16a34a; }
.sentiment-pct.dir-flat { color: #64748b; }
.sentiment-muted { font-size: 24px; color: #94a3b8; }
.sentiment-msg {
  font-size: 14px;
  color: #475569;
  max-width: 720px;
  line-height: 1.5;
}

.filter-card {
  margin-bottom: 16px;
  border-radius: var(--insight-card-radius);
  border: 1px solid #e2e8f0;
}
.filter-form {
  margin-bottom: 8px;
}
.quick-picks {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  padding-top: 4px;
}
.qp-label {
  font-size: 13px;
  color: var(--insight-muted);
}

.range-hint-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px 10px;
  margin: 0 0 16px;
}
.range-hint {
  font-size: 13px;
  color: var(--insight-muted);
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

.kpi-row {
  margin-bottom: 16px;
}
.kpi-tile {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: var(--insight-card-radius);
  padding: 16px 18px;
  text-align: center;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}
.kpi-value {
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
  font-variant-numeric: tabular-nums;
}
.kpi-label {
  margin-top: 6px;
  font-size: 12px;
  color: var(--insight-muted);
}

.chart-card {
  border-radius: var(--insight-card-radius);
  border: 1px solid #e2e8f0;
  margin-bottom: 16px;
}
.card-title {
  font-weight: 600;
  color: #1e293b;
}
.card-hint {
  margin-left: 12px;
  font-size: 12px;
  font-weight: normal;
  color: var(--insight-muted);
}
.chart-box {
  width: 100%;
  height: 400px;
}

.detail-collapse {
  border: none;
  background: transparent;
}
.detail-collapse :deep(.el-collapse-item__header) {
  font-size: 13px;
  color: #64748b;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 0 12px;
  background: #fff;
}
.detail-collapse :deep(.el-collapse-item__wrap) {
  border: none;
}
.detail-collapse :deep(.el-collapse-item__content) {
  padding-top: 12px;
}
</style>

<!-- el-dialog 内容 teleport 到 body，需非 scoped -->
<style>
.backfill-dialog-inner .bf-hint {
  font-size: 13px;
  color: #475569;
  line-height: 1.6;
  margin-bottom: 16px;
}
.backfill-dialog-inner .bf-progress-wrap {
  margin-bottom: 12px;
}
.backfill-dialog-inner .bf-meta {
  margin-top: 8px;
  font-size: 12px;
  color: #64748b;
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}
.backfill-dialog-inner .bf-current {
  font-family: ui-monospace, Consolas, monospace;
}
.backfill-dialog-inner .terminal {
  background: #0d1117;
  border: 1px solid #30363d;
  border-radius: 8px;
  max-height: 280px;
  overflow: auto;
  padding: 12px 14px;
}
.backfill-dialog-inner .terminal-pre {
  margin: 0;
  font-family: ui-monospace, 'Cascadia Code', Consolas, monospace;
  font-size: 12px;
  line-height: 1.55;
  color: #3fb950;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
