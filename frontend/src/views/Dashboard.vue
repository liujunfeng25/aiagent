<template>
  <div class="dashboard">
    <AiPageHeader
      title="AI 工作台"
      subtitle="平台状态总览 · 训练推理一体化编排 · 智能任务协同"
    >
      <template #actions>
        <RealtimeSignal status="ok" label="服务正常" />
        <el-button type="primary" @click="$router.push('/training')">训练一个模型</el-button>
      </template>
    </AiPageHeader>

    <div class="quick-actions">
      <el-button plain @click="$router.push('/models')">部署模型</el-button>
      <el-button plain @click="$router.push('/recognition')">运行推理</el-button>
      <el-button plain @click="$router.push('/cockpit')">查看监控</el-button>
      <el-button plain @click="$router.push('/insights')">业务洞察</el-button>
    </div>

    <div class="metrics-grid">
      <InferenceMetric label="模型数量" :value="stats.model_count" :show-trend="false" />
      <InferenceMetric label="数据集数量" :value="stats.dataset_count" :show-trend="false" />
      <InferenceMetric label="训练任务数" :value="stats.task_count" :show-trend="false" />
      <InferenceMetric label="今日推理次数" :value="stats.inference_today" :show-trend="false" />
    </div>

    <div class="model-grid">
      <ModelStatusCard name="图像分类模型-A" version="v2.1.3" accuracy="96.2" status="ok" status-label="已部署" />
      <ModelStatusCard name="票据识别模型-B" version="v1.8.0" accuracy="93.8" status="warn" status-label="观察中" />
      <ModelStatusCard name="物流预测模型-C" version="v1.4.6" accuracy="91.5" status="ok" status-label="已部署" />
    </div>

    <el-row :gutter="16" style="margin-top: 12px;">
      <el-col :span="12">
        <el-card class="ai-card">
          <template #header>训练趋势（近7天）</template>
          <div ref="trendChartRef" style="height: 280px;"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card class="ai-card">
          <template #header>Top 5 模型</template>
          <div ref="topChartRef" style="height: 280px;"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="ai-card" style="margin-top: 14px;">
      <template #header>任务流转时间线</template>
      <el-timeline>
        <el-timeline-item
          v-for="row in recentTasks.slice(0, 6)"
          :key="row.id"
          :timestamp="formatBeijingTime(row.created_at)"
          :type="row.status === 'done' ? 'success' : row.status === 'error' ? 'danger' : 'primary'"
        >
          任务 #{{ row.id }} · 状态：{{ row.status }}
        </el-timeline-item>
      </el-timeline>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import * as echarts from 'echarts'
import { getStats, getTrainTrend, getTopModels, getRecentTasks } from '../api/dashboard'
import { formatBeijingTime } from '../utils/format'
import AiPageHeader from '../components/ui/AiPageHeader.vue'
import InferenceMetric from '../components/ui/InferenceMetric.vue'
import ModelStatusCard from '../components/ui/ModelStatusCard.vue'
import RealtimeSignal from '../components/ui/RealtimeSignal.vue'

const stats = ref({
  model_count: 0,
  dataset_count: 0,
  task_count: 0,
  inference_today: 0,
})
const recentTasks = ref([])
const trendChartRef = ref(null)
const topChartRef = ref(null)

/** 深色卡片上的图表：浅色轴线/网格，避免 ECharts 默认深色字贴在深色底上看不清 */
function trendChartOption(dates, counts) {
  const axisLine = { lineStyle: { color: 'rgba(148, 163, 184, 0.45)' } }
  const axisLabel = { color: '#cbd5e1', fontSize: 11 }
  const splitLine = { lineStyle: { color: 'rgba(148, 163, 184, 0.14)' } }
  return {
    backgroundColor: 'transparent',
    grid: { left: 44, right: 20, top: 28, bottom: 28 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.94)',
      borderColor: 'rgba(56, 189, 248, 0.35)',
      textStyle: { color: '#e2e8f0', fontSize: 12 },
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLine,
      axisLabel: { ...axisLabel, rotate: dates.length > 8 ? 24 : 0 },
      axisTick: { alignWithLabel: true },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisLabel,
      splitLine,
    },
    series: [{
      type: 'line',
      data: counts,
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      lineStyle: { width: 2.5, color: '#38bdf8' },
      itemStyle: { color: '#22d3ee', borderColor: '#0c4a6e', borderWidth: 1 },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(56, 189, 248, 0.35)' },
          { offset: 1, color: 'rgba(56, 189, 248, 0.02)' },
        ]),
      },
    }],
  }
}

function topModelsChartOption(names, values) {
  const axisLine = { lineStyle: { color: 'rgba(148, 163, 184, 0.45)' } }
  const axisLabel = { color: '#cbd5e1', fontSize: 11 }
  const splitLine = { lineStyle: { color: 'rgba(148, 163, 184, 0.14)' } }
  return {
    backgroundColor: 'transparent',
    grid: { left: 48, right: 20, top: 20, bottom: names.some((n) => String(n).length > 6) ? 52 : 32 },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: 'rgba(15, 23, 42, 0.94)',
      borderColor: 'rgba(56, 189, 248, 0.35)',
      textStyle: { color: '#e2e8f0', fontSize: 12 },
      valueFormatter: (v) => (typeof v === 'number' ? v.toFixed(3) : v),
    },
    xAxis: {
      type: 'category',
      data: names,
      axisLine,
      axisLabel: { ...axisLabel, rotate: 18, interval: 0 },
    },
    yAxis: {
      type: 'value',
      max: 1,
      min: 0,
      axisLine: { show: false },
      axisLabel: {
        ...axisLabel,
        formatter: (v) => (typeof v === 'number' ? `${Math.round(v * 100)}%` : v),
      },
      splitLine,
    },
    series: [{
      type: 'bar',
      data: values,
      barMaxWidth: 36,
      itemStyle: {
        borderRadius: [4, 4, 0, 0],
        color: new echarts.graphic.LinearGradient(0, 1, 0, 0, [
          { offset: 0, color: '#0e7490' },
          { offset: 1, color: '#38bdf8' },
        ]),
      },
    }],
  }
}

const load = async () => {
  try {
    stats.value = await getStats()
    const trend = await getTrainTrend()
    const top = await getTopModels()
    recentTasks.value = (await getRecentTasks()).data || []
    if (trendChartRef.value) {
      const chart = echarts.init(trendChartRef.value)
      const rows = trend.data || []
      chart.setOption(trendChartOption(rows.map((d) => d.date), rows.map((d) => d.count)))
    }
    if (topChartRef.value) {
      const chart = echarts.init(topChartRef.value)
      const d = top.data || []
      chart.setOption(topModelsChartOption(
        d.map((m) => m.name || `模型${m.id}`),
        d.map((m) => m.accuracy || 0),
      ))
    }
  } catch (e) {
    console.error(e)
    if (trendChartRef.value) {
      const chart = echarts.init(trendChartRef.value)
      chart.setOption(trendChartOption(
        ['一', '二', '三', '四', '五', '六', '日'],
        [1, 3, 2, 5, 4, 6, 8],
      ))
    }
    if (topChartRef.value) {
      const chart = echarts.init(topChartRef.value)
      chart.setOption(topModelsChartOption(['占位A', '占位B'], [0.92, 0.88]))
    }
  }
}
onMounted(load)
</script>

<style scoped>
.dashboard { color: #e8eef8; }

.quick-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.model-grid {
  margin-top: 10px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

:deep(.ai-card) {
  border: 1px solid rgba(56, 189, 248, 0.35);
  background: linear-gradient(160deg, rgba(36, 48, 82, 0.82) 0%, rgba(24, 34, 58, 0.88) 100%);
  box-shadow: 0 0 20px rgba(30, 144, 255, 0.1);
  color: var(--ai-text-primary, #f1f5f9);
}
:deep(.ai-card .el-card__body) {
  color: var(--ai-text-secondary, #cbd5e1);
}
:deep(.ai-card .el-card__header) {
  border-bottom-color: rgba(56, 189, 248, 0.25);
  color: #f1f5f9;
  font-weight: 600;
}
:deep(.el-timeline-item__timestamp) { color: #94a3b8; font-size: 12px; }
:deep(.el-timeline-item__content) { color: #e2e8f0; }

@media (max-width: 1100px) {
  .metrics-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .model-grid { grid-template-columns: 1fr; }
}
</style>
