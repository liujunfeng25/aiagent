<template>
  <div>
    <h2 class="page-title">分析中心</h2>
    <el-card>
      <el-form :inline="true">
        <el-form-item label="数据源">
          <el-select v-model="dataSourceId" placeholder="选择数据源" style="width: 200px;">
            <el-option v-for="d in dataSources" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
        </el-form-item>
        <el-form-item><el-button type="primary" @click="runQuery">执行查询</el-button></el-form-item>
      </el-form>
      <el-input v-model="sql" type="textarea" :rows="4" placeholder="输入 SELECT 查询，例如：SELECT * FROM table LIMIT 10" style="margin-top: 8px;" />
      <el-table :data="resultRows" stripe style="margin-top: 16px;">
        <el-table-column v-for="col in resultColumns" :key="col" :prop="col" :label="col" show-overflow-tooltip />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { runQuery as apiRunQuery } from '../api/analysis'
import { list as listDataSources } from '../api/datasources'

const dataSources = ref([])
const dataSourceId = ref(null)
const sql = ref('')
const resultColumns = ref([])
const resultRows = ref([])

const load = async () => {
  dataSources.value = (await listDataSources()).data || []
}
const runQuery = async () => {
  if (!dataSourceId.value || !sql.value.trim()) {
    ElMessage.warning('请选择数据源并输入 SQL')
    return
  }
  try {
    const res = await apiRunQuery({ data_source_id: dataSourceId.value, sql: sql.value })
    resultColumns.value = res.columns || []
    resultRows.value = res.rows || []
    ElMessage.success('查询成功')
  } catch (e) {
    ElMessage.error(e.message || '查询失败')
  }
}
onMounted(load)
</script>

<style scoped>
.page-title { margin-bottom: 16px; font-size: 20px; }
</style>
