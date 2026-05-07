import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import request from '@/utils/request'

export const useUserStore = defineStore('user', () => {
  const user = ref(null)
  const token = ref(localStorage.getItem('token') || '')
  const permissions = ref([])

  const isLoggedIn = computed(() => !!token.value && !!user.value)
  const username = computed(() => user.value?.username || '')
  const roles = computed(() => user.value?.roles || [])

  function hasPermission(permission) {
    // Super admin has all permissions
    if (roles.value.some(r => r.name === 'super_admin')) {
      return true
    }
    return permissions.value.includes(permission)
  }

  async function login(username, password) {
    const response = await request.post('/auth/login', { username, password })
    token.value = response.access_token
    user.value = response.user
    permissions.value = response.user.permissions || []
    localStorage.setItem('token', response.access_token)
    return response
  }

  async function logout() {
    try {
      await request.post('/auth/logout')
    } catch (error) {
      // Ignore errors
    }
    token.value = ''
    user.value = null
    permissions.value = []
    localStorage.removeItem('token')
  }

  async function fetchCurrentUser() {
    const response = await request.get('/auth/me')
    user.value = response
    permissions.value = response.permissions || []
    return response
  }

  return {
    user,
    token,
    permissions,
    isLoggedIn,
    username,
    roles,
    hasPermission,
    login,
    logout,
    fetchCurrentUser
  }
})
