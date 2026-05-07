<template>
  <div class="node-list">
    <div class="page-header">
      <div>
        <h2>节点管理</h2>
        <div class="page-subtitle">批量选择节点并执行快速连通性检查</div>
      </div>
      <el-button type="primary" @click="batchPing" :disabled="selectedNodes.length === 0">
        批量 Ping
      </el-button>
    </div>

    <el-card class="content-card">
      <div class="filter-bar">
        <el-form :inline="true" class="filter-form">
        <el-form-item label="集群">
          <el-select v-model="filters.cluster_id" placeholder="全部" clearable filterable @change="fetchNodes" style="width: 240px">
            <el-option
              v-for="cluster in clusters"
              :key="cluster.id"
              :label="cluster.name"
              :value="cluster.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" clearable @change="fetchNodes" style="width: 160px">
            <el-option label="运行中" value="running" />
            <el-option label="已停止" value="stopped" />
            <el-option label="异常" value="error" />
            <el-option label="同步中" value="syncing" />
          </el-select>
        </el-form-item>
        </el-form>
      </div>

      <!-- Table -->
      <el-table
        :data="nodes"
        v-loading="loading"
        style="width: 100%"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="55" />
        <el-table-column prop="host" label="地址" width="200">
          <template #default="{ row }">
            <span class="kv-num">{{ row.host }}:{{ row.port }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="cluster_id" label="所属集群" width="150">
          <template #default="{ row }">
            <el-link type="primary" @click="$router.push(`/clusters/${row.cluster_id}`)">
              {{ getClusterName(row.cluster_id) }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column prop="role" label="角色" width="100">
          <template #default="{ row }">
            <el-tag :type="row.role === 'master' ? 'danger' : 'info'" size="small">
              {{ row.role === 'master' ? '主节点' : '从节点' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170">
          <template #default="{ row }">
            <span class="kv-num">{{ formatTime(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button type="primary" link @click="pingNode(row)">Ping</el-button>
            <el-button type="primary" link @click="$router.push(`/clusters/${row.cluster_id}`)">
              查看集群
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { nodeApi, clusterApi } from '@/api/cluster'
import dayjs from 'dayjs'

const loading = ref(false)
const nodes = ref([])
const clusters = ref([])
const selectedNodes = ref([])

const filters = reactive({
  cluster_id: null,
  status: ''
})

function getStatusType(status) {
  const types = { running: 'success', stopped: 'info', error: 'danger', syncing: 'warning' }
  return types[status] || 'info'
}

function getStatusText(status) {
  const texts = { running: '运行中', stopped: '已停止', error: '异常', syncing: '同步中' }
  return texts[status] || status
}

function formatTime(time) {
  return dayjs(time).format('YYYY-MM-DD HH:mm:ss')
}

function getClusterName(clusterId) {
  const cluster = clusters.value.find(c => c.id === clusterId)
  return cluster ? cluster.name : '-'
}

function handleSelectionChange(selection) {
  selectedNodes.value = selection
}

async function fetchClusters() {
  try {
    clusters.value = await clusterApi.list({ limit: 100 })
  } catch (error) {
    console.error('Failed to fetch clusters:', error)
  }
}

async function fetchNodes() {
  loading.value = true
  try {
    const params = {}
    if (filters.cluster_id) params.cluster_id = filters.cluster_id
    if (filters.status) params.status = filters.status

    nodes.value = await nodeApi.list(params)
  } catch (error) {
    console.error('Failed to fetch nodes:', error)
  } finally {
    loading.value = false
  }
}

async function pingNode(node) {
  try {
    const result = await nodeApi.ping(node.id)
    if (result.alive) {
      ElMessage.success(`${node.host}:${node.port} 响应正常`)
    } else {
      ElMessage.error(`${node.host}:${node.port} 无响应`)
    }
    await fetchNodes()
  } catch (error) {
    ElMessage.error('Ping 失败')
  }
}

async function batchPing() {
  ElMessage.info(`正在 Ping ${selectedNodes.value.length} 个节点...`)
  for (const node of selectedNodes.value) {
    await pingNode(node)
  }
  ElMessage.success('批量 Ping 完成')
}

onMounted(async () => {
  await fetchClusters()
  await fetchNodes()
})
</script>

<style scoped>
.filter-bar {
  padding: 12px 0 8px;
}

.filter-form {
  margin-bottom: 12px;
}
</style>
