<template>
  <div class="dashboard">
    <!-- Stats Cards — top row: cluster/node overview -->
    <div class="stats-grid stagger-enter">
      <div class="stat-card">
        <div class="stat-icon stat-icon--accent">
          <el-icon><Grid /></el-icon>
        </div>
        <div class="stat-body">
          <div class="stat-value font-mono">{{ stats.total_clusters }}</div>
          <div class="stat-label">集群总数</div>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon stat-icon--success">
          <el-icon><Monitor /></el-icon>
        </div>
        <div class="stat-body">
          <div class="stat-value font-mono">
            <span>{{ stats.running_nodes }}</span>
            <span class="stat-sep">/</span>
            <span class="stat-total">{{ stats.total_nodes }}</span>
          </div>
          <div class="stat-label">运行节点</div>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon stat-icon--warning">
          <el-icon><Warning /></el-icon>
        </div>
        <div class="stat-body">
          <div class="stat-value font-mono">{{ stats.error_nodes }}</div>
          <div class="stat-label">异常节点</div>
        </div>
      </div>
    </div>

    <!-- Content: Cluster List -->
    <el-row :gutter="20" class="content-row">
      <el-col :span="24">
        <el-card class="content-card">
          <template #header>
            <div class="card-header">
              <span class="card-title">集群列表</span>
              <el-button type="primary" size="small" @click="$router.push('/clusters')">
                查看全部
              </el-button>
            </div>
          </template>
          <el-table :data="clusters" style="width: 100%">
            <el-table-column prop="name" label="集群名称">
              <template #default="{ row }">
                <span class="font-mono">{{ row.name }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="cluster_type" label="类型">
              <template #default="{ row }">
                <el-tag :type="row.cluster_type === 'master_slave' ? 'primary' : 'success'" size="small">
                  {{ row.cluster_type === 'master_slave' ? '主从' : '分片' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="节点数" width="120">
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
            <el-table-column label="操作" width="100">
              <template #default="{ row }">
                <el-button type="primary" link @click="$router.push(`/clusters/${row.id}`)">
                  详情
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { clusterApi } from '@/api/cluster'

const stats = ref({
  total_clusters: 0,
  total_nodes: 0,
  running_nodes: 0,
  error_nodes: 0
})

const clusters = ref([])

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

async function fetchData() {
  try {
    const clusterData = await clusterApi.list({ limit: 5 })
    clusters.value = clusterData

    // Compute stats from cluster data
    const allClusters = await clusterApi.list({ limit: 100 })
    stats.value.total_clusters = allClusters.length || 0
    let totalNodes = 0
    let runningNodes = 0
    let errorNodes = 0
    for (const cluster of allClusters) {
      const nodeCount = (cluster.master_count || 0) + (cluster.slave_count || 0)
      totalNodes += nodeCount
      if (cluster.status === 'running') {
        runningNodes += nodeCount
      } else if (cluster.status === 'error') {
        errorNodes += nodeCount
      }
    }
    stats.value.total_nodes = totalNodes
    stats.value.running_nodes = runningNodes
    stats.value.error_nodes = errorNodes
  } catch (error) {
    console.error('Failed to fetch dashboard data:', error)
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.dashboard {
  padding: 0;
}

/* ── Stats Grid: 3 equal columns ── */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.stat-card {
  background: var(--kv-bg-elevated);
  border: 1px solid var(--kv-border-subtle);
  border-radius: var(--kv-radius-md);
  padding: 24px;
  display: flex;
  align-items: center;
  gap: 16px;
  position: relative;
  overflow: hidden;
  transition: border-color var(--kv-dur-base) var(--kv-ease),
              box-shadow var(--kv-dur-base) var(--kv-ease);
}

.stat-card:hover {
  border-color: var(--kv-border-default);
  box-shadow: var(--kv-shadow-sm);
}

.stat-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--kv-radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
}

.stat-icon--accent {
  background: var(--kv-accent-muted);
  color: var(--kv-accent);
}

.stat-icon--success {
  background: var(--kv-success-muted);
  color: var(--kv-success);
}

.stat-icon--warning {
  background: var(--kv-warning-muted);
  color: var(--kv-warning);
}

.stat-body {
  flex: 1;
  min-width: 0;
}

.stat-value {
  font-size: 26px;
  font-weight: 700;
  color: var(--kv-text-primary);
  line-height: 1.2;
}

.stat-sep {
  color: var(--kv-text-tertiary);
  margin: 0 2px;
  font-weight: 400;
}

.stat-total {
  color: var(--kv-text-secondary);
  font-weight: 400;
}

.stat-label {
  font-size: 13px;
  color: var(--kv-text-tertiary);
  margin-top: 4px;
}

/* ── Content section ── */
.content-row {
  margin-top: 0;
}

.content-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-title {
  font-weight: 600;
  color: var(--kv-text-primary);
}

/* ── Responsive ── */
@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
}
</style>
