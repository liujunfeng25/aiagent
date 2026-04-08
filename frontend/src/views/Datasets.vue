<template>
  <div>
    <h2 class="page-title">数据集管理</h2>
    <el-alert
      type="info"
      show-icon
      :closable="false"
      class="page-hint"
      title="用于训练管理的图片包：上传、组合或与数据源关联。业务库联查请用「分析中心」并先配置数据源。"
    />
    <el-card>
      <div class="toolbar">
        <el-button type="primary" @click="showCreateComposite">创建组合</el-button>
      </div>
      <el-table :data="list" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="source_type" label="来源" width="100">
          <template #default="{ row }">
            <span v-if="row.source_type === 'composite'">组合 ({{ (row.source_ids || []).length }} 个源)</span>
            <span v-else>{{ row.source_type }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="row_count" label="行数" width="100" />
        <el-table-column prop="created_at" label="创建时间">
          <template #default="{ row }">
            <span class="cell-datetime">{{ row.created_at }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220">
          <template #default="{ row }">
            <el-button size="small" @click="preview(row)">预览</el-button>
            <el-button size="small" @click="showRename(row)">重命名</el-button>
            <el-button size="small" type="danger" @click="doDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
    <el-dialog v-model="previewVisible" title="数据预览" width="70%">
      <div v-if="previewData.type === 'image_folders'">
        <p>图片分类数据集，共 {{ previewData.total }} 张，类别：{{ (previewData.classes || []).join('、') }}</p>
      </div>
      <el-table v-else :data="previewData.rows || []" stripe max-height="400">
        <el-table-column v-for="col in (previewData.columns || [])" :key="col" :prop="col" :label="col" show-overflow-tooltip />
      </el-table>
    </el-dialog>

    <el-dialog v-model="renameVisible" title="重命名数据集" width="400px">
      <el-form :model="renameForm" label-width="80px">
        <el-form-item label="新名称" required>
          <el-input v-model="renameForm.name" placeholder="请输入名称" clearable />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="renameVisible = false">取消</el-button>
        <el-button type="primary" :loading="renameSubmitting" @click="submitRename">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="compositeVisible" title="创建组合数据集" width="480px">
      <el-form :model="compositeForm" label-width="100px">
        <el-form-item label="组合名称" required>
          <el-input v-model="compositeForm.name" placeholder="请输入名称" />
        </el-form-item>
        <el-form-item label="源数据集" required>
          <el-select v-model="compositeForm.sourceIds" multiple placeholder="至少选择 2 个数据集" style="width: 100%">
            <el-option
              v-for="d in compositeSourceOptions"
              :key="d.id"
              :label="`${d.name} (ID: ${d.id})`"
              :value="d.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="compositeVisible = false">取消</el-button>
        <el-button type="primary" :loading="compositeSubmitting" @click="submitComposite">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { list as fetchList, preview as fetchPreview, remove, create, update } from '../api/datasets'

const list = ref([])
const previewVisible = ref(false)
const previewData = ref({ columns: [], rows: [] })
const renameVisible = ref(false)
const renameForm = ref({ id: null, name: '' })
const renameSubmitting = ref(false)
const compositeVisible = ref(false)
const compositeForm = ref({ name: '', sourceIds: [] })
const compositeSubmitting = ref(false)

const compositeSourceOptions = computed(() =>
  list.value.filter(
    (d) =>
      (d.source_type === 'upload' || d.source_type === 'composite') && d.id
  )
)

const load = async () => {
  const res = await fetchList()
  list.value = res.data || []
}
const preview = async (row) => {
  const res = await fetchPreview(row.id)
  previewData.value = res
  previewVisible.value = true
}
const doDelete = async (row) => {
  await ElMessageBox.confirm('确定删除？')
  await remove(row.id)
  ElMessage.success('已删除')
  load()
}

const showRename = (row) => {
  renameForm.value = { id: row.id, name: row.name || '' }
  renameVisible.value = true
}
const submitRename = async () => {
  const { id, name } = renameForm.value
  if (!id || !name?.trim()) {
    ElMessage.warning('请输入新名称')
    return
  }
  renameSubmitting.value = true
  try {
    await update(id, { name: name.trim() })
    ElMessage.success('重命名成功')
    renameVisible.value = false
    load()
  } catch (e) {
    const d = e?.response?.data?.detail
    const msg = Array.isArray(d) ? d.map((x) => x?.msg ?? x).join('; ') : (d || e?.message || '重命名失败')
    ElMessage.error(msg)
  } finally {
    renameSubmitting.value = false
  }
}

const showCreateComposite = () => {
  compositeForm.value = { name: '', sourceIds: [] }
  compositeVisible.value = true
}
const submitComposite = async () => {
  const { name, sourceIds } = compositeForm.value
  if (!name?.trim()) {
    ElMessage.warning('请输入组合名称')
    return
  }
  if (!sourceIds?.length || sourceIds.length < 2) {
    ElMessage.warning('请至少选择 2 个源数据集')
    return
  }
  compositeSubmitting.value = true
  try {
    await create({
      name: name.trim(),
      source_type: 'composite',
      config_json: JSON.stringify({ source_ids: sourceIds }),
    })
    ElMessage.success('创建成功')
    compositeVisible.value = false
    load()
  } catch (e) {
    const d = e?.response?.data?.detail
    const msg = Array.isArray(d) ? d.map((x) => x?.msg ?? x).join('; ') : (d || e?.message || '创建失败')
    ElMessage.error(msg)
  } finally {
    compositeSubmitting.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.page-title {
  margin-bottom: 12px;
  font-size: 20px;
  font-weight: 600;
  color: var(--sx-text-title);
  letter-spacing: 0.03em;
  text-shadow: var(--sx-text-shadow-readable);
}
.page-hint { margin-bottom: 16px; }
.toolbar { margin-bottom: 16px; }
</style>
