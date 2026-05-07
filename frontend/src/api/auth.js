import request from '@/utils/request'

// Auth API
export const authApi = {
  login: (data) => request.post('/auth/login', data),
  logout: () => request.post('/auth/logout'),
  refresh: () => request.post('/auth/refresh'),
  me: () => request.get('/auth/me')
}

// User API
export const userApi = {
  list: (params) => request.get('/users', { params }),
  get: (id) => request.get(`/users/${id}`),
  create: (data) => request.post('/users', data),
  update: (id, data) => request.put(`/users/${id}`, data),
  delete: (id) => request.delete(`/users/${id}`),
  changePassword: (id, data) => request.put(`/users/${id}/password`, data)
}

// Role API
export const roleApi = {
  list: () => request.get('/roles'),
  get: (id) => request.get(`/roles/${id}`),
  create: (data) => request.post('/roles', data),
  update: (id, data) => request.put(`/roles/${id}`, data),
  delete: (id) => request.delete(`/roles/${id}`)
}

// Permission API
export const permissionApi = {
  list: (module) => request.get('/permissions', { params: { module } })
}

export default { authApi, userApi, roleApi, permissionApi }
