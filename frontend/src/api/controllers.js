import request from '@/utils/request'

export const controllersApi = {
  // List all controllers
  list(params) {
    return request.get('/controllers', { params })
  },

  // Create a new controller
  create(data) {
    return request.post('/controllers', data)
  },

  // Get controller details
  get(id) {
    return request.get(`/controllers/${id}`)
  },

  // Update controller
  update(id, data) {
    return request.put(`/controllers/${id}`, data)
  },

  // Delete controller
  delete(id) {
    return request.delete(`/controllers/${id}`)
  },

  // Check controller health
  check(id) {
    return request.post(`/controllers/${id}/check`)
  },

  // Discover namespaces and clusters
  discover(id) {
    return request.get(`/controllers/${id}/discover`)
  },

  // Import clusters from controller
  import(id, data) {
    return request.post(`/controllers/${id}/import`, data)
  }
}
