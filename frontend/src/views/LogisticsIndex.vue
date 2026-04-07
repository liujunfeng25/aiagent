<template>
  <div class="logistics-index">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>车辆管理（SXW MySQL）</span>
          <div>
            <el-button size="small" @click="syncLocal">同步绑定到本地 SQLite</el-button>
          </div>
        </div>
      </template>

      <el-form :inline="true" :model="searchForm">
        <el-form-item label="租户 supp" title="与食迅后台 supp_code 一致">
          <el-input
            v-model="tenantSuppCode"
            placeholder="业务库标识"
            clearable
            style="width: 220px"
            @change="onTenantChange"
          />
        </el-form-item>
        <el-form-item label="车牌号">
          <el-input v-model="searchForm.plateno" placeholder="模糊查询" clearable />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadVehicles">查询</el-button>
        </el-form-item>
      </el-form>
      <p class="tenant-hint">
        数据与食迅「智能物流 → 车辆管理」同源；<strong>设备绑定</strong>与<strong>位置</strong>为独立页面，对齐 SXW 多页结构。
      </p>

      <el-table :data="vehicles" border stripe v-loading="loading">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="plateno" label="车牌号" width="110" />
        <el-table-column prop="car_type" label="车型" />
        <el-table-column prop="shipper_type" label="类型" width="80" />
        <el-table-column prop="driver_name" label="司机" />
        <el-table-column label="北斗" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.beidou_bind_rows > 0" :type="row.beidou_macid_conflict ? 'danger' : 'success'" size="small">
              {{ row.beidou_macid_conflict ? '已绑(冲突)' : '已绑' }}
            </el-tag>
            <el-tag v-else-if="row.has_imei_field" type="warning" size="small">仅IMEI</el-tag>
            <el-tag v-else type="info" size="small">未绑</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="摄像头" width="90">
          <template #default="{ row }">
            <el-tag type="primary" size="small">{{ row.camera_count }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="goBind(row)">设备管理</el-button>
            <el-button link type="success" @click="goLocation(row)">位置</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager" v-if="total > 0">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @current-change="loadVehicles"
          @size-change="loadVehicles"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { useRouter } from 'vue-router'
import { getSxwLogisticsSuppCode, setSxwLogisticsSuppCode, sxwLogisticsAxiosParams } from '../utils/sxwLogisticsTenant'

const router = useRouter()
const tenantSuppCode = ref(getSxwLogisticsSuppCode())
const searchForm = reactive({ plateno: '' })
const vehicles = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)
const loading = ref(false)

function onTenantChange() {
  setSxwLogisticsSuppCode(tenantSuppCode.value)
  page.value = 1
  loadVehicles()
}

onMounted(() => loadVehicles())

async function loadVehicles() {
  loading.value = true
  try {
    const { data } = await axios.get('/api/logistics/vehicles', {
      params: sxwLogisticsAxiosParams({
        ...searchForm,
        page: page.value,
        page_size: pageSize.value,
      }),
    })
    const payload = data.data
    if (payload && Array.isArray(payload.items)) {
      vehicles.value = payload.items
      total.value = payload.total || 0
    } else if (Array.isArray(payload)) {
      vehicles.value = payload
      total.value = payload.length
    } else {
      vehicles.value = []
      total.value = 0
    }
  } catch (e) {
    console.error(e)
    ElMessage.error(e.response?.data?.detail || e.message || '加载车辆失败')
    vehicles.value = []
  } finally {
    loading.value = false
  }
}

async function syncLocal() {
  try {
    const { data } = await axios.post('/api/logistics/sync/sxw-bindings', null, { params: sxwLogisticsAxiosParams() })
    const d = data.data
    ElMessage.success(`本地同步：摄像头新增 ${d.cameras_upserted}，北斗 ${d.beidou_upserted}，绑定 ${d.camera_binds}`)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message || '同步失败')
  }
}

function goBind(row) {
  router.push({ path: `/logistics/vehicle/${row.id}/bind`, query: { plateno: row.plateno } })
}

function goLocation(row) {
  router.push({ path: `/logistics/vehicle/${row.id}/location`, query: { plateno: row.plateno } })
}
</script>

<style scoped>
.logistics-index { padding: 20px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.tenant-hint {
  margin: 0 0 12px;
  padding: 8px 12px;
  font-size: 12px;
  color: #606266;
  background: #f4f4f5;
  border-radius: 4px;
}
.pager { margin-top: 16px; display: flex; justify-content: flex-end; }
</style>
