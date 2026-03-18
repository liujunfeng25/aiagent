<template>
  <div>
    <h2 class="page-title">模型库</h2>
    <el-card>
      <el-table :data="list" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="val_acc" label="验证准确率">
          <template #default="{ row }">{{ (row.val_acc * 100 || 0).toFixed(1) }}%</template>
        </el-table-column>
        <el-table-column prop="deployed" label="部署">
          <template #default="{ row }">
            <el-tag v-if="row.deployed" type="success" size="small">已部署</el-tag>
            <el-tag v-else size="small">未部署</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="200">
          <template #default="{ row }">{{ formatBeijingTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="openRename(row)">重命名</el-button>
            <el-button v-if="!row.deployed" size="small" type="primary" @click="doDeploy(row)">部署</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
    <el-dialog v-model="renameVisible" title="重命名模型" width="400" @close="renameForm.name = ''">
      <el-form label-width="80px">
        <el-form-item label="新名称">
          <el-input v-model="renameForm.name" placeholder="输入模型名称" maxlength="200" show-word-limit clearable />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="renameVisible = false">取消</el-button>
        <el-button type="primary" :loading="renameLoading" @click="doRename">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { list as fetchList, deploy, rename as renameApi } from '../api/models'
import { formatBeijingTime } from '../utils/format'

const list = ref([])
const renameVisible = ref(false)
const renameLoading = ref(false)
const renameForm = ref({ id: null, name: '' })

const load = async () => {
  list.value = (await fetchList()).data || []
}
const openRename = (row) => {
  renameForm.value = { id: row.id, name: row.name }
  renameVisible.value = true
}
const doRename = async () => {
  const name = renameForm.value.name?.trim()
  if (!name) {
    ElMessage.warning('请输入名称')
    return
  }
  renameLoading.value = true
  try {
    await renameApi(renameForm.value.id, name)
    ElMessage.success('已修改')
    renameVisible.value = false
    load()
  } catch (e) {
    ElMessage.error(e.message || e.detail || '修改失败')
  } finally {
    renameLoading.value = false
  }
}
const doDeploy = async (row) => {
  await deploy(row.id)
  ElMessage.success('部署成功')
  load()
}
onMounted(load)
</script>

<style scoped>
.page-title { margin-bottom: 16px; font-size: 20px; }
</style>
