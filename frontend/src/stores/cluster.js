import { defineStore } from 'pinia'
import { ref } from 'vue'
import request from '@/utils/request'

export const useClusterStore = defineStore('cluster', () => {
  const clusters = ref([])
  const currentCluster = ref(null)
  const loading = ref(false)

  async function fetchClusters(params = {}) {
    loading.value = true
    try {
      const response = await request.get('/clusters', { params })
      clusters.value = response
      return response
    } finally {
      loading.value = false
    }
  }

  async function fetchCluster(id) {
    loading.value = true
    try {
      const response = await request.get(`/clusters/${id}`)
      currentCluster.value = response
      return response
    } finally {
      loading.value = false
    }
  }

  async function createCluster(data) {
    const response = await request.post('/clusters', data)
    await fetchClusters()
    return response
  }

  async function updateCluster(id, data) {
    const response = await request.put(`/clusters/${id}`, data)
    await fetchClusters()
    return response
  }

  async function deleteCluster(id) {
    await request.delete(`/clusters/${id}`)
    await fetchClusters()
  }

  async function refreshClusterStatus(id) {
    const response = await request.post(`/clusters/${id}/refresh-status`)
    await fetchCluster(id)
    return response
  }

  return {
    clusters,
    currentCluster,
    loading,
    fetchClusters,
    fetchCluster,
    createCluster,
    updateCluster,
    deleteCluster,
    refreshClusterStatus
  }
})
