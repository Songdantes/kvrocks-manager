import request from '@/utils/request'

/**
 * Scaling API for kvrocks-controller integration
 *
 * Operations are delegated to kvrocks-controller via HTTP API.
 * Uses namespace/cluster/shard/node hierarchy.
 */
export const scalingApi = {
  // ==================== Topology ====================

  // Get cluster topology from controller (silent error - handled by component)
  getTopology: (clusterId) => request.get(`/clusters/${clusterId}/scaling/topology`, { silentError: true }),

  // Sync topology from controller to local database
  syncTopology: (clusterId) => request.post(`/clusters/${clusterId}/scaling/topology/sync`),

  // Import existing cluster into controller
  importCluster: (clusterId, data) => request.post(`/clusters/${clusterId}/scaling/import`, data),

  // Create new cluster on controller
  createCluster: (clusterId, data) => request.post(`/clusters/${clusterId}/scaling/create`, data),

  // ==================== Suggestions ====================

  // Get suggestions (silent error - optional feature)
  getSuggestions: (clusterId) => request.get(`/clusters/${clusterId}/scaling/suggestions`, { silentError: true }),

  // ==================== Shard Operations ====================

  // Execute shard failover
  failover: (clusterId, data) => request.post(`/clusters/${clusterId}/scaling/failover`, data),

  // Add a new shard (nodes list, first becomes master)
  addShard: (clusterId, data) => request.post(`/clusters/${clusterId}/scaling/add-shard`, data),

  // Remove a shard
  removeShard: (clusterId, data) => request.post(`/clusters/${clusterId}/scaling/remove-shard`, data),

  // ==================== Slot Operations ====================

  // Migrate slots to target shard
  migrateSlots: (clusterId, data) => request.post(`/clusters/${clusterId}/scaling/migrate-slots`, data),

  // ==================== Node Operations ====================

  // Add a node to a shard
  addNode: (clusterId, data) => request.post(`/clusters/${clusterId}/scaling/add-node`, data),

  // Remove a node from a shard
  removeNode: (clusterId, data) => request.post(`/clusters/${clusterId}/scaling/remove-node`, data),

  // ==================== Task Management ====================

  listTasks: (clusterId, params) => request.get(`/clusters/${clusterId}/scaling/tasks`, { params }),
  getTask: (clusterId, taskId) => request.get(`/clusters/${clusterId}/scaling/tasks/${taskId}`),
  getTaskLogs: (clusterId, taskId, params) => request.get(`/clusters/${clusterId}/scaling/tasks/${taskId}/logs`, { params })
}

export default scalingApi
