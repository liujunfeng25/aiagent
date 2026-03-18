<template>
  <div>
    <h2 class="page-title">数据源管理</h2>
    <el-card>
      <el-button type="primary" @click="openDialog()">新增数据源</el-button>
      <el-table :data="list" stripe style="margin-top: 16px;">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="type" label="类型" width="100" />
        <el-table-column prop="host" label="主机" />
        <el-table-column prop="database" label="数据库" />
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button size="small" @click="testConn(row)">测试</el-button>
            <el-button size="small" @click="openDialog(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="doDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
    <el-dialog v-model="dialogVisible" :title="editId ? '编辑数据源' : '新增数据源'" width="500">
      <el-form :model="form" label-width="80px">
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="主机"><el-input v-model="form.host" /></el-form-item>
        <el-form-item label="端口"><el-input-number v-model="form.port" :min="1" /></el-form-item>
        <el-form-item label="数据库"><el-input v-model="form.database" /></el-form-item>
        <el-form-item label="用户名"><el-input v-model="form.username" /></el-form-item>
        <el-form-item label="密码"><el-input v-model="form.password" type="password" show-password :placeholder="editId ? '留空不修改' : ''" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { list as fetchList, create, update, remove, test } from '../api/datasources'

const list = ref([])
const dialogVisible = ref(false)
const editId = ref(null)
const form = ref({ name: '', host: '', port: 3306, database: '', username: '', password: '' })

const load = async () => {
  const res = await fetchList()
  list.value = res.data || []
}
const openDialog = (row) => {
  editId.value = row?.id || null
  form.value = row ? { ...row, password: '' } : { name: '', host: '', port: 3306, database: '', username: '', password: '' }
  dialogVisible.value = true
}
const submit = async () => {
  try {
    if (editId.value) {
      const data = { ...form.value }
      if (!data.password) delete data.password
      await update(editId.value, data)
      ElMessage.success('更新成功')
    } else {
      await create(form.value)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    load()
  } catch (e) {
    ElMessage.error(e.message || '操作失败')
  }
}
const testConn = async (row) => {
  try {
    const res = await test(row.id)
    ElMessage[res.success ? 'success' : 'error'](res.message)
  } catch (e) {
    ElMessage.error(e.message || '测试失败')
  }
}
const doDelete = async (row) => {
  await ElMessageBox.confirm('确定删除？')
  await remove(row.id)
  ElMessage.success('已删除')
  load()
}
onMounted(load)
</script>

<style scoped>
.page-title { margin-bottom: 16px; font-size: 20px; }
</style>
