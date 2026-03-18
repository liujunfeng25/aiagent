<template>
  <div>
    <div class="nav-back">
      <router-link :to="backLink">← 返回类别列表</router-link>
    </div>
    <h2 class="page-title">类别：{{ categoryName }}</h2>
    <el-card>
      <template #header>上传图片</template>
      <el-upload
        class="upload-drag"
        drag
        :auto-upload="false"
        :show-file-list="false"
        accept="image/*"
        multiple
        :on-change="onSelectImages"
      >
        <el-icon class="upload-icon"><UploadFilled /></el-icon>
        <div class="upload-text">点击选择或拖拽图片到此处</div>
      </el-upload>
    </el-card>
    <el-card style="margin-top: 16px;">
      <template #header>已上传图片</template>
      <div v-if="imageList.length" class="image-gallery">
        <div v-for="f in imageList" :key="f" class="image-card">
          <img :src="imageUrl(f)" :alt="f" class="thumb" />
          <el-button class="btn-delete" type="danger" size="small" @click="doDeleteImage(f)">删除</el-button>
        </div>
      </div>
      <div v-else class="image-empty">暂无图片，请在上方上传</div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { listCategoryImages, uploadCategoryImage, deleteCategoryImage } from '../api/datasets'

const route = useRoute()
const router = useRouter()
const datasetId = computed(() => route.query.dataset_id ?? '')
const categoryName = computed(() => route.params.name || '')
const imageList = ref([])
const uploading = ref(false)

const backLink = computed(() => ({ path: '/categories', query: datasetId.value ? { dataset_id: datasetId.value } : {} }))

const imageUrl = (filename) =>
  `/api/datasets/${datasetId.value}/categories/${encodeURIComponent(categoryName.value)}/image/${encodeURIComponent(filename)}`

const load = async () => {
  if (!categoryName.value || !datasetId.value) return
  try {
    const res = await listCategoryImages(datasetId.value, categoryName.value)
    imageList.value = res.images || []
  } catch (_) {
    imageList.value = []
  }
}

const onSelectImages = async (uploadFile) => {
  if (!categoryName.value || !datasetId.value || !uploadFile.raw) return
  uploading.value = true
  try {
    await uploadCategoryImage(datasetId.value, categoryName.value, uploadFile.raw)
    ElMessage.success('上传成功')
    await load()
  } catch (e) {
    ElMessage.error(e.message || e.detail || '上传失败')
  } finally {
    uploading.value = false
  }
}

const doDeleteImage = async (filename) => {
  await ElMessageBox.confirm(`确定删除图片 ${filename}？`)
  await deleteCategoryImage(datasetId.value, categoryName.value, filename)
  ElMessage.success('已删除')
  await load()
}

onMounted(() => {
  if (!datasetId.value) {
    ElMessage.warning('缺少数据集，请从类别管理进入')
    router.replace('/categories')
    return
  }
  load()
})
watch([() => route.params.name, () => route.query.dataset_id], load)
</script>

<style scoped>
.nav-back { margin-bottom: 16px; }
.page-title { margin-bottom: 16px; font-size: 20px; }
.upload-drag { width: 100%; }
.upload-icon { font-size: 56px; color: #c0c4cc; margin-bottom: 8px; }
.upload-text { color: #606266; }
.image-gallery { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 12px; }
.image-card { position: relative; border: 1px solid #eee; border-radius: 8px; overflow: hidden; }
.image-card .thumb { width: 100%; height: 140px; object-fit: cover; display: block; }
.image-card .btn-delete { position: absolute; bottom: 4px; right: 4px; }
.image-empty { color: #909399; text-align: center; padding: 32px; }
</style>
