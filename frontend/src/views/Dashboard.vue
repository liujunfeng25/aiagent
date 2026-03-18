<template>
  <div class="dashboard">
    <h2 class="page-title">工作台</h2>
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-card">
            <span class="stat-value">{{ stats.model_count }}</span>
            <span class="stat-label">模型数量</span>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-card">
            <span class="stat-value">{{ stats.dataset_count }}</span>
            <span class="stat-label">数据集数量</span>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-card">
            <span class="stat-value">{{ stats.task_count }}</span>
            <span class="stat-label">训练任务数</span>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-card">
            <span class="stat-value">{{ stats.inference_today }}</span>
            <span class="stat-label">今日推理次数</span>
          </div>
        </el-card>
      </el-col>
    </el-row>
    <el-row :gutter="16" style="margin-top: 16px;">
      <el-col :span="12">
        <el-card>
          <template #header>训练趋势（近7天）</template>
          <div ref="trendChartRef" style="height: 280px;"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>Top 5 模型</template>
          <div ref="topChartRef" style="height: 280px;"></div>
        </el-card>
      </el-col>
    </el-row>
    <el-card style="margin-top: 16px;">
      <template #header>最近任务</template>
      <el-table :data="recentTasks" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="status" label="状态">
          <template #default="{ row }">
            <el-tag :type="row.status === 'done' ? 'success' : row.status === 'error' ? 'danger' : 'info'" size="small">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="200">
          <template #default="{ row }">{{ formatBeijingTime(row.created_at) }}</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import * as echarts from 'echarts'
import { getStats, getTrainTrend, getTopModels, getRecentTasks } from '../api/dashboard'
import { formatBeijingTime } from '../utils/format'

const stats = ref({ model_count: 0, dataset_count: 0, task_count: 0, inference_today: 0 })
const recentTasks = ref([])
const trendChartRef = ref(null)
const topChartRef = ref(null)

const load = async () => {
  try {
    stats.value = await getStats()
    const trend = await getTrainTrend()
    const top = await getTopModels()
    recentTasks.value = (await getRecentTasks()).data || []
    if (trendChartRef.value) {
      const chart = echarts.init(trendChartRef.value)
      chart.setOption({
        xAxis: { type: 'category', data: (trend.data || []).map(d => d.date) },
        yAxis: { type: 'value' },
        series: [{ type: 'line', data: (trend.data || []).map(d => d.count), smooth: true }],
      })
    }
    if (topChartRef.value) {
      const chart = echarts.init(topChartRef.value)
      const d = top.data || []
      chart.setOption({
        xAxis: { type: 'category', data: d.map(m => m.name || `模型${m.id}`) },
        yAxis: { type: 'value', max: 1 },
        series: [{ type: 'bar', data: d.map(m => m.accuracy || 0) }],
      })
    }
  } catch (e) {
    console.error(e)
    if (trendChartRef.value) {
      const chart = echarts.init(trendChartRef.value)
      chart.setOption({ xAxis: { data: [] }, yAxis: {}, series: [{ type: 'line', data: [1,3,2,5,4,6,8] }] })
    }
    if (topChartRef.value) {
      const chart = echarts.init(topChartRef.value)
      chart.setOption({ xAxis: { data: ['占位A','占位B'] }, yAxis: {}, series: [{ type: 'bar', data: [0.92, 0.88] }] })
    }
  }
}
onMounted(load)
</script>

<style scoped>
.page-title { margin-bottom: 16px; font-size: 20px; }
.stat-card { text-align: center; }
.stat-value { font-size: 28px; font-weight: bold; color: #1890ff; display: block; }
.stat-label { font-size: 14px; color: #666; }
</style>
