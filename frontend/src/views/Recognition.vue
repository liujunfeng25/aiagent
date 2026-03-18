<template>
  <div class="recognition-page">
    <h2 class="page-title">识别中心</h2>
    <el-card v-if="!status.deployed" class="tip-card">
      <el-alert type="warning" show-icon :closable="false">
        <span>当前没有已部署的模型。</span>
        <span v-if="presetAvailable">您可以使用预置蔬菜模型，或前往 </span>
        <template v-else>请先在 </template>
        <router-link to="/models">模型库</router-link>
        <span v-if="presetAvailable"> 部署其他模型。</span>
        <span v-else> 中部署一个模型后再进行识别。</span>
      </el-alert>
      <el-button
        v-if="presetAvailable"
        type="primary"
        :loading="deployPresetLoading"
        style="margin-top: 12px;"
        @click="doDeployPreset"
      >
        一键使用预置蔬菜模型
      </el-button>
    </el-card>
    <el-card v-else class="tip-card">
      <span class="current-model">当前使用模型：{{ status.model_name }}</span>
    </el-card>
    <el-card v-if="testImageFiles.length" class="tip-card">
      <template #header>示例图片（来自 vegetable-recognition）</template>
      <div class="test-images">
        <div
          v-for="name in testImageFiles"
          :key="name"
          class="test-img-wrap"
          @click="useTestImage(name)"
        >
          <img :src="testImageUrl(name)" :alt="name" class="test-img" />
          <span class="test-img-name">{{ name }}</span>
        </div>
      </div>
    </el-card>
    <el-row :gutter="24">
      <el-col :span="12">
        <el-card>
          <template #header>上传图片</template>
          <el-upload
            class="upload-area"
            drag
            :auto-upload="false"
            :show-file-list="false"
            accept="image/*"
            :disabled="!status.deployed"
            @change="onFileChange"
          >
            <el-icon class="upload-icon"><UploadFilled /></el-icon>
            <div class="upload-text">将图片拖到此处，或<em>点击选择</em></div>
            <template #tip>
              <span>支持 jpg、png 等图片格式</span>
            </template>
          </el-upload>
          <el-button
            type="primary"
            :loading="loading"
            :disabled="!previewUrl || !status.deployed"
            style="margin-top: 12px;"
            @click="doRecognize"
          >
            开始识别
          </el-button>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>识别结果</template>
          <div v-if="previewUrl" class="preview-wrap">
            <img :src="previewUrl" alt="预览" class="preview-img" />
          </div>
          <div v-else class="preview-placeholder">请先选择一张图片</div>
          <el-table v-if="results.length" :data="results" stripe style="margin-top: 16px;">
            <el-table-column type="index" label="排名" width="70" />
            <el-table-column prop="label" label="类别" />
            <el-table-column prop="score" label="置信度" width="120">
              <template #default="{ row }">
                <el-progress :percentage="Math.round(row.score * 100)" :stroke-width="12" />
              </template>
            </el-table-column>
          </el-table>
          <div v-else-if="!loading && previewUrl && !results.length && !errorMsg" class="result-tip">点击「开始识别」获取结果</div>
          <el-alert v-if="errorMsg" type="error" :title="errorMsg" show-icon style="margin-top: 12px;" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { getRecognitionStatus, getPresetAvailable, deployPreset as apiDeployPreset, getTestImages, recognize as apiRecognize } from '../api/recognition'

const status = ref({ deployed: false, model_name: null })
const presetAvailable = ref(false)
const deployPresetLoading = ref(false)
const testImageFiles = ref([])
const previewUrl = ref('')
const currentFile = ref(null)
const results = ref([])
const loading = ref(false)
const errorMsg = ref('')

const loadStatus = async () => {
  try {
    status.value = await getRecognitionStatus()
  } catch (_) {
    status.value = { deployed: false, model_name: null }
  }
}
const loadPresetAvailable = async () => {
  try {
    const res = await getPresetAvailable()
    presetAvailable.value = !!res.available
  } catch (_) {
    presetAvailable.value = false
  }
}
const doDeployPreset = async () => {
  deployPresetLoading.value = true
  try {
    const res = await apiDeployPreset()
    ElMessage.success(res.message || '预置模型已部署')
    await loadStatus()
  } catch (e) {
    ElMessage.error((typeof e === 'string' ? e : (e?.message || e?.detail)) || '部署失败')
  } finally {
    deployPresetLoading.value = false
  }
}
const loadTestImages = async () => {
  try {
    const res = await getTestImages()
    testImageFiles.value = res.files || []
  } catch (_) {
    testImageFiles.value = []
  }
}
const testImageUrl = (name) => `/api/recognition/test_images/${encodeURIComponent(name)}`
const useTestImage = async (name) => {
  if (!status.value.deployed) return
  loading.value = true
  errorMsg.value = ''
  results.value = []
  try {
    const url = testImageUrl(name)
    const resp = await fetch(url)
    const blob = await resp.blob()
    const file = new File([blob], name, { type: blob.type || 'image/jpeg' })
    if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
    previewUrl.value = URL.createObjectURL(blob)
    currentFile.value = file
    const res = await apiRecognize(file)
    results.value = res.results || []
    ElMessage.success('识别完成')
  } catch (e) {
    errorMsg.value = (typeof e === 'string' ? e : (e?.message || e?.detail)) || '识别失败'
  } finally {
    loading.value = false
  }
}

const onFileChange = (uploadFile) => {
  const file = uploadFile.raw
  if (!file || !file.type.startsWith('image/')) {
    ElMessage.warning('请选择图片文件')
    return
  }
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = URL.createObjectURL(file)
  currentFile.value = file
  results.value = []
  errorMsg.value = ''
}

const doRecognize = async () => {
  if (!currentFile.value || !status.value.deployed) return
  loading.value = true
  errorMsg.value = ''
  results.value = []
  try {
    const res = await apiRecognize(currentFile.value)
    results.value = res.results || []
    ElMessage.success('识别完成')
  } catch (e) {
    errorMsg.value = (typeof e === 'string' ? e : (e?.message || e?.detail)) || '识别失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => { loadStatus(); loadPresetAvailable(); loadTestImages() })
</script>

<style scoped>
.page-title { margin-bottom: 16px; font-size: 20px; }
.tip-card { margin-bottom: 16px; }
.current-model { color: #606266; font-size: 14px; }
.upload-area { width: 100%; }
.upload-icon { font-size: 48px; color: #c0c4cc; margin-bottom: 8px; }
.upload-text { color: #606266; }
.upload-text em { color: #409eff; }
.preview-wrap { text-align: center; min-height: 200px; }
.preview-img { max-width: 100%; max-height: 280px; object-fit: contain; }
.preview-placeholder, .result-tip { color: #909399; text-align: center; padding: 24px; }
.test-images { display: flex; flex-wrap: wrap; gap: 12px; }
.test-img-wrap { width: 80px; text-align: center; cursor: pointer; border: 2px solid #eee; border-radius: 8px; padding: 4px; }
.test-img-wrap:hover { border-color: #409eff; }
.test-img { width: 72px; height: 72px; object-fit: cover; display: block; margin: 0 auto; border-radius: 4px; }
.test-img-name { font-size: 11px; color: #909399; display: block; margin-top: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
