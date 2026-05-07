<template>
  <el-container class="layout-container">
    <!-- Sidebar -->
    <el-aside :width="isCollapse ? '72px' : '232px'" class="sidebar">
      <div class="logo">
        <span class="logo-mark">KV</span>
        <transition name="fade">
          <span v-if="!isCollapse" class="logo-text">rocks Manager</span>
        </transition>
      </div>

      <div class="sidebar-divider"></div>

      <el-menu
        :default-active="currentRoute"
        :collapse="isCollapse"
        :router="true"
      >
        <el-menu-item index="/dashboard">
          <el-icon><Odometer /></el-icon>
          <span>仪表盘</span>
        </el-menu-item>

        <el-sub-menu index="cluster">
          <template #title>
            <el-icon><Grid /></el-icon>
            <span>集群管理</span>
          </template>
          <el-menu-item index="/controllers">Controller</el-menu-item>
          <el-menu-item index="/clusters">集群列表</el-menu-item>
          <el-menu-item index="/nodes">节点管理</el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="system" v-if="hasPermission('user:read')">
          <template #title>
            <el-icon><Setting /></el-icon>
            <span>系统管理</span>
          </template>
          <el-menu-item index="/users" v-if="hasPermission('user:read')">用户管理</el-menu-item>
          <el-menu-item index="/roles" v-if="hasPermission('role:read')">角色管理</el-menu-item>
        </el-sub-menu>
      </el-menu>

      <div class="sidebar-footer">
        <div class="sidebar-actions" v-if="!isCollapse">
          <el-dropdown @command="handleCommand" placement="top-start">
            <span class="user-dropdown">
              <el-avatar :size="28" icon="User" />
              <span class="username">{{ username }}</span>
              <el-icon class="arrow-icon"><ArrowUp /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">个人信息</el-dropdown-item>
                <el-dropdown-item command="password">修改密码</el-dropdown-item>
                <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
        <div class="sidebar-actions-collapsed" v-else>
          <el-dropdown @command="handleCommand" placement="right-end">
            <el-avatar :size="28" icon="User" style="cursor: pointer" />
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">个人信息</el-dropdown-item>
                <el-dropdown-item command="password">修改密码</el-dropdown-item>
                <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>
    </el-aside>

    <!-- Main content -->
    <el-container>
      <!-- Header -->
      <el-header class="header">
        <div class="header-left">
          <el-icon class="collapse-btn" @click="toggleCollapse">
            <Fold v-if="!isCollapse" />
            <Expand v-else />
          </el-icon>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/dashboard' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-if="currentTitle">{{ currentTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
      </el-header>

      <!-- Main -->

      <!-- Profile Dialog -->
      <el-dialog v-model="showProfileDialog" title="个人信息" width="480px">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="用户名">
            <span class="font-mono">{{ userStore.user?.username }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="邮箱">
            {{ userStore.user?.email || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="手机号">
            {{ userStore.user?.phone || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="角色">
            <el-tag
              v-for="role in userStore.user?.roles"
              :key="role.id"
              size="small"
              style="margin-right: 6px"
            >
              {{ role.name }}
            </el-tag>
            <span v-if="!userStore.user?.roles?.length">-</span>
          </el-descriptions-item>
        </el-descriptions>
        <template #footer>
          <el-button @click="showProfileDialog = false">关闭</el-button>
        </template>
      </el-dialog>

      <!-- Change Password Dialog -->
      <el-dialog v-model="showPasswordDialog" title="修改密码" width="480px">
        <el-form
          ref="pwdFormRef"
          :model="pwdForm"
          :rules="pwdRules"
          label-width="100px"
        >
          <el-form-item label="旧密码" prop="old_password">
            <el-input v-model="pwdForm.old_password" type="password" placeholder="请输入旧密码" show-password />
          </el-form-item>
          <el-form-item label="新密码" prop="new_password">
            <el-input v-model="pwdForm.new_password" type="password" placeholder="请输入新密码" show-password />
          </el-form-item>
          <el-form-item label="确认密码" prop="confirm_password">
            <el-input v-model="pwdForm.confirm_password" type="password" placeholder="请再次输入新密码" show-password />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="showPasswordDialog = false">取消</el-button>
          <el-button type="primary" :loading="changingPwd" @click="handleChangePassword">确定</el-button>
        </template>
      </el-dialog>

      <el-main class="main">
        <router-view v-slot="{ Component }">
          <transition name="page" mode="out-in">
            <div class="kv-page">
              <component :is="Component" />
            </div>
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { userApi } from '@/api/auth'
import { ElMessage } from 'element-plus'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const isCollapse = ref(false)
const showProfileDialog = ref(false)
const showPasswordDialog = ref(false)
const changingPwd = ref(false)
const pwdFormRef = ref(null)

const pwdForm = reactive({
  old_password: '',
  new_password: '',
  confirm_password: ''
})

const pwdRules = {
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
        if (value !== pwdForm.new_password) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
}

const currentRoute = computed(() => route.path)
const currentTitle = computed(() => route.meta.title)
const username = computed(() => userStore.username)

function hasPermission(permission) {
  return userStore.hasPermission(permission)
}

function toggleCollapse() {
  isCollapse.value = !isCollapse.value
}

function handleCommand(command) {
  switch (command) {
    case 'profile':
      showProfileDialog.value = true
      break
    case 'password':
      pwdForm.old_password = ''
      pwdForm.new_password = ''
      pwdForm.confirm_password = ''
      showPasswordDialog.value = true
      break
    case 'logout':
      userStore.logout()
      router.push('/login')
      break
  }
}

async function handleChangePassword() {
  if (!pwdFormRef.value) return

  await pwdFormRef.value.validate(async (valid) => {
    if (!valid) return

    changingPwd.value = true
    try {
      await userApi.changePassword(userStore.user.id, {
        old_password: pwdForm.old_password,
        new_password: pwdForm.new_password
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
      changingPwd.value = false
    }
  })
}

</script>

<style scoped>
.layout-container {
  height: 100vh;
}

.sidebar {
  background: var(--kv-sidebar-bg);
  border-right: 1px solid rgba(248, 250, 252, 0.08);
  transition: width 0.3s var(--kv-ease);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  padding: 0 20px;
  gap: 0;
  white-space: nowrap;
  overflow: hidden;
}

.logo-mark {
  font-family: var(--kv-font-mono);
  font-size: 22px;
  font-weight: 700;
  color: var(--kv-accent);
  text-shadow: 0 0 22px rgba(91, 108, 255, 0.35);
  animation: accentBreath 4s ease-in-out infinite;
  flex-shrink: 0;
}

.logo-text {
  font-family: var(--kv-font-body);
  font-size: 14px;
  font-weight: 600;
  color: rgba(226, 232, 240, 0.84);
  margin-left: 1px;
  letter-spacing: -0.02em;
}

.sidebar-divider {
  height: 1px;
  margin: 4px 20px 8px;
  background: linear-gradient(90deg,
    transparent,
    var(--kv-border-default),
    transparent
  );
}

.sidebar-footer {
  margin-top: auto;
  padding: 12px 16px;
  border-top: 1px solid var(--kv-border-subtle);
}

.sidebar-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.sidebar-actions-collapsed {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.sidebar-icon {
  font-size: 18px;
  color: var(--kv-sidebar-text);
  cursor: pointer;
  transition: color var(--kv-dur-fast) var(--kv-ease);
}

.sidebar-icon:hover {
  color: var(--kv-sidebar-text-active);
}

.header {
  display: flex;
  align-items: center;
  background: rgba(255, 255, 255, 0.86);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--kv-border-subtle);
  padding: 0 24px;
  height: 56px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 20px;
}

.collapse-btn {
  font-size: 18px;
  color: var(--kv-text-tertiary);
  cursor: pointer;
  transition: color var(--kv-dur-fast) var(--kv-ease);
}

.collapse-btn:hover {
  color: var(--kv-text-primary);
}

.user-dropdown {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: var(--kv-radius-sm);
  transition: background var(--kv-dur-fast) var(--kv-ease);
}

.user-dropdown:hover {
  background: var(--kv-sidebar-hover);
}

.username {
  color: var(--kv-sidebar-text-hover);
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.arrow-icon {
  color: var(--kv-sidebar-text);
  font-size: 12px;
}

.main {
  background: var(--kv-bg-base);
  padding: 0;
  overflow-y: auto;
}

/* Fade transition for logo text */
.fade-enter-active {
  transition: opacity 0.3s var(--kv-ease);
}
.fade-leave-active {
  transition: opacity 0.15s var(--kv-ease);
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
