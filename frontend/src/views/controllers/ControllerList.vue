<template>
  <div class="controllers-container">
    <!-- Header -->
    <div class="page-header">
      <h2>Controller 管理</h2>
      <el-button type="primary" @click="showAddDialog">
        <el-icon><Plus /></el-icon>
        添加 Controller
      </el-button>
    </div>

    <!-- Controller List -->
    <el-card class="content-card">
      <el-table :data="controllers" v-loading="loading" stripe>
        <el-table-column prop="name" label="名称" min-width="150" />
        <el-table-column prop="address" label="地址" min-width="200">
          <template #default="{ row }">
            <span class="kv-num">{{ row.address }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="cluster_count" label="集群数" width="100" align="center" />
        <el-table-column prop="last_check_at" label="最后检查" width="180">
          <template #default="{ row }">
            <span class="kv-num">{{ formatTime(row.last_check_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button-group>
              <el-button size="small" @click="checkController(row)">
                检查
              </el-button>
              <el-button size="small" type="primary" @click="showDiscoverDialog(row)">
                发现集群
              </el-button>
              <el-button size="small" @click="showEditDialog(row)">
                编辑
              </el-button>
              <el-button size="small" type="danger" @click="deleteController(row)">
                删除
              </el-button>
            </el-button-group>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Add/Edit Dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingController ? '编辑 Controller' : '添加 Controller'"
      width="500px"
    >
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="Controller 显示名称" />
        </el-form-item>
        <el-form-item label="地址" prop="address">
          <el-input
            v-model="form.address"
            placeholder="http://host:port"
            :disabled="!!editingController"
          />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="3"
            placeholder="可选描述"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitting">
          {{ editingController ? '保存' : '添加' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- Discover Dialog -->
    <el-dialog
      v-model="discoverDialogVisible"
      title="发现集群"
      width="700px"
    >
      <div v-loading="discovering">
        <el-alert
          v-if="discoverError"
          :title="discoverError"
          type="error"
          show-icon
          style="margin-bottom: 16px"
        />

        <div v-if="discoveredNamespaces.length > 0">
          <p style="margin-bottom: 12px">
            发现 <strong>{{ discoveredNamespaces.length }}</strong> 个命名空间，
            共 <strong>{{ totalDiscoveredClusters }}</strong> 个集群
          </p>

          <el-table
            :data="flattenedClusters"
            max-height="400"
            @selection-change="handleSelectionChange"
          >
            <el-table-column type="selection" width="50" />
            <el-table-column prop="namespace" label="Namespace" width="150" />
            <el-table-column prop="cluster" label="Cluster" />
            <el-table-column prop="imported" label="状态" width="100">
              <template #default="{ row }">
                <el-tag v-if="row.imported" type="info" size="small">已导入</el-tag>
                <el-tag v-else type="success" size="small">可导入</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <el-empty v-else-if="!discovering && !discoverError" description="未发现集群" />
      </div>

      <template #footer>
        <el-button @click="discoverDialogVisible = false">关闭</el-button>
        <el-button
          type="primary"
          @click="importSelected"
          :loading="importing"
          :disabled="selectedClusters.length === 0"
        >
          导入选中 ({{ selectedClusters.length }})
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { controllersApi } from '@/api/controllers'
import dayjs from 'dayjs'

const controllers = ref([])
const loading = ref(false)

// Form dialog
const dialogVisible = ref(false)
const editingController = ref(null)
const formRef = ref(null)
const submitting = ref(false)
const form = ref({
  name: '',
  address: '',
  description: ''
})

const rules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  address: [{ required: true, message: '请输入地址', trigger: 'blur' }]
}

// Discover dialog
const discoverDialogVisible = ref(false)
const discovering = ref(false)
const discoverError = ref('')
const discoveredNamespaces = ref([])
const selectedClusters = ref([])
const importing = ref(false)
const currentController = ref(null)

const totalDiscoveredClusters = computed(() => {
  return discoveredNamespaces.value.reduce((sum, ns) => sum + ns.clusters.length, 0)
})

const flattenedClusters = computed(() => {
  const result = []
  for (const ns of discoveredNamespaces.value) {
    for (const cluster of ns.clusters) {
      result.push({
        namespace: ns.namespace,
        cluster: cluster,
        imported: false // TODO: check if already imported
      })
    }
  }
  return result
})

// Methods
const fetchControllers = async () => {
  loading.value = true
  try {
    const res = await controllersApi.list()
    console.log('Controllers response:', res)
    controllers.value = res  // response interceptor already returns data
  } catch (error) {
    ElMessage.error('获取 Controller 列表失败')
  } finally {
    loading.value = false
  }
}

const showAddDialog = () => {
  editingController.value = null
  form.value = { name: '', address: '', description: '' }
  dialogVisible.value = true
}

const showEditDialog = (row) => {
  editingController.value = row
  form.value = {
    name: row.name,
    address: row.address,
    description: row.description || ''
  }
  dialogVisible.value = true
}

const submitForm = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    if (editingController.value) {
      await controllersApi.update(editingController.value.id, {
        name: form.value.name,
        description: form.value.description
      })
      ElMessage.success('更新成功')
    } else {
      await controllersApi.create(form.value)
      ElMessage.success('添加成功')
    }
    dialogVisible.value = false
    fetchControllers()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '操作失败')
  } finally {
    submitting.value = false
  }
}

const checkController = async (row) => {
  try {
    const res = await controllersApi.check(row.id)
    if (res.success) {
      ElMessage.success('Controller 在线')
    } else {
      ElMessage.warning('Controller 离线: ' + (res.error || ''))
    }
    fetchControllers()
  } catch (error) {
    ElMessage.error('检查失败')
  }
}

const deleteController = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除 Controller "${row.name}" 吗？关联的集群不会被删除，但会解除关联。`,
      '确认删除',
      { type: 'warning' }
    )
    await controllersApi.delete(row.id)
    ElMessage.success('删除成功')
    fetchControllers()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const showDiscoverDialog = async (row) => {
  currentController.value = row
  discoverDialogVisible.value = true
  discovering.value = true
  discoverError.value = ''
  discoveredNamespaces.value = []
  selectedClusters.value = []

  try {
    const res = await controllersApi.discover(row.id)
    discoveredNamespaces.value = res.namespaces
  } catch (error) {
    discoverError.value = error.response?.data?.detail || '发现集群失败'
  } finally {
    discovering.value = false
  }
}

const handleSelectionChange = (selection) => {
  selectedClusters.value = selection.filter(item => !item.imported)
}

const importSelected = async () => {
  if (selectedClusters.value.length === 0) return

  importing.value = true
  try {
    const clusters = selectedClusters.value.map(item => ({
      namespace: item.namespace,
      cluster: item.cluster
    }))

    const res = await controllersApi.import(currentController.value.id, { clusters })

    if (res.imported_count > 0) {
      ElMessage.success(`成功导入 ${res.imported_count} 个集群`)
    }
    if (res.failed_count > 0) {
      const errors = res.results
        .filter(r => !r.success)
        .map(r => `${r.namespace}/${r.cluster}: ${r.error}`)
        .join('\n')
      ElMessage.warning(`${res.failed_count} 个集群导入失败:\n${errors}`)
    }

    discoverDialogVisible.value = false
    fetchControllers()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '导入失败')
  } finally {
    importing.value = false
  }
}

const getStatusType = (status) => {
  const map = {
    ONLINE: 'success',
    OFFLINE: 'warning',
    ERROR: 'danger',
    UNKNOWN: 'info'
  }
  return map[status] || 'info'
}

const getStatusText = (status) => {
  const map = {
    ONLINE: '在线',
    OFFLINE: '离线',
    ERROR: '错误',
    UNKNOWN: '未知'
  }
  return map[status] || status
}

const formatTime = (time) => {
  if (!time) return '-'
  return dayjs(time).format('YYYY-MM-DD HH:mm:ss')
}

onMounted(() => {
  fetchControllers()
})
</script>

<style scoped>
.controllers-container {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
}
</style>
