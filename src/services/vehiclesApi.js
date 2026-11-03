import { apiClient } from './apiClient.js'

export const vehiclesApi = {
  listVehicles: async (params = {}) => {
    const payload = await apiClient.get('/vehicles', params)
    return {
      items: payload.data || [],
      meta: payload.meta || { total: 0, page: 1, limit: 20 },
    }
  },

  getVehicle: async (id) => {
    const payload = await apiClient.get(`/vehicles/${id}`)
    return payload.data
  },

  createVehicle: async (formData) => {
    const payload = await apiClient.postForm('/vehicles', formData)
    return payload.data
  },

  updateVehicle: async (id, formData) => {
    const payload = await apiClient.patchForm(`/vehicles/${id}`, formData)
    return payload.data
  },

  toggleShowOnWavygo: async (id, showOnWavygo) => {
    const payload = await apiClient.patch(`/vehicles/${id}/show-on-wavygo`, { showOnWavygo })
    return payload.data
  },

  deleteVehicle: async (id) => {
    const payload = await apiClient.delete(`/vehicles/${id}`)
    return payload.data
  },
}

