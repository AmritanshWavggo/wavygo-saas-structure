import { apiClient } from './apiClient.js'

export const bookingsApi = {
  listBookings: async (params = {}) => {
    const payload = await apiClient.get('/bookings', params)
    return {
      items: payload.data || [],
      meta: payload.meta || { total: 0, page: 1, limit: 20 },
    }
  },

  getBooking: async (id) => {
    const payload = await apiClient.get(`/bookings/${id}`)
    return payload.data
  },

  createBooking: async (data) => {
    const payload = await apiClient.post('/bookings', data)
    return payload.data
  },

  updateBooking: async (id, data) => {
    const payload = await apiClient.patch(`/bookings/${id}`, data)
    return payload.data
  },

  transitionStatus: async (id, statusData) => {
    const payload = await apiClient.patch(`/bookings/${id}/status`, statusData)
    return payload.data
  },

  deleteBooking: async (id) => {
    const payload = await apiClient.delete(`/bookings/${id}`)
    return payload
  },

  checkAvailability: async (params) => {
    const payload = await apiClient.get('/bookings/availability', params)
    return payload.data
  },
}

