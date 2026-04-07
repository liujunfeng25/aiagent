<template>
  <div class="logistics-fee">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>物流费用管理</span>
          <el-button type="primary" @click="showAddDialog = true">新增费用</el-button>
        </div>
      </template>

      <el-form :inline="true" :model="searchForm">
        <el-form-item label="日期范围">
          <el-date-picker
            v-model="searchForm.date_range"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
            style="width: 240px"
          />
        </el-form-item>
        <el-form-item label="车牌">
          <el-input v-model="searchForm.plateno" placeholder="车牌号" clearable style="width: 120px" />
        </el-form-item>
        <el-form-item label="司机">
          <el-input v-model="searchForm.driver_name" placeholder="司机姓名" clearable style="width: 120px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadFees">查询</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="fees" border stripe show-summary :summary-method="summaryMethod">
        <el-table-column prop="fee_date" label="日期" width="110" />
        <el-table-column prop="plateno" label="车牌" width="110" />
        <el-table-column prop="driver_name" label="司机" width="90" />
        <el-table-column prop="follow_fee" label="跟车费" width="80" />
        <el-table-column prop="follow_fee2" label="跟车费2" width="80" />
        <el-table-column prop="freight" label="运费" width="80" />
        <el-table-column prop="staff_cost" label="人工费" width="80" />
        <el-table-column prop="toll_fee" label="路桥费" width="80" />
        <el-table-column prop="parking_fee" label="停车费" width="80" />
        <el-table-column prop="fixed_cost" label="固定成本" width="90" />
        <el-table-column label="油耗" width="110">
          <template #default="{ row }">{{ row.kilo }} km × {{ row.fuel_economy }}</template>
        </el-table-column>
        <el-table-column prop="fine_amount" label="罚款" width="70" />
        <el-table-column prop="total" label="合计" width="90">
          <template #default="{ row }">
            <strong style="color: #f56c6c;">{{ row.total }}</strong>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button link type="danger" @click="deleteFee(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新增费用对话框 -->
    <el-dialog v-model="showAddDialog" title="新增物流费用" width="600px">
      <el-form :model="feeForm" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="日期" required>
              <el-date-picker v-model="feeForm.fee_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="车牌">
              <el-input v-model="feeForm.plateno" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="司机">
              <el-input v-model="feeForm.driver_name" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="跟车费">
              <el-input-number v-model="feeForm.follow_fee" :precision="2" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="跟车费2">
              <el-input-number v-model="feeForm.follow_fee2" :precision="2" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="运费">
              <el-input-number v-model="feeForm.freight" :precision="2" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="人工费">
              <el-input-number v-model="feeForm.staff_cost" :precision="2" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="路桥费">
              <el-input-number v-model="feeForm.toll_fee" :precision="2" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="停车费">
              <el-input-number v-model="feeForm.parking_fee" :precision="2" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="固定成本">
              <el-input-number v-model="feeForm.fixed_cost" :precision="2" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="里程(km)">
              <el-input-number v-model="feeForm.kilo" :precision="1" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="油耗(元/km)">
              <el-input-number v-model="feeForm.fuel_economy" :precision="3" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="罚款">
              <el-input-number v-model="feeForm.fine_amount" :precision="2" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注">
              <el-input v-model="feeForm.remark" type="textarea" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item>
          <div style="background: #f5f7fa; padding: 8px 12px; border-radius: 4px; width: 100%">
            预计合计：<strong style="color: #f56c6c; font-size: 18px;">¥ {{ calcTotal }}</strong>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="addFee">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'

const searchForm = reactive({ date_range: [], plateno: '', driver_name: '' })
const fees = ref([])
const showAddDialog = ref(false)
const feeForm = reactive({
  fee_date: '', plateno: '', driver_name: '',
  follow_fee: 0, follow_fee2: 0, freight: 0,
  staff_cost: 0, toll_fee: 0, parking_fee: 0,
  fixed_cost: 0, kilo: 0, fuel_economy: 0,
  fine_amount: 0, remark: ''
})

const calcTotal = computed(() => {
  const t = feeForm.follow_fee + feeForm.follow_fee2 + feeForm.freight
    + feeForm.staff_cost + feeForm.toll_fee + feeForm.parking_fee
    + feeForm.fixed_cost + feeForm.kilo * feeForm.fuel_economy
    + feeForm.fine_amount
  return t.toFixed(2)
})

onMounted(loadFees)

async function loadFees() {
  const params = {
    plateno: searchForm.plateno,
    driver_name: searchForm.driver_name,
  }
  if (searchForm.date_range && searchForm.date_range.length === 2) {
    params.fee_date_start = searchForm.date_range[0]
    params.fee_date_end = searchForm.date_range[1]
  }
  const { data } = await axios.get('/api/logistics/fees', { params })
  fees.value = data.data
}

async function addFee() {
  if (!feeForm.fee_date) { ElMessage.warning('请选择日期'); return }
  await axios.post('/api/logistics/fees', feeForm)
  ElMessage.success('添加成功')
  showAddDialog.value = false
  loadFees()
}

async function deleteFee(row) {
  await ElMessageBox.confirm('确认删除该费用记录？', '提示', { type: 'warning' })
  await axios.delete(`/api/logistics/fees/${row.id}`)
  ElMessage.success('删除成功')
  loadFees()
}

function summaryMethod({ columns, data }) {
  return columns.map((col, index) => {
    if (index === 0) return '合计'
    const sumCols = ['follow_fee', 'follow_fee2', 'freight', 'staff_cost', 'toll_fee', 'parking_fee', 'fixed_cost', 'fine_amount', 'total']
    if (sumCols.includes(col.property)) {
      return data.reduce((acc, row) => acc + (Number(row[col.property]) || 0), 0).toFixed(2)
    }
    return ''
  })
}
</script>

<style scoped>
.logistics-fee { padding: 20px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
</style>
