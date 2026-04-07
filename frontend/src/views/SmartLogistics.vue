<template>
  <div class="smart-logistics">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>车辆管理（数据源自公司业务库 MySQL）</span>
          <div>
            <el-button size="small" @click="syncLocal">同步绑定到本地 SQLite</el-button>
          </div>
        </div>
      </template>

      <el-form :inline="true" :model="searchForm">
        <el-form-item label="租户 supp" title="与食迅后台登录会话一致，见浏览器侧说明">
          <el-input
            v-model="tenantSuppCode"
            placeholder="如登录后台的数字 ID 或 supp_ 前缀"
            clearable
            style="width: 220px"
            @change="onTenantChange"
          />
        </el-form-item>
        <el-form-item label="车牌号">
          <el-input v-model="searchForm.plateno" placeholder="输入车牌号" clearable />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadVehicles">查询</el-button>
        </el-form-item>
      </el-form>
      <p class="tenant-hint">
        车辆数据在供应商分库 <code>supp_*</code> 中；后台已登录时 PHP 会按 supp_code 切换库，AI 平台需填同一租户标识，或在后端 <code>.env</code> 设置 <code>SXW_MYSQL_SUPP_CODE</code>。
      </p>

      <el-table :data="vehicles" border stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="plateno" label="车牌号" width="120" />
        <el-table-column prop="car_type" label="车型" />
        <el-table-column prop="shipper_type" label="类型" width="80" />
        <el-table-column prop="driver_name" label="司机" />
        <el-table-column label="电话" width="80">
          <template #default><span class="text-muted">—</span></template>
        </el-table-column>
        <el-table-column label="北斗" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.beidou_bind_rows > 0" :type="row.beidou_macid_conflict ? 'danger' : 'success'" size="small">
              {{ row.beidou_macid_conflict ? '已绑(冲突)' : '已绑' }}
            </el-tag>
            <el-tag v-else-if="row.has_imei_field" type="warning" size="small">仅IMEI</el-tag>
            <el-tag v-else type="info" size="small">未绑</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="摄像头" width="80">
          <template #default="{ row }">
            <el-tag type="primary" size="small">{{ row.camera_count }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openBindDialog(row)">设备管理</el-button>
            <el-button link type="success" @click="openLocationPage(row)">位置</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 设备绑定对话框 -->
    <el-dialog v-model="showBindDialog" :title="`设备管理 - ${currentVehicle?.plateno}`" width="800px">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="北斗设备" name="beidou">
          <el-form :model="beidouForm" label-width="120px">
            <el-form-item label="MDS/终端号">
              <el-input v-model="beidouForm.mds" />
            </el-form-item>
            <el-form-item label="UnitId">
              <el-input v-model="beidouForm.unit_id" />
            </el-form-item>
            <el-form-item label="登录账号">
              <el-input v-model="beidouForm.login_name" placeholder="留空使用全局配置" />
            </el-form-item>
            <el-form-item label="登录密码">
              <el-input v-model="beidouForm.login_password" type="password" placeholder="留空使用全局配置" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveBeidou">保存</el-button>
              <el-button type="danger" @click="detachBeidou" v-if="beidouForm.id">解绑</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="摄像头" name="camera">
          <el-button type="primary" size="small" @click="showCameraSelectDialog = true" style="margin-bottom: 10px">
            添加摄像头
          </el-button>
          <el-table :data="cameras" border size="small">
            <el-table-column prop="name" label="设备名称" />
            <el-table-column prop="brand" label="品牌" width="80" />
            <el-table-column prop="device_serial" label="序列号" />
            <el-table-column prop="position_label" label="安装位置" />
            <el-table-column label="操作" width="100">
              <template #default="{ row }">
                <el-button link type="danger" @click="detachCamera(row)">解绑</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-dialog>

    <!-- 摄像头选择对话框 -->
    <el-dialog v-model="showCameraSelectDialog" title="选择摄像头" width="600px">
      <el-form :model="cameraBindForm" label-width="100px">
        <el-form-item label="摄像头">
          <el-select v-model="cameraBindForm.camera_id" placeholder="选择设备">
            <el-option
              v-for="cam in allCameras"
              :key="cam.id"
              :label="`${cam.name} (${cam.device_serial})`"
              :value="cam.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="安装位置">
          <el-input v-model="cameraBindForm.position_label" placeholder="如：车头、车厢" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCameraSelectDialog = false">取消</el-button>
        <el-button type="primary" @click="attachCamera">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import { useRouter } from 'vue-router'
import { getSxwLogisticsSuppCode, setSxwLogisticsSuppCode, sxwLogisticsAxiosParams } from '../utils/sxwLogisticsTenant'

const router = useRouter()

const tenantSuppCode = ref(getSxwLogisticsSuppCode())
const searchForm = reactive({ plateno: '' })

function onTenantChange() {
  setSxwLogisticsSuppCode(tenantSuppCode.value)
  loadVehicles()
}
const vehicles = ref([])

const showBindDialog = ref(false)
const currentVehicle = ref(null)
const activeTab = ref('beidou')
const beidouForm = reactive({ id: null, mds: '', unit_id: '', login_name: '', login_password: '' })
const cameras = ref([])

const showCameraSelectDialog = ref(false)
const allCameras = ref([])
const cameraBindForm = reactive({ camera_id: null, position_label: '' })

onMounted(() => {
  loadVehicles()
  loadAllCameras()
})

async function loadVehicles() {
  try {
    const { data } = await axios.get('/api/logistics/vehicles', { params: sxwLogisticsAxiosParams(searchForm) })
    vehicles.value = data.data || []
  } catch (e) {
    console.error(e)
    ElMessage.error(e.response?.data?.detail || e.message || '加载车辆失败')
    vehicles.value = []
  }
}

async function syncLocal() {
  try {
    const { data } = await axios.post('/api/logistics/sync/sxw-bindings', null, { params: sxwLogisticsAxiosParams() })
    ElMessage.success(`本地同步完成：摄像头 ${data.data.cameras_upserted} 新增，北斗 ${data.data.beidou_upserted}，绑定 ${data.data.camera_binds}`)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message || '同步失败')
  }
}

async function openBindDialog(row) {
  currentVehicle.value = row
  showBindDialog.value = true
  activeTab.value = 'beidou'
  await loadBeidou(row.id)
  await loadCameras(row.id)
}

async function loadBeidou(vehicleId) {
  const { data } = await axios.get(`/api/logistics/vehicles/${vehicleId}/beidou`, { params: sxwLogisticsAxiosParams() })
  if (data.data) {
    Object.assign(beidouForm, data.data)
  } else {
    Object.assign(beidouForm, { id: null, mds: '', unit_id: '', login_name: '', login_password: '' })
  }
}

async function saveBeidou() {
  await axios.post(`/api/logistics/vehicles/${currentVehicle.value.id}/beidou`, beidouForm, { params: sxwLogisticsAxiosParams() })
  ElMessage.success('保存成功')
  loadBeidou(currentVehicle.value.id)
  loadVehicles()
}

async function detachBeidou() {
  await ElMessageBox.confirm('确认解绑北斗设备？', '提示', { type: 'warning' })
  await axios.delete(`/api/logistics/vehicles/${currentVehicle.value.id}/beidou`, { params: sxwLogisticsAxiosParams() })
  ElMessage.success('解绑成功')
  loadBeidou(currentVehicle.value.id)
  loadVehicles()
}

async function loadCameras(vehicleId) {
  const { data } = await axios.get(`/api/logistics/vehicles/${vehicleId}/cameras`, { params: sxwLogisticsAxiosParams() })
  cameras.value = data.data
}

async function loadAllCameras() {
  const { data } = await axios.get('/api/logistics/devices/cameras', { params: sxwLogisticsAxiosParams() })
  allCameras.value = data.data
}

async function attachCamera() {
  await axios.post(`/api/logistics/vehicles/${currentVehicle.value.id}/cameras`, cameraBindForm, { params: sxwLogisticsAxiosParams() })
  ElMessage.success('绑定成功')
  showCameraSelectDialog.value = false
  Object.assign(cameraBindForm, { camera_id: null, position_label: '' })
  loadCameras(currentVehicle.value.id)
  loadVehicles()
}

async function detachCamera(row) {
  await ElMessageBox.confirm('确认解绑该摄像头？', '提示', { type: 'warning' })
  await axios.delete(`/api/logistics/vehicles/${currentVehicle.value.id}/cameras/${row.bind_id}`, { params: sxwLogisticsAxiosParams() })
  ElMessage.success('解绑成功')
  loadCameras(currentVehicle.value.id)
  loadVehicles()
}

function openLocationPage(row) {
  router.push({ path: '/logistics/location', query: { vehicleId: row.id, plateno: row.plateno } })
}
</script>

<style scoped>
.smart-logistics {
  padding: 20px;
}
.text-muted {
  color: #909399;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.tenant-hint {
  margin: 0 0 12px;
  padding: 8px 12px;
  font-size: 12px;
  color: #606266;
  background: #f4f4f5;
  border-radius: 4px;
  line-height: 1.5;
}
.tenant-hint code {
  font-size: 11px;
}
</style>
