import request from '@/utils/request'

// Cluster API
export const clusterApi = {
  list: (params) => request.get('/clusters', { params }),
  get: (id) => request.get(`/clusters/${id}`),
  create: (data) => request.post('/clusters', data),
  update: (id, data) => request.put(`/clusters/${id}`, data),
  delete: (id) => request.delete(`/clusters/${id}`),
  refreshStatus: (id) => request.post(`/clusters/${id}/refresh-status`)
}

// Node API
export const nodeApi = {
  list: (params) => request.get('/nodes', { params }),
  get: (id) => request.get(`/nodes/${id}`),
  create: (data) => request.post('/nodes', data),
  delete: (id) => request.delete(`/nodes/${id}`),
  ping: (id) => request.post(`/nodes/${id}/ping`),
  info: (id, section) => request.get(`/nodes/${id}/info`, { params: { section } }),
  getConfig: (id, pattern) => request.get(`/nodes/${id}/config`, { params: { pattern } }),
  setConfig: (id, configs) => request.put(`/nodes/${id}/config`, { configs }),
  executeCommand: (id, command, args) => request.post(`/nodes/${id}/command`, { command, args })
}

export default { clusterApi, nodeApi }
