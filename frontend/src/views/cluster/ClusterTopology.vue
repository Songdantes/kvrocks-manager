<template>
  <div class="cluster-topology" v-loading="loading">
    <!-- Error State -->
    <el-card v-if="errorState" class="error-card">
      <el-result
        icon="warning"
        :title="errorState.title"
        :sub-title="errorState.message"
      >
        <template #extra>
          <el-button type="primary" @click="showImportDialog = true">
            <el-icon><Upload /></el-icon> 导入现有集群
          </el-button>
          <el-button @click="showCreateDialog = true">
            <el-icon><Plus /></el-icon> 创建新集群
          </el-button>
          <el-button @click="$router.back()">返回</el-button>
        </template>
      </el-result>
    </el-card>

    <!-- Normal Content -->
    <template v-else>
    <!-- Header -->
    <el-card class="header-card">
      <div class="header">
        <div class="header-left">
          <h2>集群拓扑 - {{ clusterName }}</h2>
          <el-tag v-if="topology" :type="topology.cluster_state === 'ok' ? 'success' : 'danger'" size="small">
            {{ topology.cluster_state === 'ok' ? '正常' : '异常' }}
          </el-tag>
          <el-tag type="info" size="small" v-if="topology">
            v{{ topology.version }}
          </el-tag>
        </div>
        <div class="header-right">
          <div class="auto-refresh">
            <span class="auto-refresh-label">自动刷新</span>
            <el-switch
              v-model="autoRefresh"
              @change="toggleAutoRefresh"
              :active-text="refreshIntervalText"
              active-color="#5b9cf5"
              inactive-color="#93c5fd"
            />
            <el-select
              v-if="autoRefresh"
              v-model="refreshSeconds"
              size="small"
              style="width: 80px; margin-left: 8px"
              @change="updateRefreshInterval"
            >
              <el-option :value="5" label="5秒" />
              <el-option :value="10" label="10秒" />
              <el-option :value="30" label="30秒" />
              <el-option :value="60" label="60秒" />
            </el-select>
          </div>
          <el-button @click="syncTopology" :loading="syncing">
            <el-icon><Refresh /></el-icon> 同步拓扑
          </el-button>
          <el-button type="success" @click="showAddShardDialog = true">
            <el-icon><Plus /></el-icon> 添加分片
          </el-button>
          <el-button type="primary" @click="showImportDialog = true" v-if="!topology?.shards?.length">
            <el-icon><Upload /></el-icon> 导入集群
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- Stats -->
    <el-row :gutter="20" class="stats-row">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ topology?.shard_count || 0 }}</div>
          <div class="stat-label">分片数</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ topology?.node_count || 0 }}</div>
          <div class="stat-label">节点总数</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ topology?.total_slots || 0 }}</div>
          <div class="stat-label">已分配槽位</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ topology?.total_slots || 0 }} / 16384</div>
          <div class="stat-label">槽位覆盖</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Suggestions -->
    <el-card class="suggestions-card" v-if="suggestions.length > 0">
      <template #header>
        <span>扩缩容建议</span>
      </template>
      <div class="suggestions-list">
        <el-alert
          v-for="(suggestion, index) in suggestions"
          :key="index"
          :title="suggestion.reason"
          :description="suggestion.recommendation"
          :type="getSuggestionType(suggestion.severity)"
          :closable="false"
          show-icon
          class="suggestion-item"
        />
      </div>
    </el-card>

    <!-- Shard List -->
    <el-card class="shards-card">
      <template #header>
        <span>分片列表</span>
      </template>

      <div v-if="!topology?.shards?.length" class="empty-state">
        <el-empty description="暂无分片数据">
          <el-button type="primary" @click="showImportDialog = true">导入现有集群</el-button>
        </el-empty>
      </div>

      <el-collapse v-else v-model="expandedShards">
        <el-collapse-item
          v-for="shard in topology.shards"
          :key="shard.index"
          :name="shard.index"
        >
          <template #title>
            <div class="shard-header">
              <span class="shard-title">分片 {{ shard.index }}</span>
              <el-tag type="primary" size="small">{{ getSlotsCount(shard) }} 槽位</el-tag>
              <el-tag type="info" size="small">{{ shard.nodes?.length || 0 }} 节点</el-tag>
              <el-tag v-if="shard.migrating_slot !== null && shard.migrating_slot !== undefined" type="warning" size="small">
                迁移中: {{ shard.migrating_slot }}
              </el-tag>
            </div>
          </template>

          <!-- Slot Distribution Bar -->
          <div class="slot-bar">
            <div class="slot-bar-label">
              <span>槽位范围:</span>
              <span class="slot-ranges">{{ formatSlotRanges(shard.slot_ranges) || '无' }}</span>
            </div>
            <el-progress
              :percentage="(getSlotsCount(shard) / 16384) * 100"
              :stroke-width="15"
              :show-text="false"
              :color="getProgressColor(getSlotsCount(shard))"
            />
          </div>

          <!-- Node List -->
          <el-table :data="shard.nodes" size="small" style="margin-top: 15px">
            <el-table-column prop="addr" label="地址" width="200" />
            <el-table-column prop="id" label="节点ID" width="200">
              <template #default="{ row }">
                <span class="node-id">{{ row.id?.substring(0, 16) }}...</span>
              </template>
            </el-table-column>
            <el-table-column prop="role" label="角色" width="100">
              <template #default="{ row }">
                <el-tag :type="row.role === 'master' ? 'danger' : 'info'" size="small">
                  {{ row.role === 'master' ? '主节点' : '从节点' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200">
              <template #default="{ row }">
                <el-button
                  v-if="row.role === 'slave'"
                  type="primary"
                  link
                  size="small"
                  @click="handleFailover(shard, row)"
                >主从切换</el-button>
                <el-button
                  type="danger"
                  link
                  size="small"
                  @click="handleRemoveNode(shard, row)"
                >移除</el-button>
              </template>
            </el-table-column>
          </el-table>

          <!-- Shard Actions -->
          <div class="shard-actions">
            <el-button size="small" @click="handleAddNode(shard)">
              <el-icon><Plus /></el-icon> 添加节点
            </el-button>
            <el-button size="small" @click="handleMigrateSlots(shard)" v-if="getSlotsCount(shard) > 0">
              <el-icon><Right /></el-icon> 迁移槽位
            </el-button>
            <el-button size="small" type="danger" @click="handleRemoveShard(shard)">
              <el-icon><Delete /></el-icon> 删除分片
            </el-button>
          </div>
        </el-collapse-item>
      </el-collapse>
    </el-card>
    </template>

    <!-- Import Cluster Dialog -->
    <el-dialog v-model="showImportDialog" title="导入集群到 Controller" width="500px">
      <el-alert
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 20px"
      >
        从已有的 KVrocks 集群节点导入拓扑信息到 kvrocks-controller
      </el-alert>
      <el-form :model="importForm" label-width="100px">
        <el-form-item label="节点地址" required>
          <el-input
            v-model="importForm.nodes"
            type="textarea"
            :rows="3"
            placeholder="每行一个节点地址，格式: host:port"
          />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="importForm.password" type="password" show-password placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showImportDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitImport">导入</el-button>
      </template>
    </el-dialog>

    <!-- Add Shard Dialog -->
    <el-dialog v-model="showAddShardDialog" title="添加分片" width="500px">
      <el-form :model="addShardForm" label-width="100px">
        <el-form-item label="节点地址" required>
          <el-input
            v-model="addShardForm.nodes"
            type="textarea"
            :rows="3"
            placeholder="每行一个节点地址，格式: host:port&#10;第一个节点将成为主节点，其他为从节点"
          />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="addShardForm.password" type="password" show-password placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddShardDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitAddShard">添加</el-button>
      </template>
    </el-dialog>

    <!-- Add Node Dialog -->
    <el-dialog v-model="showAddNodeDialog" title="添加节点" width="500px">
      <el-form :model="addNodeForm" label-width="100px">
        <el-form-item label="分片">
          <el-input :value="`分片 ${selectedShard?.index}`" disabled />
        </el-form-item>
        <el-form-item label="节点地址" required>
          <el-input v-model="addNodeForm.addr" placeholder="host:port" />
        </el-form-item>
        <el-form-item label="角色">
          <el-radio-group v-model="addNodeForm.role">
            <el-radio value="slave">从节点</el-radio>
            <el-radio value="master">主节点</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="addNodeForm.password" type="password" show-password placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddNodeDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitAddNode">添加</el-button>
      </template>
    </el-dialog>

    <!-- Migrate Slots Dialog -->
    <el-dialog v-model="showMigrateDialog" title="迁移槽位" width="500px">
      <el-form :model="migrateForm" label-width="100px">
        <el-form-item label="源分片">
          <el-input :value="`分片 ${selectedShard?.index}`" disabled />
        </el-form-item>
        <el-form-item label="目标分片" required>
          <el-select v-model="migrateForm.target_shard" placeholder="选择目标分片" style="width: 100%">
            <el-option
              v-for="shard in targetShards"
              :key="shard.index"
              :label="`分片 ${shard.index} (${getSlotsCount(shard)} 槽位)`"
              :value="shard.index"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="槽位范围" required>
          <el-row :gutter="10">
            <el-col :span="10">
              <el-input-number v-model="migrateForm.slot_start" :min="0" :max="16383" style="width: 100%" />
            </el-col>
            <el-col :span="4" class="text-center">至</el-col>
            <el-col :span="10">
              <el-input-number v-model="migrateForm.slot_stop" :min="0" :max="16383" style="width: 100%" />
            </el-col>
          </el-row>
        </el-form-item>
        <el-form-item label="仅元数据">
          <el-switch v-model="migrateForm.slot_only" />
          <div class="form-tip">开启后只迁移槽位元数据，不迁移实际数据</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showMigrateDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitMigrate">开始迁移</el-button>
      </template>
    </el-dialog>

    <!-- Failover Dialog -->
    <el-dialog v-model="showFailoverDialog" title="主从切换" width="500px">
      <el-alert
        type="warning"
        :closable="false"
        show-icon
        style="margin-bottom: 20px"
      >
        将节点 <strong>{{ selectedNode?.addr }}</strong> 提升为分片 {{ selectedShard?.index }} 的主节点
      </el-alert>
      <template #footer>
        <el-button @click="showFailoverDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitFailover">执行切换</el-button>
      </template>
    </el-dialog>

    <!-- Remove Shard Dialog -->
    <el-dialog v-model="showRemoveShardDialog" title="删除分片" width="500px">
      <el-alert
        type="danger"
        :closable="false"
        show-icon
        style="margin-bottom: 20px"
      >
        将删除分片 {{ selectedShard?.index }}
      </el-alert>
      <el-form :model="removeShardForm" label-width="120px" v-if="getSlotsCount(selectedShard) > 0">
        <el-form-item label="迁移槽位到">
          <el-select v-model="removeShardForm.target_shard_index" placeholder="选择目标分片" clearable style="width: 100%">
            <el-option
              v-for="shard in targetShards"
              :key="shard.index"
              :label="`分片 ${shard.index}`"
              :value="shard.index"
            />
          </el-select>
          <div class="form-tip">需要先迁移槽位才能删除分片</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRemoveShardDialog = false">取消</el-button>
        <el-button type="danger" :loading="submitting" @click="submitRemoveShard">确认删除</el-button>
      </template>
    </el-dialog>

    <!-- Create Cluster Dialog -->
    <el-dialog v-model="showCreateDialog" title="创建新集群" width="600px">
      <el-alert
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 20px"
      >
        在 kvrocks-controller 上创建新的集群
      </el-alert>
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="节点地址" required>
          <el-input
            v-model="createForm.nodes"
            type="textarea"
            :rows="4"
            placeholder="每行一个节点地址，格式: host:port&#10;至少需要3个节点"
          />
        </el-form-item>
        <el-form-item label="副本数">
          <el-input-number v-model="createForm.replicas" :min="0" :max="10" />
          <span style="margin-left: 10px; color: var(--kv-text-tertiary)">每个分片的节点数量</span>
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="createForm.password" type="password" show-password placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { scalingApi } from '@/api/scaling'

const route = useRoute()
const router = useRouter()
const clusterId = route.params.id

const loading = ref(true)
const syncing = ref(false)
const submitting = ref(false)
const topology = ref(null)
const suggestions = ref([])
const clusterName = ref('')
const errorState = ref(null)

const expandedShards = ref([0])

// Auto refresh
const autoRefresh = ref(false)
const refreshSeconds = ref(30)
const refreshIntervalText = computed(() => autoRefresh.value ? `${refreshSeconds.value}s` : '')

// Dialogs
const showImportDialog = ref(false)
const showAddShardDialog = ref(false)
const showAddNodeDialog = ref(false)
const showMigrateDialog = ref(false)
const showFailoverDialog = ref(false)
const showRemoveShardDialog = ref(false)
const showCreateDialog = ref(false)

const selectedShard = ref(null)
const selectedNode = ref(null)

// Forms
const importForm = reactive({
  nodes: '',
  password: ''
})

const addShardForm = reactive({
  nodes: '',
  password: ''
})

const addNodeForm = reactive({
  addr: '',
  role: 'slave',
  password: ''
})

const migrateForm = reactive({
  target_shard: null,
  slot_start: 0,
  slot_stop: 100,
  slot_only: false
})

const removeShardForm = reactive({
  target_shard_index: null
})

const createForm = reactive({
  nodes: '',
  replicas: 0,
  password: ''
})

// Computed
const targetShards = computed(() => {
  if (!topology.value?.shards || !selectedShard.value) return []
  return topology.value.shards.filter(s => s.index !== selectedShard.value.index)
})

// Methods
function getSlotsCount(shard) {
  if (!shard?.slot_ranges) return 0
  return shard.slot_ranges.reduce((sum, sr) => sum + (sr.stop - sr.start + 1), 0)
}

function formatSlotRanges(ranges) {
  if (!ranges || ranges.length === 0) return ''
  return ranges.map(r => r.start === r.stop ? `${r.start}` : `${r.start}-${r.stop}`).join(', ')
}

function getSuggestionType(severity) {
  const types = { info: 'info', warning: 'warning', critical: 'error' }
  return types[severity] || 'info'
}

function getProgressColor(slots) {
  const percent = (slots / 16384) * 100
  if (percent < 10) return '#eab244'
  if (percent > 30) return '#ef6b6b'
  return '#3dd68c'
}

async function fetchTopology() {
  loading.value = true
  errorState.value = null
  try {
    topology.value = await scalingApi.getTopology(clusterId)
    clusterName.value = topology.value.cluster_name
    console.log('Topology loaded:', topology.value)
  } catch (error) {
    console.error('Failed to fetch topology:', error)
    const detail = error?.response?.data?.detail || error?.message || '获取拓扑失败'

    // Check if it's a "cluster not found" or controller error
    if (detail.includes('500') || detail.includes('not found') || detail.includes('Controller error')) {
      errorState.value = {
        title: '集群尚未在 Controller 中创建',
        message: '该集群在 kvrocks-controller 中不存在。您可以导入现有集群或创建新集群。'
      }
    } else if (detail.includes('503') || detail.includes('unavailable')) {
      errorState.value = {
        title: 'Controller 连接失败',
        message: '无法连接到 kvrocks-controller，请检查 Controller 是否在线。'
      }
    } else {
      errorState.value = {
        title: '获取集群拓扑失败',
        message: detail
      }
    }
  } finally {
    loading.value = false
  }
}

async function fetchSuggestions() {
  // Don't fetch suggestions if there's already an error
  if (errorState.value) return

  try {
    const result = await scalingApi.getSuggestions(clusterId)
    suggestions.value = result.suggestions.filter(s => s.type !== 'none')
  } catch (error) {
    // Silently ignore - suggestions are optional
    console.error('Failed to fetch suggestions:', error)
  }
}

async function syncTopology() {
  syncing.value = true
  try {
    const result = await scalingApi.syncTopology(clusterId)
    console.log('Sync result:', result)
    ElMessage.success(result?.message || '拓扑已同步')
    await fetchTopology()
  } catch (error) {
    console.error('Failed to sync topology:', error)
    const msg = error?.response?.data?.detail || error?.message || '同步拓扑失败'
    ElMessage.error(msg)
  } finally {
    syncing.value = false
  }
}

// Handlers
function handleAddNode(shard) {
  selectedShard.value = shard
  addNodeForm.addr = ''
  addNodeForm.role = 'slave'
  addNodeForm.password = ''
  showAddNodeDialog.value = true
}

function handleMigrateSlots(shard) {
  selectedShard.value = shard
  const firstRange = shard.slot_ranges?.[0]
  migrateForm.target_shard = null
  migrateForm.slot_start = firstRange?.start || 0
  migrateForm.slot_stop = firstRange?.stop || 100
  migrateForm.slot_only = false
  showMigrateDialog.value = true
}

function handleFailover(shard, node) {
  selectedShard.value = shard
  selectedNode.value = node
  showFailoverDialog.value = true
}

function handleRemoveShard(shard) {
  selectedShard.value = shard
  removeShardForm.target_shard_index = null
  showRemoveShardDialog.value = true
}

async function handleRemoveNode(shard, node) {
  try {
    await ElMessageBox.confirm(
      `确定要从分片 ${shard.index} 移除节点 ${node.addr} 吗？`,
      '移除节点',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )

    submitting.value = true
    await scalingApi.removeNode(clusterId, {
      shard_index: shard.index,
      node_id: node.id
    })
    ElMessage.success('节点已移除')
    await fetchTopology()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Failed to remove node:', error)
      ElMessage.error('移除节点失败')
    }
  } finally {
    submitting.value = false
  }
}

// Submissions
async function submitImport() {
  const nodes = importForm.nodes.trim().split('\n').filter(n => n.trim())
  if (nodes.length === 0) {
    ElMessage.warning('请输入至少一个节点地址')
    return
  }

  submitting.value = true
  try {
    await scalingApi.importCluster(clusterId, {
      nodes: nodes,
      password: importForm.password || null
    })
    ElMessage.success('集群导入成功')
    showImportDialog.value = false
    importForm.nodes = ''
    importForm.password = ''
    errorState.value = null
    await fetchTopology()
  } catch (error) {
    console.error('Failed to import cluster:', error)
    const msg = error?.response?.data?.detail || '导入集群失败'
    ElMessage.error(msg)
  } finally {
    submitting.value = false
  }
}

async function submitAddShard() {
  const nodes = addShardForm.nodes.trim().split('\n').filter(n => n.trim())
  if (nodes.length === 0) {
    ElMessage.warning('请输入至少一个节点地址')
    return
  }

  submitting.value = true
  try {
    await scalingApi.addShard(clusterId, {
      nodes: nodes,
      password: addShardForm.password || null
    })
    ElMessage.success('分片添加成功')
    showAddShardDialog.value = false
    addShardForm.nodes = ''
    addShardForm.password = ''
    await fetchTopology()
  } catch (error) {
    console.error('Failed to add shard:', error)
    ElMessage.error('添加分片失败')
  } finally {
    submitting.value = false
  }
}

async function submitAddNode() {
  if (!addNodeForm.addr) {
    ElMessage.warning('请输入节点地址')
    return
  }

  submitting.value = true
  try {
    await scalingApi.addNode(clusterId, {
      shard_index: selectedShard.value.index,
      addr: addNodeForm.addr,
      role: addNodeForm.role,
      password: addNodeForm.password || null
    })
    ElMessage.success('节点添加成功')
    showAddNodeDialog.value = false
    await fetchTopology()
  } catch (error) {
    console.error('Failed to add node:', error)
    ElMessage.error('添加节点失败')
  } finally {
    submitting.value = false
  }
}

async function submitMigrate() {
  if (migrateForm.target_shard === null) {
    ElMessage.warning('请选择目标分片')
    return
  }

  submitting.value = true
  try {
    await scalingApi.migrateSlots(clusterId, {
      target_shard: migrateForm.target_shard,
      slot_start: migrateForm.slot_start,
      slot_stop: migrateForm.slot_stop,
      slot_only: migrateForm.slot_only
    })
    ElMessage.success('槽位迁移成功')
    showMigrateDialog.value = false
    await fetchTopology()
  } catch (error) {
    console.error('Failed to migrate slots:', error)
    ElMessage.error('槽位迁移失败')
  } finally {
    submitting.value = false
  }
}

async function submitFailover() {
  submitting.value = true
  try {
    await scalingApi.failover(clusterId, {
      shard_index: selectedShard.value.index,
      preferred_node_id: selectedNode.value.id
    })
    ElMessage.success('主从切换成功')
    showFailoverDialog.value = false
    await fetchTopology()
  } catch (error) {
    console.error('Failed to failover:', error)
    ElMessage.error('主从切换失败')
  } finally {
    submitting.value = false
  }
}

async function submitRemoveShard() {
  submitting.value = true
  try {
    await scalingApi.removeShard(clusterId, {
      shard_index: selectedShard.value.index,
      target_shard_index: removeShardForm.target_shard_index
    })
    ElMessage.success('分片删除成功')
    showRemoveShardDialog.value = false
    await fetchTopology()
  } catch (error) {
    console.error('Failed to remove shard:', error)
    ElMessage.error('删除分片失败')
  } finally {
    submitting.value = false
  }
}

async function submitCreate() {
  const nodes = createForm.nodes.trim().split('\n').filter(n => n.trim())
  if (nodes.length < 3) {
    ElMessage.warning('请输入至少3个节点地址')
    return
  }

  submitting.value = true
  try {
    await scalingApi.createCluster(clusterId, {
      nodes: nodes,
      replicas: createForm.replicas,
      password: createForm.password || null
    })
    ElMessage.success('集群创建成功')
    showCreateDialog.value = false
    createForm.nodes = ''
    createForm.replicas = 0
    createForm.password = ''
    errorState.value = null
    await fetchTopology()
  } catch (error) {
    console.error('Failed to create cluster:', error)
    const msg = error?.response?.data?.detail || '创建集群失败'
    ElMessage.error(msg)
  } finally {
    submitting.value = false
  }
}

// Auto refresh functions
function toggleAutoRefresh(enabled) {
  if (enabled) {
    startAutoRefresh()
  } else {
    stopAutoRefresh()
  }
}

function updateRefreshInterval() {
  if (autoRefresh.value) {
    stopAutoRefresh()
    startAutoRefresh()
  }
}

function startAutoRefresh() {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
  refreshInterval = setInterval(() => {
    fetchTopology()
  }, refreshSeconds.value * 1000)
}

function stopAutoRefresh() {
  if (refreshInterval) {
    clearInterval(refreshInterval)
    refreshInterval = null
  }
}

// Lifecycle
let refreshInterval = null

onMounted(async () => {
  await fetchTopology()
  // Only fetch suggestions if topology loaded successfully
  if (!errorState.value) {
    fetchSuggestions()
  }

  // Auto refresh if enabled
  if (autoRefresh.value) {
    startAutoRefresh()
  }
})

onUnmounted(() => {
  stopAutoRefresh()
})
</script>

<style scoped>
.header-card {
  margin-bottom: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 15px;
}

.header-left h2 {
  margin: 0;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.auto-refresh {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 15px;
  border-right: 1px solid var(--kv-border-subtle);
  margin-right: 5px;
}

.auto-refresh-label {
  font-size: 14px;
  color: var(--kv-text-secondary);
}

/* 自动刷新开关蓝色主题 */
.auto-refresh :deep(.el-switch__core) {
  border-color: #5b9cf5;
}

.auto-refresh :deep(.el-switch:not(.is-checked) .el-switch__core) {
  background-color: #e0edff;
  border-color: #93c5fd;
}

.stats-row {
  margin-bottom: 20px;
}

.stat-card {
  text-align: center;
  padding: 10px 0;
}

.stat-value {
  font-family: var(--kv-font-mono);
  font-size: 28px;
  font-weight: bold;
  color: var(--kv-accent);
}

.stat-label {
  font-size: 14px;
  color: var(--kv-text-tertiary);
  margin-top: 5px;
}

.suggestions-card {
  margin-bottom: 20px;
}

.suggestion-item {
  margin-bottom: 10px;
}

.suggestion-item:last-child {
  margin-bottom: 0;
}

.shards-card {
  margin-bottom: 20px;
}

.empty-state {
  padding: 40px 0;
}

.shard-header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.shard-title {
  font-weight: 500;
}

.slot-bar {
  margin-top: 10px;
}

.slot-bar-label {
  display: flex;
  justify-content: space-between;
  margin-bottom: 5px;
  font-size: 14px;
}

.slot-ranges {
  color: var(--kv-text-secondary);
  font-family: var(--kv-font-mono);
}

.node-id {
  font-family: var(--kv-font-mono);
  font-size: 12px;
  color: var(--kv-text-tertiary);
}

.shard-actions {
  margin-top: 15px;
  display: flex;
  gap: 10px;
}

.text-center {
  text-align: center;
  line-height: 32px;
}

.form-tip {
  font-size: 12px;
  color: var(--kv-text-tertiary);
  margin-top: 5px;
}

.error-card {
  margin-bottom: 20px;
}

.error-card :deep(.el-result__title) {
  margin-top: 15px;
}

.error-card :deep(.el-result__extra) {
  margin-top: 20px;
}
</style>
