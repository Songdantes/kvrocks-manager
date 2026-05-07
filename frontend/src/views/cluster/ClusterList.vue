<template>
  <div class="cluster-list">
    <div class="page-header">
      <div>
        <h2>集群列表</h2>
        <div class="page-subtitle">快速检索、查看状态并进入详情管理</div>
      </div>
      <el-button type="primary" @click="showCreateDialog = true">
        <el-icon><Plus /></el-icon>
        添加集群
      </el-button>
    </div>

    <el-card class="content-card">
      <div class="filter-bar">
        <el-form :inline="true" class="filter-form">
          <el-form-item label="集群">
            <el-select
              v-model="filters.cluster_id"
              placeholder="全部"
              clearable
              filterable
              @change="handleClusterFilter"
              style="width: 240px"
            >
              <el-option
                v-for="cluster in allClusters"
                :key="cluster.id"
                :label="cluster.name"
                :value="cluster.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="类型">
            <el-select v-model="filters.cluster_type" placeholder="全部" clearable @change="fetchClusters" style="width: 160px">
              <el-option label="主从" value="master_slave" />
              <el-option label="分片" value="sharding" />
            </el-select>
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="filters.status" placeholder="全部" clearable @change="fetchClusters" style="width: 160px">
              <el-option label="运行中" value="running" />
              <el-option label="已停止" value="stopped" />
              <el-option label="异常" value="error" />
            </el-select>
          </el-form-item>
        </el-form>
      </div>

      <el-table :data="clusters" v-loading="loading" style="width: 100%">
        <el-table-column prop="name" label="集群名称" min-width="150">
          <template #default="{ row }">
            <el-link type="primary" @click="$router.push(`/clusters/${row.id}`)">
              {{ row.name }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column prop="controller_name" label="所属Controller" width="180">
          <template #default="{ row }">
            <span v-if="row.controller_name">{{ row.controller_name }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="cluster_type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="row.cluster_type === 'master_slave' ? 'primary' : 'success'" size="small">
              {{ row.cluster_type === 'master_slave' ? '主从' : '分片' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="节点" width="120">
          <template #default="{ row }">
            <span class="font-mono">{{ row.master_count }}主 / {{ row.slave_count }}从</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column prop="created_at" label="创建时间" width="170">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="$router.push(`/clusters/${row.id}`)">
              详情
            </el-button>
            <el-button type="primary" link @click="refreshStatus(row)">
              刷新状态
            </el-button>
            <el-button type="danger" link @click="handleDelete(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Create Dialog -->
    <el-dialog v-model="showCreateDialog" title="添加集群" width="500px">
      <el-form
        ref="formRef"
        :model="createForm"
        :rules="createRules"
        label-width="100px"
      >
        <el-form-item label="集群名称" prop="name">
          <el-input v-model="createForm.name" placeholder="请输入集群名称" />
        </el-form-item>
        <el-form-item label="集群类型" prop="cluster_type">
          <el-radio-group v-model="createForm.cluster_type">
            <el-radio value="master_slave">主从集群</el-radio>
            <el-radio value="sharding">分片集群</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="Controller" prop="controller_id">
          <el-select
            v-model="createForm.controller_id"
            placeholder="请选择 Controller"
            style="width: 100%"
            filterable
          >
            <el-option
              v-for="ctrl in controllers"
              :key="ctrl.id"
              :label="`${ctrl.name} (${ctrl.address})`"
              :value="ctrl.id"
              :disabled="ctrl.status !== 'ONLINE'"
            >
              <span>{{ ctrl.name }}</span>
              <span style="float: right; color: var(--kv-text-tertiary); font-size: 12px">
                {{ ctrl.address }}
                <el-tag :type="ctrl.status === 'ONLINE' ? 'success' : 'danger'" size="small" style="margin-left: 8px">
                  {{ ctrl.status === 'ONLINE' ? '在线' : '离线' }}
                </el-tag>
              </span>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="createForm.description"
            type="textarea"
            :rows="3"
            placeholder="请输入集群描述"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="handleCreate">
          创建
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { clusterApi } from '@/api/cluster'
import { controllersApi } from '@/api/controllers'
import dayjs from 'dayjs'

const loading = ref(false)
const creating = ref(false)
const clusters = ref([])
const allClusters = ref([])
const controllers = ref([])
const showCreateDialog = ref(false)
const formRef = ref(null)

const filters = reactive({
  cluster_id: null,
  cluster_type: '',
  status: ''
})

const createForm = reactive({
  name: '',
  cluster_type: 'sharding',
  controller_id: null,
  description: ''
})

const createRules = {
  name: [
    { required: true, message: '请输入集群名称', trigger: 'blur' },
    { min: 2, max: 100, message: '长度在 2 到 100 个字符', trigger: 'blur' }
  ],
  cluster_type: [
    { required: true, message: '请选择集群类型', trigger: 'change' }
  ],
  controller_id: [
    { required: true, message: '请选择 Controller', trigger: 'change' }
  ]
}

function getStatusType(status) {
  const types = {
    running: 'success',
    stopped: 'info',
    error: 'danger',
    deploying: 'warning'
  }
  return types[status] || 'info'
}

function getStatusText(status) {
  const texts = {
    running: '运行中',
    stopped: '已停止',
    error: '异常',
    deploying: '部署中'
  }
  return texts[status] || status
}

function formatTime(time) {
  return dayjs(time).format('YYYY-MM-DD HH:mm:ss')
}

async function fetchClusters() {
  loading.value = true
  try {
    const params = {}
    if (filters.cluster_type) params.cluster_type = filters.cluster_type
    if (filters.status) params.status = filters.status

    clusters.value = await clusterApi.list(params)
  } catch (error) {
    console.error('Failed to fetch clusters:', error)
  } finally {
    loading.value = false
  }
}

async function fetchAllClusters() {
  try {
    allClusters.value = await clusterApi.list({ limit: 100 })
  } catch (error) {
    console.error('Failed to fetch all clusters:', error)
  }
}

function handleClusterFilter() {
  if (filters.cluster_id) {
    // Filter to show only the selected cluster
    const selected = allClusters.value.find(c => c.id === filters.cluster_id)
    clusters.value = selected ? [selected] : []
  } else {
    // No filter, show all clusters
    fetchClusters()
  }
}

async function fetchControllers() {
  try {
    controllers.value = await controllersApi.list()
  } catch (error) {
    console.error('Failed to fetch controllers:', error)
  }
}

async function refreshStatus(row) {
  try {
    await clusterApi.refreshStatus(row.id)
    ElMessage.success('状态已刷新')
    await fetchClusters()
  } catch (error) {
    console.error('Failed to refresh status:', error)
  }
}

async function handleCreate() {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    creating.value = true
    try {
      await clusterApi.create({
        name: createForm.name,
        cluster_type: createForm.cluster_type,
        description: createForm.description,
        controller_id: createForm.controller_id
      })
      ElMessage.success('集群创建成功')
      showCreateDialog.value = false
      // Reset form
      createForm.name = ''
      createForm.cluster_type = 'sharding'
      createForm.controller_id = null
      createForm.description = ''
      await fetchClusters()
    } catch (error) {
      console.error('Failed to create cluster:', error)
    } finally {
      creating.value = false
    }
  })
}

async function handleDelete(row) {
  if (row.status === 'running') {
    ElMessage.warning('请先停止集群再删除')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定要删除集群 "${row.name}" 吗？此操作不可恢复。`,
      '删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    await clusterApi.delete(row.id)
    ElMessage.success('删除成功')
    await fetchClusters()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Failed to delete cluster:', error)
    }
  }
}

onMounted(() => {
  fetchAllClusters()
  fetchClusters()
  fetchControllers()
})
</script>

<style scoped>
.filter-bar {
  padding: 12px 0 8px;
}

.filter-form {
  margin-bottom: 12px;
}

.text-muted {
  color: var(--kv-text-tertiary);
}
</style>
