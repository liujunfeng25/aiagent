<template>
  <div class="models-page">
    <h2 class="page-title">模型库</h2>
    <p class="card-hint">
      链路：<strong>数据集</strong> → <router-link to="/training">训练任务</router-link> → <strong>模型</strong>。
      下表「显示名称」仅用于本库展示；<strong>重命名模型不会修改数据集名称</strong>。
      同一数据集再次训练成功时，系统会按<strong>当前数据集名</strong>刷新默认显示名（规则：<code>数据集名</code> + <code>模型</code>）。
    </p>
    <el-card>
      <template #header>
        <div class="card-header-row">
          <span>模型列表</span>
          <el-button size="small" plain :loading="syncLoading" @click="confirmSyncDisplayNames">
            按数据集同步显示名
          </el-button>
        </div>
      </template>
      <el-table :data="list" stripe>
        <el-table-column prop="id" label="ID" width="72" />
        <el-table-column label="显示名称" min-width="160">
          <template #header>
            <span>显示名称</span>
            <el-tooltip content="可与数据集名不同；「自定义」表示与默认规则不一致。" placement="top">
              <span class="col-hint-icon">ⓘ</span>
            </el-tooltip>
          </template>
          <template #default="{ row }">
            <span class="name-cell">{{ row.name }}</span>
            <el-tag v-if="row.name_is_custom" type="info" size="small" class="custom-tag">自定义</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="来源数据集" min-width="140">
          <template #default="{ row }">
            <router-link v-if="row.dataset_id" to="/datasets" class="ds-link">{{ row.dataset_name }}</router-link>
            <span v-else>{{ row.dataset_name }}</span>
          </template>
        </el-table-column>
        <el-table-column label="训练任务" width="100">
          <template #default="{ row }">
            <router-link v-if="row.task_id" to="/training" class="task-link">#{{ row.task_id }}</router-link>
            <span v-else>—</span>
          </template>
        </el-table-column>
        <el-table-column prop="val_acc" label="验证准确率" width="110">
          <template #default="{ row }">{{ (row.val_acc * 100 || 0).toFixed(1) }}%</template>
        </el-table-column>
        <el-table-column prop="deployed" label="部署" width="88">
          <template #default="{ row }">
            <el-tag v-if="row.deployed" type="success" size="small">已部署</el-tag>
            <el-tag v-else size="small">未部署</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="186">
          <template #default="{ row }">{{ formatBeijingTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="openRename(row)">重命名</el-button>
            <el-button v-if="!row.deployed" size="small" type="primary" @click="doDeploy(row)">部署</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
    <el-dialog v-model="renameVisible" title="重命名模型" width="420" @close="renameForm.name = ''">
      <p class="dialog-tip">仅修改模型在库中的显示名称，不会重命名「数据集」菜单里的数据集。</p>
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
import { ElMessage, ElMessageBox } from 'element-plus'
import { list as fetchList, deploy, rename as renameApi, syncDisplayNames } from '../api/models'
import { formatBeijingTime } from '../utils/format'

const list = ref([])
const renameVisible = ref(false)
const renameLoading = ref(false)
const syncLoading = ref(false)
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

const confirmSyncDisplayNames = () => {
  ElMessageBox.confirm(
    '将所有模型的显示名重置为「当前数据集名 + 模型」。若您曾手动重命名模型，将被覆盖。是否继续？',
    '按数据集同步显示名',
    { type: 'warning', confirmButtonText: '同步', cancelButtonText: '取消' }
  )
    .then(async () => {
      syncLoading.value = true
      try {
        const res = await syncDisplayNames()
        ElMessage.success(res.message ? `${res.message}（${res.updated} 条已更新）` : '已完成')
        load()
      } catch (e) {
        ElMessage.error(e?.message || e?.detail || '同步失败')
      } finally {
        syncLoading.value = false
      }
    })
    .catch(() => {})
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
.card-hint {
  color: var(--sx-text-readable-muted);
  font-size: 14px;
  margin-bottom: 16px;
  line-height: 1.65;
  max-width: 85ch;
  text-shadow: var(--sx-text-shadow-strong);
}
.card-hint :deep(strong) {
  color: var(--sx-text-body);
}
.card-hint a { color: var(--sx-primary); font-weight: 500; }
.card-hint a:hover { color: var(--sx-cyan-light); }
.card-hint code {
  font-size: 0.9em;
  padding: 2px 6px;
  background: rgba(15, 23, 42, 0.85);
  border: 1px solid var(--sx-edge-cyan-mid);
  border-radius: 4px;
  color: var(--sx-cyan-light);
}
.card-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.col-hint-icon {
  margin-left: 4px;
  cursor: help;
  color: var(--sx-text-readable-dim);
  font-size: 12px;
}
.name-cell { margin-right: 8px; }
.custom-tag { vertical-align: middle; }
.ds-link,
.task-link {
  color: var(--sx-primary);
  text-decoration: none;
}
.ds-link:hover,
.task-link:hover {
  color: var(--sx-cyan-light);
  text-decoration: underline;
}
.dialog-tip {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--sx-text-readable-muted);
  line-height: 1.5;
}
</style>
