import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/',
    component: () => import('@/components/Layout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        redirect: '/dashboard'
      },
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { title: '仪表盘' }
      },
      {
        path: 'clusters',
        name: 'ClusterList',
        component: () => import('@/views/cluster/ClusterList.vue'),
        meta: { title: '集群管理' }
      },
      {
        path: 'clusters/:id',
        name: 'ClusterDetail',
        component: () => import('@/views/cluster/ClusterDetail.vue'),
        meta: { title: '集群详情' }
      },
      {
        path: 'clusters/:id/scaling/topology',
        name: 'ClusterTopology',
        component: () => import('@/views/cluster/ClusterTopology.vue'),
        meta: { title: '集群拓扑', permission: 'scaling:read' }
      },
      {
        path: 'clusters/:id/scaling/tasks',
        name: 'ScalingTasks',
        component: () => import('@/views/cluster/ScalingTasks.vue'),
        meta: { title: '扩缩容任务', permission: 'scaling:read' }
      },
      {
        path: 'nodes',
        name: 'NodeList',
        component: () => import('@/views/cluster/NodeList.vue'),
        meta: { title: '节点管理' }
      },
      {
        path: 'users',
        name: 'Users',
        component: () => import('@/views/system/User.vue'),
        meta: { title: '用户管理', permission: 'user:read' }
      },
      {
        path: 'roles',
        name: 'Roles',
        component: () => import('@/views/system/Role.vue'),
        meta: { title: '角色管理', permission: 'role:read' }
      },
      {
        path: 'controllers',
        name: 'Controllers',
        component: () => import('@/views/controllers/ControllerList.vue'),
        meta: { title: 'Controller 管理' }
      }
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/dashboard'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Navigation guard
router.beforeEach(async (to, from, next) => {
  const userStore = useUserStore()

  // Check if route requires authentication
  if (to.meta.requiresAuth !== false) {
    if (!userStore.isLoggedIn) {
      // Try to restore from localStorage
      const token = localStorage.getItem('token')
      if (token) {
        try {
          await userStore.fetchCurrentUser()
        } catch (error) {
          localStorage.removeItem('token')
          return next('/login')
        }
      } else {
        return next('/login')
      }
    }

    // Check permission
    if (to.meta.permission && !userStore.hasPermission(to.meta.permission)) {
      return next('/dashboard')
    }
  }

  next()
})

export default router
