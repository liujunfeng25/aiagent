<template>
  <div>
    <h2 class="page-title">类别管理</h2>
    <el-card class="tip-card">
      <el-form-item label="归属数据集">
        <el-select v-model="selectedDatasetId" placeholder="请选择数据集" style="width: 280px;" clearable @change="onDatasetChange">
          <el-option v-for="d in datasets" :key="d.id" :label="d.name" :value="d.id" />
        </el-select>
      </el-form-item>
      <el-alert v-if="!selectedDatasetId" type="info" show-icon :closable="false">
        请先选择上方「归属数据集」，再在该数据集下创建类别、上传图片。
      </el-alert>
      <el-alert v-else type="info" show-icon :closable="false">
        共 {{ totalImages }} 张图片
        <template v-if="totalImages > 0">
          ，<router-link to="/training">去训练</router-link> 时选择本数据集即可；
          <el-button v-if="categories.length >= 2 && totalImages >= 10" type="primary" link @click="trainVisible = true">用类别数据训练</el-button>
        </template>
      </el-alert>
    </el-card>
    <template v-if="selectedDatasetId">
      <el-card>
        <template #header>新建类别</template>
        <el-form :inline="true">
          <el-form-item label="类别名称">
            <el-input v-model="newCategoryName" placeholder="如：土豆、茄子、白菜" style="width: 220px;" clearable />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="creating" @click="createCategory">创建</el-button>
          </el-form-item>
        </el-form>
      </el-card>
      <el-card style="margin-top: 16px;">
        <template #header>现有类别</template>
        <el-table :data="categories" stripe>
          <el-table-column prop="name" label="类别名称" />
          <el-table-column prop="count" label="图片数量" width="120">
            <template #default="{ row }">{{ row.count }} 张</template>
          </el-table-column>
          <el-table-column label="操作" width="180">
            <template #default="{ row }">
              <router-link :to="{ path: '/categories/' + encodeURIComponent(row.name), query: { dataset_id: selectedDatasetId } }">
                <el-button size="small" type="primary" link>管理图片</el-button>
              </router-link>
              <el-button size="small" type="danger" link @click="doDeleteCategory(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </template>

    <el-dialog v-model="trainVisible" title="用类别数据训练" width="400">
      <el-form label-width="80px">
        <el-form-item label="训练轮数">
          <el-input-number v-model="trainEpochs" :min="2" :max="50" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="trainVisible = false">取消</el-button>
        <el-button type="primary" :loading="trainLoading" @click="doTrain">开始训练</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { list as listDatasetsApi, listCategories, createCategory as apiCreateCategory, deleteCategory } from '../api/datasets'
import { trainFromCategories } from '../api/categories'

const route = useRoute()
const router = useRouter()
const datasets = ref([])
const selectedDatasetId = ref(null)
const categories = ref([])
const totalImages = ref(0)
const newCategoryName = ref('')
const creating = ref(false)
const trainVisible = ref(false)
const trainEpochs = ref(10)
const trainLoading = ref(false)

const loadDatasets = async () => {
  const res = await listDatasetsApi()
  datasets.value = res.data || []
  const q = route.query.dataset_id
  if (q) {
    selectedDatasetId.value = Number(q) || q
    load()
  }
}
const onDatasetChange = () => {
  categories.value = []
  totalImages.value = 0
  if (selectedDatasetId.value) load()
}
const load = async () => {
  if (!selectedDatasetId.value) return
  const res = await listCategories(selectedDatasetId.value)
  categories.value = res.categories || []
  totalImages.value = res.total_images ?? 0
}

const createCategory = async () => {
  const name = newCategoryName.value?.trim()
  if (!name) {
    ElMessage.warning('请输入类别名称')
    return
  }
  if (!selectedDatasetId.value) {
    ElMessage.warning('请先选择归属数据集')
    return
  }
  creating.value = true
  try {
    await apiCreateCategory(selectedDatasetId.value, { name })
    ElMessage.success('创建成功')
    newCategoryName.value = ''
    load()
  } catch (e) {
    ElMessage.error(e.message || e.detail || '创建失败')
  } finally {
    creating.value = false
  }
}

const doDeleteCategory = async (row) => {
  await ElMessageBox.confirm(`确定删除类别「${row.name}」？其下 ${row.count} 张图片将一并删除。`)
  await deleteCategory(selectedDatasetId.value, row.name)
  ElMessage.success('已删除')
  load()
}

const doTrain = async () => {
  if (!selectedDatasetId.value) {
    ElMessage.warning('请先选择归属数据集')
    return
  }
  trainLoading.value = true
  try {
    await trainFromCategories({ dataset_id: selectedDatasetId.value, epochs: trainEpochs.value })
    ElMessage.success('训练已启动，请到训练管理查看进度')
    trainVisible.value = false
    router.push('/training')
  } catch (e) {
    ElMessage.error(e.message || e.detail || '启动失败')
  } finally {
    trainLoading.value = false
  }
}

onMounted(loadDatasets)
</script>

<style scoped>
.page-title {
  margin-bottom: 16px;
  font-size: 20px;
  font-weight: 600;
  color: var(--sx-text-title);
  letter-spacing: 0.03em;
  text-shadow: var(--sx-text-shadow-readable);
}
.tip-card { margin-bottom: 16px; }
.tip-card :deep(.el-alert) {
  margin-top: 12px;
}
.tip-card :deep(.el-alert:first-of-type) {
  margin-top: 0;
}
.tip-card :deep(a) {
  color: var(--sx-primary);
  font-weight: 500;
}
.tip-card :deep(a:hover) {
  color: var(--sx-cyan-light);
}
</style>
