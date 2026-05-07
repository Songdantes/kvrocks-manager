<template>
  <div class="cluster-detail" v-loading="loading">
    <template v-if="cluster">
      <!-- Header -->
      <el-card class="header-card">
        <div class="cluster-header">
          <div class="cluster-info">
            <h2>{{ cluster.name }}</h2>
            <div class="cluster-meta">
              <el-tag :type="cluster.cluster_type === 'master_slave' ? 'primary' : 'success'" size="small">
                {{ cluster.cluster_type === 'master_slave' ? '主从集群' : '分片集群' }}
              </el-tag>
              <el-tag :type="getStatusType(cluster.status)" size="small">
                {{ getStatusText(cluster.status) }}
              </el-tag>
              <span class="meta-item">{{ cluster.node_count }} 个节点</span>
              <span class="meta-item">创建于 {{ formatTime(cluster.created_at) }}</span>
            </div>
            <p class="description" v-if="cluster.description">{{ cluster.description }}</p>
          </div>
          <div class="cluster-actions">
            <el-button @click="refreshStatus">
              <el-icon><Refresh /></el-icon> 刷新状态
            </el-button>
            <el-button type="primary" @click="goToTopology" v-if="cluster.cluster_type === 'sharding'">
              <el-icon><DataLine /></el-icon> 集群拓扑
            </el-button>
            <el-button type="success" @click="showImportDialog = true" v-if="cluster.cluster_type === 'sharding' && !hasNodes">
              <el-icon><Download /></el-icon> 导入集群
            </el-button>
            <el-button type="warning" @click="showCreateClusterDialog = true" v-if="cluster.cluster_type === 'sharding' && !hasNodes">
              <el-icon><Plus /></el-icon> 新建集群
            </el-button>
            <el-button type="primary" @click="showAddNodeDialog = true" v-if="cluster.cluster_type === 'master_slave'">
              <el-icon><Plus /></el-icon> 添加节点
            </el-button>
          </div>
        </div>
      </el-card>

      <!-- Nodes -->
      <el-card class="nodes-card">
        <template #header>
          <span>节点列表</span>
        </template>
        <el-table :data="cluster.nodes" style="width: 100%">
          <el-table-column prop="host" label="地址" width="200">
            <template #default="{ row }">
              <span class="font-mono">{{ row.host }}:{{ row.port }}</span>
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
              <el-tag :type="getNodeStatusType(row.status)" size="small">
                {{ getNodeStatusText(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="300">
            <template #default="{ row }">
              <el-button type="primary" link @click="pingNode(row)">Ping</el-button>
              <el-button type="primary" link @click="showNodeInfo(row)">Info</el-button>
              <el-button type="primary" link @click="showNodeConfig(row)">配置</el-button>
              <el-button type="primary" link @click="showCommand(row)">执行命令</el-button>
              <el-button type="danger" link @click="deleteNode(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </template>

    <!-- Add Node Dialog (for master_slave) -->
    <el-dialog v-model="showAddNodeDialog" title="添加节点" width="500px">
      <el-form
        ref="nodeFormRef"
        :model="nodeForm"
        :rules="nodeRules"
        label-width="100px"
      >
        <el-form-item label="主机地址" prop="host">
          <el-input v-model="nodeForm.host" placeholder="IP地址或主机名" />
        </el-form-item>
        <el-form-item label="端口" prop="port">
          <el-input-number v-model="nodeForm.port" :min="1" :max="65535" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="nodeForm.password" type="password" placeholder="可选" show-password />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-radio-group v-model="nodeForm.role">
            <el-radio value="master">主节点</el-radio>
            <el-radio value="slave">从节点</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddNodeDialog = false">取消</el-button>
        <el-button type="primary" :loading="adding" @click="handleAddNode">添加</el-button>
      </template>
    </el-dialog>

    <!-- Import Cluster Dialog (for sharding) -->
    <el-dialog v-model="showImportDialog" title="导入集群" width="600px">
      <el-form
        ref="importFormRef"
        :model="importForm"
        :rules="importRules"
        label-width="100px"
      >
        <el-form-item label="节点地址" prop="nodes">
          <el-input
            v-model="importForm.nodes"
            type="textarea"
            :rows="4"
            placeholder="输入节点地址，每行一个，格式: host:port&#10;例如:&#10;10.0.0.1:6379&#10;10.0.0.2:6379"
          />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="importForm.password" type="password" placeholder="集群密码（可选）" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showImportDialog = false">取消</el-button>
        <el-button type="primary" :loading="importing" @click="handleImport">导入</el-button>
      </template>
    </el-dialog>

    <!-- Create Cluster Dialog (for sharding) -->
    <el-dialog v-model="showCreateClusterDialog" title="新建集群" width="600px">
      <el-form
        ref="createClusterFormRef"
        :model="createClusterForm"
        :rules="createClusterRules"
        label-width="100px"
      >
        <el-form-item label="节点地址" prop="nodes">
          <el-input
            v-model="createClusterForm.nodes"
            type="textarea"
            :rows="4"
            placeholder="输入节点地址，每行一个，格式: host:port&#10;例如:&#10;10.0.0.1:6379&#10;10.0.0.2:6379&#10;10.0.0.3:6379"
          />
        </el-form-item>
        <el-form-item label="副本数" prop="replicas">
          <el-input-number v-model="createClusterForm.replicas" :min="0" :max="10" />
          <span style="margin-left: 10px; color: var(--kv-text-tertiary)">每个分片的节点数量</span>
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="createClusterForm.password" type="password" placeholder="集群密码（可选）" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateClusterDialog = false">取消</el-button>
        <el-button type="primary" :loading="creatingCluster" @click="handleCreateCluster">创建</el-button>
      </template>
    </el-dialog>

    <!-- Node Info Dialog -->
    <el-dialog v-model="showInfoDialog" title="节点信息" width="800px">
      <pre class="info-content">{{ nodeInfo }}</pre>
    </el-dialog>

    <!-- Node Config Dialog -->
    <el-dialog v-model="showConfigDialog" title="节点配置" width="800px">
      <div v-loading="configLoading">
        <el-table :data="configList" max-height="400">
          <el-table-column prop="key" label="配置项" width="300" />
          <el-table-column prop="value" label="值" />
        </el-table>
      </div>
    </el-dialog>

    <!-- Command Dialog -->
    <el-dialog v-model="showCommandDialog" title="执行命令" width="600px">
      <el-form @submit.prevent="executeCommand">
        <el-form-item label="命令">
          <el-input
            v-model="commandInput"
            placeholder="输入 Redis 命令，如: INFO, GET key, DBSIZE"
            @keyup.enter="executeCommand"
          />
        </el-form-item>
      </el-form>
      <div class="command-result" v-if="commandResult !== null">
        <h4>执行结果:</h4>
        <pre>{{ commandResult }}</pre>
      </div>
      <template #footer>
        <el-button @click="showCommandDialog = false">关闭</el-button>
        <el-button type="primary" :loading="executing" @click="executeCommand">执行</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { clusterApi, nodeApi } from '@/api/cluster'
import { scalingApi } from '@/api/scaling'
import dayjs from 'dayjs'

const route = useRoute()
const router = useRouter()
const clusterId = route.params.id

const loading = ref(true)
const adding = ref(false)
const importing = ref(false)
const creatingCluster = ref(false)
const executing = ref(false)
const configLoading = ref(false)
const cluster = ref(null)

const hasNodes = computed(() => {
  return cluster.value?.nodes?.length > 0
})

const showAddNodeDialog = ref(false)
const showImportDialog = ref(false)
const showCreateClusterDialog = ref(false)
const showInfoDialog = ref(false)
const showConfigDialog = ref(false)
const showCommandDialog = ref(false)

const nodeFormRef = ref(null)
const nodeForm = reactive({
  host: '',
  port: 6666,
  password: '',
  role: 'master'
})

const nodeRules = {
  host: [{ required: true, message: '请输入主机地址', trigger: 'blur' }],
  port: [{ required: true, message: '请输入端口', trigger: 'blur' }],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }]
}

const importFormRef = ref(null)
const importForm = reactive({
  nodes: '',
  password: ''
})

const importRules = {
  nodes: [{ required: true, message: '请输入节点地址', trigger: 'blur' }]
}

const createClusterFormRef = ref(null)
const createClusterForm = reactive({
  nodes: '',
  replicas: 0,
  password: ''
})

const createClusterRules = {
  nodes: [{ required: true, message: '请输入节点地址', trigger: 'blur' }]
}

const currentNode = ref(null)
const nodeInfo = ref('')
const configList = ref([])
const commandInput = ref('')
const commandResult = ref(null)

function getStatusType(status) {
  const types = { running: 'success', stopped: 'info', error: 'danger', deploying: 'warning' }
  return types[status] || 'info'
}

function getStatusText(status) {
  const texts = { running: '运行中', stopped: '已停止', error: '异常', deploying: '部署中' }
  return texts[status] || status
}

function getNodeStatusType(status) {
  const types = { running: 'success', stopped: 'info', error: 'danger', syncing: 'warning' }
  return types[status] || 'info'
}

function getNodeStatusText(status) {
  const texts = { running: '运行中', stopped: '已停止', error: '异常', syncing: '同步中' }
  return texts[status] || status
}

function formatTime(time) {
  return dayjs(time).format('YYYY-MM-DD HH:mm:ss')
}

function parseNodes(nodesStr) {
  return nodesStr
    .split('\n')
    .map(line => line.trim())
    .filter(line => line && line.includes(':'))
}

async function fetchCluster() {
  loading.value = true
  try {
    cluster.value = await clusterApi.get(clusterId)
  } catch (error) {
    console.error('Failed to fetch cluster:', error)
  } finally {
    loading.value = false
  }
}

async function refreshStatus() {
  try {
    await clusterApi.refreshStatus(clusterId)
    ElMessage.success('状态已刷新')
    await fetchCluster()
  } catch (error) {
    console.error('Failed to refresh status:', error)
  }
}

function goToTopology() {
  router.push(`/clusters/${clusterId}/scaling/topology`)
}

async function handleAddNode() {
  if (!nodeFormRef.value) return

  await nodeFormRef.value.validate(async (valid) => {
    if (!valid) return

    adding.value = true
    try {
      await nodeApi.create({
        cluster_id: parseInt(clusterId),
        ...nodeForm
      })
      ElMessage.success('节点添加成功')
      showAddNodeDialog.value = false
      nodeForm.host = ''
      nodeForm.port = 6666
      nodeForm.password = ''
      nodeForm.role = 'master'
      await fetchCluster()
    } catch (error) {
      console.error('Failed to add node:', error)
    } finally {
      adding.value = false
    }
  })
}

async function handleImport() {
  if (!importFormRef.value) return

  await importFormRef.value.validate(async (valid) => {
    if (!valid) return

    const nodes = parseNodes(importForm.nodes)
    if (nodes.length === 0) {
      ElMessage.error('请输入有效的节点地址')
      return
    }

    importing.value = true
    try {
      await scalingApi.importCluster(clusterId, {
        nodes,
        password: importForm.password || undefined
      })
      ElMessage.success('集群导入成功')
      showImportDialog.value = false
      importForm.nodes = ''
      importForm.password = ''
      await fetchCluster()
    } catch (error) {
      console.error('Failed to import cluster:', error)
    } finally {
      importing.value = false
    }
  })
}

async function handleCreateCluster() {
  if (!createClusterFormRef.value) return

  await createClusterFormRef.value.validate(async (valid) => {
    if (!valid) return

    const nodes = parseNodes(createClusterForm.nodes)
    if (nodes.length === 0) {
      ElMessage.error('请输入有效的节点地址')
      return
    }

    creatingCluster.value = true
    try {
      await scalingApi.createCluster(clusterId, {
        nodes,
        replicas: createClusterForm.replicas,
        password: createClusterForm.password || undefined
      })
      ElMessage.success('集群创建成功')
      showCreateClusterDialog.value = false
      createClusterForm.nodes = ''
      createClusterForm.replicas = 0
      createClusterForm.password = ''
      await fetchCluster()
    } catch (error) {
      console.error('Failed to create cluster:', error)
    } finally {
      creatingCluster.value = false
    }
  })
}

async function pingNode(node) {
  try {
    const result = await nodeApi.ping(node.id)
    if (result.alive) {
      ElMessage.success('节点响应正常')
    } else {
      ElMessage.error('节点无响应')
    }
    await fetchCluster()
  } catch (error) {
    ElMessage.error('Ping 失败')
  }
}

async function showNodeInfo(node) {
  currentNode.value = node
  try {
    const result = await nodeApi.info(node.id)
    if (result.success) {
      nodeInfo.value = JSON.stringify(result.info, null, 2)
    } else {
      nodeInfo.value = `Error: ${result.error}`
    }
    showInfoDialog.value = true
  } catch (error) {
    ElMessage.error('获取节点信息失败')
  }
}

async function showNodeConfig(node) {
  currentNode.value = node
  configLoading.value = true
  showConfigDialog.value = true
  try {
    const result = await nodeApi.getConfig(node.id, '*')
    if (result.success) {
      configList.value = Object.entries(result.config).map(([key, value]) => ({ key, value }))
    } else {
      configList.value = []
      ElMessage.error(result.error)
    }
  } catch (error) {
    configList.value = []
    ElMessage.error('获取配置失败')
  } finally {
    configLoading.value = false
  }
}

function showCommand(node) {
  currentNode.value = node
  commandInput.value = ''
  commandResult.value = null
  showCommandDialog.value = true
}

async function executeCommand() {
  if (!commandInput.value.trim()) return

  const parts = commandInput.value.trim().split(/\s+/)
  const command = parts[0]
  const args = parts.slice(1)

  executing.value = true
  try {
    const result = await nodeApi.executeCommand(currentNode.value.id, command, args)
    if (result.success) {
      commandResult.value = typeof result.result === 'object'
        ? JSON.stringify(result.result, null, 2)
        : String(result.result)
    } else {
      commandResult.value = `Error: ${result.error}`
    }
  } catch (error) {
    commandResult.value = `Error: ${error.message}`
  } finally {
    executing.value = false
  }
}

async function deleteNode(node) {
  try {
    await ElMessageBox.confirm(
      `确定要删除节点 ${node.host}:${node.port} 吗？`,
      '删除确认',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await nodeApi.delete(node.id)
    ElMessage.success('删除成功')
    await fetchCluster()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Failed to delete node:', error)
    }
  }
}

onMounted(() => {
  fetchCluster()
})
</script>

<style scoped>
.header-card {
  margin-bottom: 20px;
}

.cluster-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.cluster-info h2 {
  margin: 0 0 10px 0;
}

.cluster-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.meta-item {
  color: var(--kv-text-tertiary);
  font-size: 14px;
}

.description {
  color: var(--kv-text-secondary);
  margin: 0;
}

.cluster-actions {
  display: flex;
  gap: 10px;
}

.nodes-card {
  margin-bottom: 20px;
}

.info-content {
  background: var(--kv-bg-overlay);
  padding: 15px;
  border-radius: var(--kv-radius-sm);
  max-height: 500px;
  overflow: auto;
  font-family: var(--kv-font-mono);
  font-size: 12px;
  color: var(--kv-text-secondary);
}

.command-result {
  margin-top: 20px;
}

.command-result h4 {
  margin: 0 0 10px 0;
  color: var(--kv-text-primary);
}

.command-result pre {
  background: var(--kv-bg-overlay);
  padding: 15px;
  border-radius: var(--kv-radius-sm);
  max-height: 300px;
  overflow: auto;
  font-family: var(--kv-font-mono);
  font-size: 12px;
  color: var(--kv-text-secondary);
}
</style>
