<template>
  <div>
    <h2 class="page-title">系统管理</h2>
    <el-card>
      <el-table :data="logs" stripe>
        <el-table-column label="时间" width="220">
          <template #default="{ row }">{{ formatBeijingTime(row.time) }}</template>
        </el-table-column>
        <el-table-column prop="action" label="操作" width="150" />
        <el-table-column prop="detail" label="详情" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getLogs } from '../api/system'
import { formatBeijingTime } from '../utils/format'

const logs = ref([])

const load = async () => {
  const res = await getLogs()
  logs.value = res.data || []
}
onMounted(load)
</script>

<style scoped>
.page-title { margin-bottom: 16px; font-size: 20px; }
</style>
