<template>
  <div class="logistics-bind">
    <el-card v-loading="loading">
      <template #header>
        <div class="card-header">
          <span>设备绑定 — {{ plateno }} (#{{ vehicleId }})</span>
          <el-button @click="$router.push('/logistics')">返回列表</el-button>
        </div>
      </template>

      <div class="vehicle-info">
        <span>车牌：<b>{{ plateno }}</b></span>
        <span v-if="vehicleMeta">车型：{{ vehicleMeta.car_type }}</span>
        <span v-if="vehicleMeta">所属：{{ vehicleMeta.shipper_type }}</span>
      </div>

      <div class="section">
        <div class="section-title">
          北斗定位
          <el-button type="primary" size="small" @click="openBeidou = true">绑定 / 修改</el-button>
        </div>
        <el-table :data="beidouRows" border size="small" v-if="beidouRows.length">
          <el-table-column prop="macid" label="设备号(macid)" />
          <el-table-column prop="user_id" label="user_id(可选)" />
          <el-table-column label="操作" width="100">
            <template #default>
              <el-button type="danger" link @click="detachBeidou">解绑</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="未绑定北斗，请点击「绑定 / 修改」" :image-size="80" />
      </div>

      <div class="section">
        <div class="section-title">
          已绑定摄像头
          <el-button type="primary" size="small" @click="openCamera = true">添加绑定</el-button>
        </div>
        <el-table :data="cameras" border size="small">
          <el-table-column prop="device_name" label="设备名称" />
          <el-table-column prop="device_guid" label="设备GUID" />
          <el-table-column prop="channel_id" label="通道" width="80" />
          <el-table-column label="操作" width="100">
            <template #default="{ row }">
              <el-button type="danger" link @click="detachCam(row)">解绑</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!cameras.length" description="暂无绑定摄像头" :image-size="60" />
      </div>
    </el-card>

    <el-dialog v-model="openBeidou" title="北斗绑定" width="520px" @open="prefillBeidou">
      <el-form :model="beidouForm" label-width="120px">
        <el-form-item label="macid / 终端号" required>
          <el-input v-model="beidouForm.mds" placeholder="与北斗平台列表一致" />
        </el-form-item>
        <el-form-item label="user_id(可选)">
          <el-input v-model="beidouForm.unit_id" placeholder="历史轨迹兜底 Guid" />
        </el-form-item>
        <el-form-item label="GPS18 账号">
          <el-input v-model="beidouForm.login_name" placeholder="留空用环境变量" />
        </el-form-item>
        <el-form-item label="GPS18 密码">
          <el-input v-model="beidouForm.login_password" type="password" placeholder="留空用环境变量" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="openBeidou = false">取消</el-button>
        <el-button type="primary" @click="saveBeidou">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="openCamera" title="绑定摄像头" width="480px">
      <el-select v-model="cameraPick" placeholder="选择设备" filterable style="width:100%">
        <el-option
          v-for="c in allCameras"
          :key="c.id"
          :label="formatCamLabel(c)"
          :value="c.id"
        />
      </el-select>
      <template #footer>
        <el-button @click="openCamera = false">取消</el-button>
        <el-button type="primary" @click="attachCamera">绑定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import { sxwLogisticsAxiosParams } from '../utils/sxwLogisticsTenant'

const route = useRoute()
const vehicleId = computed(() => Number(route.params.id))
const plateno = computed(() => route.query.plateno || '车辆')

const loading = ref(false)
const vehicleMeta = ref(null)
const cameras = ref([])
const beidouRows = ref([])
const openBeidou = ref(false)
const openCamera = ref(false)
const allCameras = ref([])
const cameraPick = ref(null)

const beidouForm = reactive({ mds: '', unit_id: '', login_name: '', login_password: '' })

onMounted(async () => {
  await refreshAll()
  const { data } = await axios.get(`/api/logistics/vehicles/${vehicleId.value}`, { params: sxwLogisticsAxiosParams() })
  vehicleMeta.value = data.data
})

function formatCamLabel(c) {
  const tag = c.brand === 'ys7' ? '[萤石] ' : '[乐橙] '
  const g = c.device_serial ? ` (${c.device_serial})` : ''
  return tag + (c.name || '') + g
}

async function refreshAll() {
  loading.value = true
  try {
    const [bd, cm, lib] = await Promise.all([
      axios.get(`/api/logistics/vehicles/${vehicleId.value}/beidou`, { params: sxwLogisticsAxiosParams() }),
      axios.get(`/api/logistics/vehicles/${vehicleId.value}/cameras`, { params: sxwLogisticsAxiosParams() }),
      axios.get('/api/logistics/devices/cameras', { params: sxwLogisticsAxiosParams() }),
    ])
    allCameras.value = lib.data.data || []
    const d = bd.data.data
    if (d && (d.macid || d.mds)) {
      beidouRows.value = [{
        macid: d.macid || d.mds,
        user_id: d.user_id || d.unit_id || '—',
      }]
    } else {
      beidouRows.value = []
    }
    cameras.value = cm.data.data || []
  } finally {
    loading.value = false
  }
}

function prefillBeidou() {
  if (beidouRows.value.length) {
    beidouForm.mds = beidouRows.value[0].macid
    beidouForm.unit_id = beidouRows.value[0].user_id === '—' ? '' : beidouRows.value[0].user_id
  } else {
    beidouForm.mds = ''
    beidouForm.unit_id = ''
  }
}

async function saveBeidou() {
  try {
    await axios.post(`/api/logistics/vehicles/${vehicleId.value}/beidou`, beidouForm, { params: sxwLogisticsAxiosParams() })
    ElMessage.success('保存成功')
    openBeidou.value = false
    await refreshAll()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  }
}

async function detachBeidou() {
  await ElMessageBox.confirm('确认解绑北斗？', '提示', { type: 'warning' })
  await axios.delete(`/api/logistics/vehicles/${vehicleId.value}/beidou`, { params: sxwLogisticsAxiosParams() })
  ElMessage.success('已解绑')
  await refreshAll()
}

async function attachCamera() {
  if (!cameraPick.value) {
    ElMessage.warning('请选择摄像头')
    return
  }
  try {
    await axios.post(
      `/api/logistics/vehicles/${vehicleId.value}/cameras`,
      { camera_device_id: cameraPick.value },
      { params: sxwLogisticsAxiosParams() },
    )
    ElMessage.success('绑定成功')
    openCamera.value = false
    cameraPick.value = null
    await refreshAll()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '绑定失败')
  }
}

async function detachCam(row) {
  await ElMessageBox.confirm('解绑该摄像头？', '提示', { type: 'warning' })
  await axios.delete(`/api/logistics/vehicles/${vehicleId.value}/cameras/${row.bind_id}`, { params: sxwLogisticsAxiosParams() })
  ElMessage.success('已解绑')
  await refreshAll()
}
</script>

<style scoped>
.logistics-bind { padding: 20px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.vehicle-info {
  background: #f8f8f8;
  padding: 12px 16px;
  border-radius: 6px;
  margin-bottom: 16px;
}
.vehicle-info span { margin-right: 24px; }
.section { margin-bottom: 24px; }
.section-title {
  font-weight: 600;
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 12px;
}
</style>
