<template>
  <div class="role-management">
    <div class="page-header">
      <div>
        <h2>角色管理</h2>
        <div class="page-subtitle">配置角色与权限点集合（内置角色仅查看）</div>
      </div>
      <el-button type="primary" @click="showDialog = true">
        <el-icon><Plus /></el-icon>
        新建角色
      </el-button>
    </div>

    <el-card class="content-card">
      <el-table :data="roles" v-loading="loading" style="width: 100%">
        <el-table-column prop="name" label="角色名称" width="150" />
        <el-table-column prop="description" label="描述" min-width="200" />
        <el-table-column prop="is_builtin" label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_builtin ? 'warning' : 'info'" size="small">
              {{ row.is_builtin ? '内置' : '自定义' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="权限数量" width="100">
          <template #default="{ row }">
            {{ row.permissions?.length || 0 }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170">
          <template #default="{ row }">
            <span class="kv-num">{{ formatTime(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button type="primary" link @click="editRole(row)">
              编辑
            </el-button>
            <el-button type="danger" link @click="deleteRole(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Role Dialog -->
    <el-dialog v-model="showDialog" :title="editingRole ? '编辑角色' : '新建角色'" width="600px">
      <el-form
        ref="formRef"
        :model="roleForm"
        :rules="formRules"
        label-width="100px"
      >
        <el-form-item label="角色名称" prop="name">
          <el-input v-model="roleForm.name" placeholder="请输入角色名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="roleForm.description" type="textarea" :rows="2" placeholder="请输入描述" />
        </el-form-item>
        <el-form-item label="权限">
          <div class="permission-groups">
            <div v-for="(perms, module) in groupedPermissions" :key="module" class="permission-group">
              <div class="module-title">{{ moduleNames[module] || module }}</div>
              <el-checkbox-group v-model="roleForm.permission_ids">
                <el-checkbox
                  v-for="perm in perms"
                  :key="perm.id"
                  :value="perm.id"
                >
                  {{ perm.name }}
                </el-checkbox>
              </el-checkbox-group>
            </div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveRole">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { roleApi, permissionApi } from '@/api/auth'
import dayjs from 'dayjs'

const loading = ref(false)
const saving = ref(false)
const roles = ref([])
const permissions = ref([])
const showDialog = ref(false)
const editingRole = ref(null)

const formRef = ref(null)
const roleForm = reactive({
  name: '',
  description: '',
  permission_ids: []
})

const formRules = {
  name: [
    { required: true, message: '请输入角色名称', trigger: 'blur' },
    { min: 2, max: 50, message: '长度在 2 到 50 个字符', trigger: 'blur' }
  ]
}

const moduleNames = {
  user: '用户管理',
  role: '角色管理',
  cluster: '集群管理',
  node: '节点管理',
  config: '配置管理',
  command: '命令执行',
  backup: '备份管理'
}

const groupedPermissions = computed(() => {
  const groups = {}
  for (const perm of permissions.value) {
    if (!groups[perm.module]) {
      groups[perm.module] = []
    }
    groups[perm.module].push(perm)
  }
  return groups
})

function formatTime(time) {
  return dayjs(time).format('YYYY-MM-DD HH:mm:ss')
}

async function fetchRoles() {
  loading.value = true
  try {
    roles.value = await roleApi.list()
  } catch (error) {
    console.error('Failed to fetch roles:', error)
  } finally {
    loading.value = false
  }
}

async function fetchPermissions() {
  try {
    permissions.value = await permissionApi.list()
  } catch (error) {
    console.error('Failed to fetch permissions:', error)
  }
}

function editRole(role) {
  editingRole.value = role
  Object.assign(roleForm, {
    name: role.name,
    description: role.description || '',
    permission_ids: role.permissions?.map(p => p.id) || []
  })
  showDialog.value = true
}

async function saveRole() {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    saving.value = true
    try {
      if (editingRole.value) {
        await roleApi.update(editingRole.value.id, roleForm)
        ElMessage.success('角色更新成功')
      } else {
        await roleApi.create(roleForm)
        ElMessage.success('角色创建成功')
      }
      showDialog.value = false
      resetForm()
      await fetchRoles()
    } catch (error) {
      console.error('Failed to save role:', error)
    } finally {
      saving.value = false
    }
  })
}

function resetForm() {
  editingRole.value = null
  roleForm.name = ''
  roleForm.description = ''
  roleForm.permission_ids = []
}

async function deleteRole(role) {
  try {
    await ElMessageBox.confirm(
      `确定要删除角色 "${role.name}" 吗？`,
      '删除确认',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await roleApi.delete(role.id)
    ElMessage.success('删除成功')
    await fetchRoles()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Failed to delete role:', error)
    }
  }
}

onMounted(() => {
  fetchRoles()
  fetchPermissions()
})
</script>

<style scoped>
.permission-groups {
  max-height: 400px;
  overflow-y: auto;
}

.permission-group {
  margin-bottom: 15px;
  padding: 10px;
  background: var(--kv-bg-overlay);
  border-radius: var(--kv-radius-sm);
  border: 1px solid var(--kv-border-subtle);
}

.module-title {
  font-weight: bold;
  margin-bottom: 10px;
  color: var(--kv-text-primary);
}

.el-checkbox {
  margin-right: 15px;
  margin-bottom: 5px;
}
</style>
