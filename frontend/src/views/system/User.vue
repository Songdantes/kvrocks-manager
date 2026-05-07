<template>
  <div class="user-management">
    <div class="page-header">
      <div>
        <h2>用户管理</h2>
        <div class="page-subtitle">维护账号状态与角色绑定（需相应权限）</div>
      </div>
      <el-button type="primary" @click="showDialog = true">
        <el-icon><Plus /></el-icon>
        新建用户
      </el-button>
    </div>

    <el-card class="content-card">
      <el-table :data="users" v-loading="loading" style="width: 100%">
        <el-table-column prop="username" label="用户名" width="150" />
        <el-table-column prop="email" label="邮箱" width="200" />
        <el-table-column prop="phone" label="手机号" width="150" />
        <el-table-column label="角色" min-width="200">
          <template #default="{ row }">
            <el-tag v-for="role in row.roles" :key="role.id" size="small" class="role-tag">
              {{ role.name }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status ? 'success' : 'danger'" size="small">
              {{ row.status ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170">
          <template #default="{ row }">
            <span class="kv-num">{{ formatTime(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="240">
          <template #default="{ row }">
            <el-button type="primary" link @click="editUser(row)">编辑</el-button>
            <el-button type="warning" link @click="openChangePassword(row)">修改密码</el-button>
            <el-button :type="row.status ? 'warning' : 'success'" link @click="toggleStatus(row)">
              {{ row.status ? '禁用' : '启用' }}
            </el-button>
            <el-button type="danger" link @click="deleteUser(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- User Dialog -->
    <el-dialog v-model="showDialog" :title="editingUser ? '编辑用户' : '新建用户'" width="500px">
      <el-form
        ref="formRef"
        :model="userForm"
        :rules="formRules"
        label-width="100px"
      >
        <el-form-item label="用户名" prop="username">
          <el-input v-model="userForm.username" :disabled="!!editingUser" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item v-if="!editingUser" label="密码" prop="password">
          <el-input v-model="userForm.password" type="password" placeholder="请输入密码" show-password />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="userForm.email" placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item label="手机号">
          <el-input v-model="userForm.phone" placeholder="请输入手机号" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="userForm.role_ids" multiple placeholder="请选择角色">
            <el-option
              v-for="role in roles"
              :key="role.id"
              :label="role.name"
              :value="role.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveUser">保存</el-button>
      </template>
    </el-dialog>

    <!-- Change Password Dialog -->
    <el-dialog v-model="showPasswordDialog" title="修改密码" width="500px">
      <el-form
        ref="passwordFormRef"
        :model="passwordForm"
        :rules="passwordRules"
        label-width="100px"
      >
        <el-form-item label="用户">
          <el-input :model-value="passwordUser?.username" disabled />
        </el-form-item>
        <el-form-item label="旧密码" prop="old_password">
          <el-input v-model="passwordForm.old_password" type="password" placeholder="请输入旧密码" show-password />
        </el-form-item>
        <el-form-item label="新密码" prop="new_password">
          <el-input v-model="passwordForm.new_password" type="password" placeholder="请输入新密码" show-password />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirm_password">
          <el-input v-model="passwordForm.confirm_password" type="password" placeholder="请再次输入新密码" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showPasswordDialog = false">取消</el-button>
        <el-button type="primary" :loading="changingPassword" @click="handleChangePassword">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { userApi, roleApi } from '@/api/auth'
import dayjs from 'dayjs'

const loading = ref(false)
const saving = ref(false)
const changingPassword = ref(false)
const users = ref([])
const roles = ref([])
const showDialog = ref(false)
const showPasswordDialog = ref(false)
const editingUser = ref(null)
const passwordUser = ref(null)

const formRef = ref(null)
const passwordFormRef = ref(null)
const userForm = reactive({
  username: '',
  password: '',
  email: '',
  phone: '',
  role_ids: []
})

const formRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 50, message: '长度在 3 到 50 个字符', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 个字符', trigger: 'blur' }
  ],
  email: [
    { type: 'email', message: '请输入正确的邮箱地址', trigger: 'blur' }
  ]
}

const passwordForm = reactive({
  old_password: '',
  new_password: '',
  confirm_password: ''
})

const passwordRules = {
  old_password: [
    { required: true, message: '请输入旧密码', trigger: 'blur' }
  ],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 个字符', trigger: 'blur' }
  ],
  confirm_password: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== passwordForm.new_password) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
}

function formatTime(time) {
  return dayjs(time).format('YYYY-MM-DD HH:mm:ss')
}

async function fetchUsers() {
  loading.value = true
  try {
    users.value = await userApi.list()
  } catch (error) {
    console.error('Failed to fetch users:', error)
  } finally {
    loading.value = false
  }
}

async function fetchRoles() {
  try {
    roles.value = await roleApi.list()
  } catch (error) {
    console.error('Failed to fetch roles:', error)
  }
}

function editUser(user) {
  editingUser.value = user
  Object.assign(userForm, {
    username: user.username,
    password: '',
    email: user.email || '',
    phone: user.phone || '',
    role_ids: user.roles.map(r => r.id)
  })
  showDialog.value = true
}

async function saveUser() {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    saving.value = true
    try {
      if (editingUser.value) {
        await userApi.update(editingUser.value.id, {
          email: userForm.email || null,
          phone: userForm.phone || null,
          role_ids: userForm.role_ids
        })
        ElMessage.success('用户更新成功')
      } else {
        await userApi.create({
          username: userForm.username,
          password: userForm.password,
          email: userForm.email || null,
          phone: userForm.phone || null,
          role_ids: userForm.role_ids
        })
        ElMessage.success('用户创建成功')
      }
      showDialog.value = false
      resetForm()
      await fetchUsers()
    } catch (error) {
      console.error('Failed to save user:', error)
    } finally {
      saving.value = false
    }
  })
}

function resetForm() {
  editingUser.value = null
  userForm.username = ''
  userForm.password = ''
  userForm.email = ''
  userForm.phone = ''
  userForm.role_ids = []
}

async function toggleStatus(user) {
  try {
    await userApi.update(user.id, { status: !user.status })
    ElMessage.success(user.status ? '用户已禁用' : '用户已启用')
    await fetchUsers()
  } catch (error) {
    console.error('Failed to toggle status:', error)
  }
}

async function deleteUser(user) {
  try {
    await ElMessageBox.confirm(
      `确定要删除用户 "${user.username}" 吗？`,
      '删除确认',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await userApi.delete(user.id)
    ElMessage.success('删除成功')
    await fetchUsers()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Failed to delete user:', error)
    }
  }
}

function openChangePassword(user) {
  passwordUser.value = user
  passwordForm.old_password = ''
  passwordForm.new_password = ''
  passwordForm.confirm_password = ''
  showPasswordDialog.value = true
}

async function handleChangePassword() {
  if (!passwordFormRef.value) return

  await passwordFormRef.value.validate(async (valid) => {
    if (!valid) return

    changingPassword.value = true
    try {
      await userApi.changePassword(passwordUser.value.id, {
        old_password: passwordForm.old_password,
        new_password: passwordForm.new_password
      })
      ElMessage.success('密码修改成功')
      showPasswordDialog.value = false
    } catch (error) {
      if (error.response?.status === 400) {
        ElMessage.error('旧密码不正确')
      } else {
        console.error('Failed to change password:', error)
      }
    } finally {
      changingPassword.value = false
    }
  })
}

onMounted(() => {
  fetchUsers()
  fetchRoles()
})
</script>

<style scoped>
.role-tag {
  margin-right: 6px;
  margin-bottom: 6px;
}
</style>
