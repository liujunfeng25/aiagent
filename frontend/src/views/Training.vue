<template>
  <div class="training-page">
    <h2 class="page-title">训练管理</h2>

    <el-card class="card-start">
      <template #header>开始训练</template>
      <p class="card-hint">
        <strong>数据从哪来：</strong>
        <router-link to="/categories">类别管理</router-link> 与
        <router-link to="/datasets">数据集</router-link> 是两套路——类别目录适合快速攒图、一键「用类别数据训练」；
        数据集适合上传 ZIP、组合多源或从数据源导出后再训。二者选其一准备好「按文件夹分好类的图片」即可，不必两边重复维护同一批图。
      </p>
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">训练轮数 (epochs)</label>
          <el-input-number v-model="form.epochs" :min="2" :max="50" class="epoch-input" />
        </div>
        <div class="form-group">
          <label class="form-label">数据集</label>
          <el-select v-model="form.dataset_id" placeholder="选择数据集" class="dataset-select" @change="onDatasetChange">
            <el-option v-for="d in datasets" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
        </div>
        <el-button type="primary" :loading="creating" :disabled="!!runningTaskId" @click="startTrain">
          开始训练
        </el-button>
      </div>
      <p v-if="sinceLast !== null" class="since-last-hint">
        <template v-if="sinceLast.last_trained_at === null">
          {{ sinceLast.message }}（当前 {{ sinceLast.new_categories }} 个类别，{{ sinceLast.new_images }} 张图片）
        </template>
        <template v-else>
          上次训练后：新增 <strong>{{ sinceLast.new_categories }}</strong> 个类别，新增 <strong>{{ sinceLast.new_images }}</strong> 张图片。
          <span v-if="sinceLast.new_categories > 0" class="new-cats-warn">存在新增类别，建议重新训练。</span>
        </template>
      </p>
      <p class="form-extra">
        或 <el-button type="primary" link @click="trainFromCategoriesOpen">用类别数据训练</el-button>
      </p>
      <p v-if="trainError" class="train-msg error">{{ trainError }}</p>
    </el-card>

    <el-card class="card-progress">
      <template #header>训练进度</template>
      <div class="progress-content">
        <template v-if="!displayTaskId || progressData.status === 'idle'">
          <p class="status-msg">{{ progressData.message || '未开始' }}</p>
        </template>
        <template v-else-if="progressData.status === 'starting'">
          <p class="status-msg status-running">{{ progressData.message || '训练启动中...' }}</p>
        </template>
        <template v-else-if="progressData.status === 'running'">
          <p class="status-msg status-running">训练中...</p>
          <div class="progress-bar-wrap">
            <div class="progress-bar-meta">
              <span>已完成 {{ progressData.percent.toFixed(2) }}%</span>
              <span v-if="progressData.etaText" class="eta">{{ progressData.etaText }}</span>
            </div>
            <el-progress :percentage="Number(progressData.percent.toFixed(2))" :stroke-width="14" />
          </div>
          <p class="progress-msg">{{ progressData.message }}</p>
          <p>Epoch {{ progressData.epoch }}/{{ progressData.total_epochs }}</p>
          <p>Loss: {{ progressData.loss ?? '-' }} | 训练准确率: {{ ((progressData.train_acc ?? 0) * 100).toFixed(1) }}% | 验证准确率: {{ ((progressData.val_acc ?? 0) * 100).toFixed(1) }}%</p>
        </template>
        <template v-else-if="progressData.status === 'done'">
          <p class="status-msg status-done">训练完成</p>
          <p class="progress-msg">{{ progressData.message }}</p>
          <p class="tip">请到模型库部署该模型后即可在识别中心使用。</p>
        </template>
        <template v-else-if="progressData.status === 'error'">
          <p class="status-msg status-error">训练出错</p>
          <p class="progress-msg">{{ progressData.message }}</p>
        </template>
      </div>
    </el-card>

    <el-card class="card-tasks">
      <template #header>最近任务</template>
      <el-table :data="tasks" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="dataset_name" label="数据集" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'done' ? 'success' : row.status === 'error' ? 'danger' : 'info'" size="small">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="200">
          <template #default="{ row }">{{ formatBeijingTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="140">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="showTaskInProgress(row)">查看</el-button>
            <el-button size="small" type="danger" link @click="doDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="trainFromCategoriesVisible" title="用类别数据训练" width="400">
      <el-form label-width="80px">
        <el-form-item label="训练轮数">
          <el-input-number v-model="categoryEpochs" :min="2" :max="50" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="trainFromCategoriesVisible = false">取消</el-button>
        <el-button type="primary" :loading="categoryTrainLoading" @click="doTrainFromCategories">开始训练</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listTasks, createTask as apiCreateTask, getTaskStatus, deleteTask, getDatasetSinceLast } from '../api/training'
import { list as listDatasets } from '../api/datasets'
import { trainFromCategories } from '../api/categories'
import { formatBeijingTime } from '../utils/format'

const router = useRouter()
const tasks = ref([])
const datasets = ref([])
const form = ref({ dataset_id: null, epochs: 10 })
const creating = ref(false)
const trainError = ref('')
const displayTaskId = ref(null)
const statusData = ref(null)
const runningTaskId = ref(null)
let pollTimer = null
const trainFromCategoriesVisible = ref(false)
const categoryEpochs = ref(10)
const categoryTrainLoading = ref(false)
const sinceLast = ref(null)

const progressData = computed(() => {
  const s = statusData.value
  if (!s) return { status: 'idle', message: '未开始', percent: 0, epoch: 0, total_epochs: 1, etaText: '' }
  const totalEpochs = s.total_epochs || 1
  const epoch = s.epoch || 0
  const numBatches = s.num_batches || 0
  const batchIdx = s.batch_idx ?? 0
  let percent = 0
  if (s.status === 'running' && numBatches > 0 && batchIdx !== undefined) {
    const completed = (epoch - 1) * numBatches + batchIdx
    percent = Math.min(100, (completed / (totalEpochs * numBatches)) * 100)
  } else {
    percent = totalEpochs > 0 ? (epoch / totalEpochs) * 100 : 0
  }
  let etaText = ''
  const startedAt = s.started_at
  if (startedAt && percent > 2) {
    const elapsed = Date.now() / 1000 - startedAt
    const etaSec = (elapsed / percent) * (100 - percent)
    etaText = '预计剩余 ' + Math.floor(etaSec / 60) + ' 分 ' + Math.floor(etaSec % 60) + ' 秒'
  } else if (startedAt && percent > 0) {
    etaText = '计算中...'
  }
  return {
    status: s.status,
    message: s.message || '',
    percent,
    epoch,
    total_epochs: totalEpochs,
    loss: s.loss,
    train_acc: s.train_acc,
    val_acc: s.val_acc,
    etaText,
  }
})

const loadTasks = async () => {
  tasks.value = (await listTasks()).data || []
}
const loadDatasets = async () => {
  datasets.value = (await listDatasets()).data || []
}
const loadSinceLast = async () => {
  if (!form.value.dataset_id) {
    sinceLast.value = null
    return
  }
  try {
    sinceLast.value = await getDatasetSinceLast(form.value.dataset_id)
  } catch (_) {
    sinceLast.value = null
  }
}
const onDatasetChange = () => {
  loadSinceLast()
}
const load = () => {
  loadTasks()
  loadDatasets()
}

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

const pollStatus = async () => {
  if (!displayTaskId.value) return
  try {
    const s = await getTaskStatus(displayTaskId.value)
    statusData.value = s
    if (s.status === 'running' || s.status === 'starting') {
      runningTaskId.value = displayTaskId.value
      if (!pollTimer) pollTimer = setInterval(pollStatus, 1500)
    } else {
      runningTaskId.value = null
      stopPolling()
      loadTasks()
    }
  } catch (_) {
    stopPolling()
    runningTaskId.value = null
  }
}

const startTrain = async () => {
  trainError.value = ''
  if (!form.value.dataset_id) {
    trainError.value = '请选择数据集'
    return
  }
  creating.value = true
  try {
    const res = await apiCreateTask(form.value)
    displayTaskId.value = res.id
    statusData.value = { status: 'starting', message: '训练启动中...' }
    runningTaskId.value = res.id
    pollTimer = setInterval(pollStatus, 1500)
    await pollStatus()
    ElMessage.success('任务已创建')
    loadTasks()
  } catch (e) {
    trainError.value = (typeof e === 'string' ? e : (e?.message || e?.detail)) || '启动失败'
  } finally {
    creating.value = false
  }
}

const showTaskInProgress = async (row) => {
  displayTaskId.value = row.id
  const s = await getTaskStatus(row.id)
  statusData.value = s
  if (s.status === 'running' || s.status === 'starting') {
    runningTaskId.value = row.id
    if (!pollTimer) pollTimer = setInterval(pollStatus, 1500)
  }
}

const doDelete = async (row) => {
  await ElMessageBox.confirm('确定删除该任务？')
  await deleteTask(row.id)
  ElMessage.success('已删除')
  if (displayTaskId.value === row.id) {
    displayTaskId.value = null
    statusData.value = null
    stopPolling()
  }
  loadTasks()
}

const trainFromCategoriesOpen = () => {
  trainFromCategoriesVisible.value = true
}
const doTrainFromCategories = async () => {
  if (!form.value.dataset_id) {
    ElMessage.warning('请先选择上方「数据集」再使用用类别数据训练')
    return
  }
  categoryTrainLoading.value = true
  try {
    const res = await trainFromCategories({ dataset_id: form.value.dataset_id, epochs: categoryEpochs.value })
    trainFromCategoriesVisible.value = false
    ElMessage.success('训练已启动')
    displayTaskId.value = res.task_id
    statusData.value = { status: 'starting', message: '训练启动中...' }
    runningTaskId.value = res.task_id
    pollTimer = setInterval(pollStatus, 1500)
    await pollStatus()
    loadTasks()
    router.push('/training')
  } catch (e) {
    ElMessage.error((typeof e === 'string' ? e : (e?.message || e?.detail)) || '启动失败')
  } finally {
    categoryTrainLoading.value = false
  }
}

onMounted(async () => {
  await load()
  if (form.value.dataset_id) loadSinceLast()
  if (tasks.value.length && !displayTaskId.value) {
    const first = tasks.value[0]
    displayTaskId.value = first.id
    const s = await getTaskStatus(first.id)
    statusData.value = s
    if (s.status === 'running' || s.status === 'starting') {
      runningTaskId.value = first.id
      pollTimer = setInterval(pollStatus, 1500)
    }
  }
})
</script>

<style scoped>
.training-page { max-width: 900px; }
.page-title { margin-bottom: 16px; font-size: 20px; }
.card-start { margin-bottom: 16px; }
.card-progress { margin-bottom: 16px; }
.card-tasks { margin-bottom: 16px; }
.card-hint { color: #606266; font-size: 14px; margin-bottom: 16px; line-height: 1.6; }
.card-hint a { color: #409eff; }
.form-row { display: flex; align-items: flex-end; gap: 16px; flex-wrap: wrap; }
.form-group { display: flex; flex-direction: column; gap: 4px; }
.form-label { font-size: 12px; color: #606266; }
.epoch-input { width: 120px; }
.dataset-select { width: 220px; }
.form-extra { margin-top: 12px; font-size: 14px; color: #606266; }
.train-msg { margin-top: 12px; font-size: 13px; }
.train-msg.error { color: #f56c6c; }
.since-last-hint { margin-top: 12px; color: #606266; font-size: 13px; line-height: 1.5; }
.since-last-hint .new-cats-warn { color: #f56c6c; font-weight: 600; }
.progress-content { min-height: 80px; }
.status-msg { margin: 0 0 8px 0; }
.status-running { color: #409eff; font-weight: 500; }
.status-done { color: #67c23a; font-weight: 500; }
.status-error { color: #f56c6c; font-weight: 500; }
.progress-bar-wrap { margin: 12px 0; }
.progress-bar-meta { display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 4px; }
.eta { color: #909399; }
.progress-msg { margin: 8px 0; font-size: 13px; }
.tip { font-size: 13px; color: #909399; margin-top: 8px; }
</style>
