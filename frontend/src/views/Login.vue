<template>
  <div class="login-page">
    <!-- Grid background -->
    <div class="login-bg"></div>
    <!-- Amber spotlight -->
    <div class="login-spotlight"></div>

    <div class="login-layout">
      <!-- Left: Brand -->
      <div class="login-brand">
        <div class="brand-content">
          <h1 class="brand-title">
            <span class="brand-kv">KVrocks</span>
            <span class="brand-mgr">Manager</span>
          </h1>
          <p class="brand-desc">分布式 KV 存储集群管理平台</p>
          <div class="brand-features">
            <div class="brand-feature">
              <span class="feature-dot"></span>
              <span>集群编排与自动化运维</span>
            </div>
            <div class="brand-feature">
              <span class="feature-dot"></span>
              <span>实时监控与监控大盘</span>
            </div>
            <div class="brand-feature">
              <span class="feature-dot"></span>
              <span>弹性扩缩容与拓扑管理</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Right: Login Form -->
      <div class="login-form-area">
        <div class="login-card">
          <div class="login-card-header">
            <h2 class="login-title">登录</h2>
            <p class="login-subtitle">Sign in to your account</p>
          </div>

          <el-form
            ref="formRef"
            :model="form"
            :rules="rules"
            class="login-form"
            @keyup.enter="handleLogin"
          >
            <el-form-item prop="username">
              <el-input
                v-model="form.username"
                placeholder="用户名"
                prefix-icon="User"
                size="large"
              />
            </el-form-item>
            <el-form-item prop="password">
              <el-input
                v-model="form.password"
                type="password"
                placeholder="密码"
                prefix-icon="Lock"
                size="large"
                show-password
              />
            </el-form-item>
            <el-form-item>
              <el-button
                type="primary"
                size="large"
                :loading="loading"
                class="login-btn"
                @click="handleLogin"
              >
                登 录
              </el-button>
            </el-form-item>
          </el-form>
        </div>
      </div>
    </div>

    <!-- Version -->
    <div class="login-version">v1.0.0</div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

const formRef = ref(null)
const loading = ref(false)

const form = reactive({
  username: '',
  password: ''
})

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于6位', trigger: 'blur' }
  ]
}

async function handleLogin() {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    loading.value = true
    try {
      await userStore.login(form.username, form.password)
      ElMessage.success('登录成功')
      router.push('/dashboard')
    } catch (error) {
      console.error('Login failed:', error)
    } finally {
      loading.value = false
    }
  })
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  background: linear-gradient(135deg, #0b1020 0%, #5b6cff 55%, #35f0c7 120%);
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* Grid background */
.login-bg {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(248, 250, 252, 0.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(248, 250, 252, 0.06) 1px, transparent 1px);
  background-size: 60px 60px;
  z-index: 0;
}

/* Amber spotlight radial gradient */
.login-spotlight {
  position: absolute;
  top: 50%;
  right: 20%;
  width: 800px;
  height: 800px;
  transform: translate(50%, -50%);
  background: radial-gradient(
    ellipse at center,
    rgba(91, 108, 255, 0.22) 0%,
    rgba(53, 240, 199, 0.10) 32%,
    transparent 70%
  );
  z-index: 0;
  pointer-events: none;
}

/* Main layout — asymmetric split */
.login-layout {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 80px;
  max-width: 960px;
  width: 100%;
  padding: 40px;
  animation: scaleIn 600ms cubic-bezier(0.22, 1, 0.36, 1) both;
}

/* Left brand section */
.login-brand {
  flex: 1;
  min-width: 0;
}

.brand-content {
  max-width: 380px;
}

.brand-title {
  margin: 0 0 16px;
  line-height: 1.1;
}

.brand-kv {
  display: block;
  font-family: var(--kv-font-display);
  font-size: 48px;
  font-weight: 700;
  color: rgba(248, 250, 252, 0.96);
  text-shadow: 0 0 44px rgba(91, 108, 255, 0.35);
  animation: accentBreath 4s ease-in-out infinite;
}

.brand-mgr {
  display: block;
  font-family: var(--kv-font-display);
  font-size: 48px;
  font-weight: 700;
  color: rgba(248, 250, 252, 0.92);
}

.brand-desc {
  font-size: 16px;
  color: rgba(226, 232, 240, 0.80);
  margin: 0 0 32px;
  letter-spacing: 0.02em;
}

.brand-features {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.brand-feature {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  color: rgba(226, 232, 240, 0.78);
}

.feature-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--kv-accent-2);
  box-shadow: 0 0 10px rgba(53, 240, 199, 0.45);
  flex-shrink: 0;
}

/* Right form section */
.login-form-area {
  flex-shrink: 0;
  width: 380px;
}

.login-card {
  background: rgba(255, 255, 255, 0.86);
  border: 1px solid rgba(255, 255, 255, 0.35);
  border-radius: var(--kv-radius-lg);
  padding: 40px 32px;
  box-shadow: var(--kv-shadow-lg), var(--kv-shadow-glow);
  backdrop-filter: blur(8px);
}

.login-card-header {
  margin-bottom: 32px;
}

.login-title {
  font-size: 22px;
  font-weight: 600;
  color: var(--kv-text-primary);
  margin: 0 0 6px;
}

.login-subtitle {
  font-size: 13px;
  color: var(--kv-text-tertiary);
  margin: 0;
  font-family: var(--kv-font-mono);
  letter-spacing: 0.02em;
}

.login-form {
  margin-top: 0;
}

.login-form :deep(.el-form-item) {
  margin-bottom: 22px;
}

.login-btn {
  width: 100%;
  height: 44px;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.1em;
}

/* Version badge */
.login-version {
  position: absolute;
  bottom: 24px;
  right: 32px;
  font-family: var(--kv-font-mono);
  font-size: 11px;
  color: rgba(226, 232, 240, 0.74);
  z-index: 1;
}

/* Responsive: stack on narrow screens */
@media (max-width: 768px) {
  .login-layout {
    flex-direction: column;
    gap: 40px;
    padding: 40px 24px;
  }

  .login-brand {
    text-align: center;
  }

  .brand-content {
    max-width: 100%;
  }

  .brand-kv,
  .brand-mgr {
    font-size: 36px;
  }

  .brand-features {
    align-items: center;
  }

  .login-form-area {
    width: 100%;
    max-width: 380px;
  }
}
</style>
