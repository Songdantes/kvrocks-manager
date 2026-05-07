<template>
  <div class="scaling-tasks">
    <!-- Header -->
    <el-card class="header-card">
      <div class="header">
        <div class="header-left">
          <h2>扩缩容历史</h2>
          <span class="subtitle">操作通过 kvrocks-controller 同步执行</span>
        </div>
        <div class="header-right">
          <el-select v-model="filters.status" placeholder="状态筛选" clearable style="width: 150px">
            <el-option label="已完成" value="completed" />
            <el-option label="失败" value="failed" />
          </el-select>
          <el-select v-model="filters.task_type" placeholder="类型筛选" clearable style="width: 150px">
            <el-option label="主从切换" value="failover" />
            <el-option label="添加分片" value="add_shard" />
            <el-option label="删除分片" value="remove_shard" />
            <el-option label="槽位迁移" value="slot_migration" />
          </el-select>
          <el-button @click="fetchTasks">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
          <el-button type="primary" @click="$router.push(`/clusters/${clusterId}/scaling/topology`)">
            <el-icon><Back /></el-icon> 返回拓扑
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- Task List -->
    <el-card v-loading="loading">
      <el-table :data="tasks" style="width: 100%">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="task_type" label="类型" width="120">
          <template #default="{ row }">
            <el-tag :type="getTaskTypeColor(row.task_type)" size="small">
              {{ getTaskTypeText(row.task_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusColor(row.status)" size="small">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作参数">
          <template #default="{ row }">
            <span v-if="row.task_type === 'failover'">
              分片 {{ row.params?.shard_index }}
            </span>
            <span v-else-if="row.task_type === 'add_shard'">
              节点: {{ row.params?.nodes?.join(', ') || '-' }}
            </span>
            <span v-else-if="row.task_type === 'remove_shard'">
              分片 {{ row.params?.shard_index }}
            </span>
            <span v-else-if="row.task_type === 'slot_migration'">
              槽位 {{ row.params?.slot_start }}-{{ row.params?.slot_stop }} → 分片 {{ row.params?.target_shard }}
            </span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="error_message" label="错误信息" width="200">
          <template #default="{ row }">
            <span v-if="row.error_message" class="error-text">{{ row.error_message }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="执行时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button type="primary" link @click="showTaskDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- Pagination -->
      <div class="pagination">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.page_size"
          :total="pagination.total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchTasks"
          @current-change="fetchTasks"
        />
      </div>
    </el-card>

    <!-- Task Detail Dialog -->
    <el-dialog v-model="showDetailDialog" title="操作详情" width="700px">
      <template v-if="currentTask">
        <!-- Basic Info -->
        <el-descriptions :column="2" border>
          <el-descriptions-item label="任务ID">{{ currentTask.id }}</el-descriptions-item>
          <el-descriptions-item label="类型">
            <el-tag :type="getTaskTypeColor(currentTask.task_type)" size="small">
              {{ getTaskTypeText(currentTask.task_type) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusColor(currentTask.status)" size="small">
              {{ getStatusText(currentTask.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="执行人">{{ currentTask.created_by || '-' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatTime(currentTask.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="完成时间">{{ formatTime(currentTask.completed_at) || '-' }}</el-descriptions-item>
        </el-descriptions>

        <!-- Parameters -->
        <div class="section" v-if="currentTask.params && Object.keys(currentTask.params).length > 0">
          <h4>操作参数</h4>
          <el-descriptions :column="1" border>
            <el-descriptions-item
              v-for="(value, key) in currentTask.params"
              :key="key"
              :label="getParamLabel(key)"
            >
              <template v-if="Array.isArray(value)">
                {{ value.join(', ') }}
              </template>
              <template v-else>
                {{ value }}
              </template>
            </el-descriptions-item>
          </el-descriptions>
        </div>

        <!-- Error Info -->
        <div class="section error-section" v-if="currentTask.error_message">
          <h4>错误信息</h4>
          <el-alert type="error" :closable="false">
            <template #title>{{ currentTask.error_message }}</template>
            <template v-if="currentTask.error_detail">
              <pre class="error-detail">{{ currentTask.error_detail }}</pre>
            </template>
          </el-alert>
        </div>

        <!-- Logs -->
        <div class="section" v-if="currentTask.logs && currentTask.logs.length > 0">
          <h4>执行日志</h4>
          <div class="log-list">
            <div
              v-for="log in currentTask.logs"
              :key="log.id"
              :class="['log-item', `log-${log.level}`]"
            >
              <span class="log-time">{{ formatTime(log.created_at) }}</span>
              <span class="log-level">[{{ log.level.toUpperCase() }}]</span>
              <span class="log-message">{{ log.message }}</span>
            </div>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { scalingApi } from '@/api/scaling'
import dayjs from 'dayjs'

const route = useRoute()
const clusterId = route.params.id

const loading = ref(false)
const tasks = ref([])
const currentTask = ref(null)
const showDetailDialog = ref(false)

const filters = reactive({
  status: '',
  task_type: ''
})

const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0
})

// Text/Color helpers
function getTaskTypeText(type) {
  const texts = {
    failover: '主从切换',
    add_shard: '添加分片',
    remove_shard: '删除分片',
    slot_migration: '槽位迁移',
    rebalance: '重平衡'
  }
  return texts[type] || type
}

function getTaskTypeColor(type) {
  const colors = {
    failover: 'warning',
    add_shard: 'success',
    remove_shard: 'danger',
    slot_migration: 'primary',
    rebalance: 'info'
  }
  return colors[type] || ''
}

function getStatusText(status) {
  const texts = {
    pending: '等待中',
    running: '执行中',
    paused: '已暂停',
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消',
    rolling_back: '回滚中'
  }
  return texts[status] || status
}

function getStatusColor(status) {
  const colors = {
    pending: 'info',
    running: 'primary',
    paused: 'warning',
    completed: 'success',
    failed: 'danger',
    cancelled: 'info',
    rolling_back: 'warning'
  }
  return colors[status] || ''
}

function getParamLabel(key) {
  const labels = {
    shard_index: '分片索引',
    target_shard: '目标分片',
    slot_start: '起始槽位',
    slot_stop: '结束槽位',
    nodes: '节点列表',
    preferred_node_id: '首选节点',
    target_shard_index: '目标分片索引'
  }
  return labels[key] || key
}

function formatTime(time) {
  if (!time) return null
  return dayjs(time).format('YYYY-MM-DD HH:mm:ss')
}

// API calls
async function fetchTasks() {
  loading.value = true
  try {
    const result = await scalingApi.listTasks(clusterId, {
      page: pagination.page,
      page_size: pagination.page_size,
      status: filters.status || undefined,
      task_type: filters.task_type || undefined
    })
    tasks.value = result.tasks
    pagination.total = result.total
  } catch (error) {
    console.error('Failed to fetch tasks:', error)
    ElMessage.error('获取任务列表失败')
  } finally {
    loading.value = false
  }
}

async function showTaskDetail(task) {
  try {
    currentTask.value = await scalingApi.getTask(clusterId, task.id)
    showDetailDialog.value = true
  } catch (error) {
    console.error('Failed to fetch task detail:', error)
    ElMessage.error('获取任务详情失败')
  }
}

// Watch filters
watch(filters, () => {
  pagination.page = 1
  fetchTasks()
})

onMounted(() => {
  fetchTasks()
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

.header-left h2 {
  margin: 0;
}

.header-left .subtitle {
  font-size: 12px;
  color: var(--kv-text-tertiary);
  margin-left: 10px;
}

.header-right {
  display: flex;
  gap: 10px;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.error-text {
  color: var(--kv-danger);
}

.text-muted {
  color: var(--kv-text-tertiary);
}

.section {
  margin-top: 20px;
}

.section h4 {
  margin: 0 0 10px 0;
  color: var(--kv-text-primary);
}

.error-section .el-alert {
  margin-top: 10px;
}

.error-detail {
  margin-top: 10px;
  padding: 10px;
  background: var(--kv-danger-muted);
  border-radius: var(--kv-radius-sm);
  font-family: var(--kv-font-mono);
  font-size: 12px;
  color: var(--kv-danger);
  white-space: pre-wrap;
  word-break: break-all;
}

.log-list {
  max-height: 300px;
  overflow-y: auto;
  background: var(--kv-bg-overlay);
  border-radius: var(--kv-radius-sm);
  padding: 10px;
}

.log-item {
  font-size: 12px;
  line-height: 1.8;
  font-family: var(--kv-font-mono);
}

.log-time {
  color: var(--kv-text-tertiary);
  margin-right: 10px;
}

.log-level {
  margin-right: 10px;
  font-weight: bold;
}

.log-info .log-level {
  color: var(--kv-info);
}

.log-warning .log-level {
  color: var(--kv-warning);
}

.log-error .log-level {
  color: var(--kv-danger);
}

.log-message {
  color: var(--kv-text-primary);
}
</style>
