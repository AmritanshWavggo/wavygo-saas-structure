import { apiClient } from './apiClient.js'

export const customersApi = {
  listCustomers: async (params = {}) => {
    const payload = await apiClient.get('/customers', params)
    return {
      items: payload.data || [],
      meta: payload.meta || { total: 0, page: 1, limit: 20 },
    }
  },

  getCustomerMetrics: async () => {
    const payload = await apiClient.get('/customers/metrics')
    return payload.data
  },

  getCustomer: async (id) => {
    const payload = await apiClient.get(`/customers/${id}`)
    return payload.data
  },

  createCustomer: async (customerData) => {
    const payload = await apiClient.post('/customers', customerData)
    return payload.data
  },

  updateCustomer: async (id, customerData) => {
    const payload = await apiClient.patch(`/customers/${id}`, customerData)
    return payload.data
  },

  deleteCustomer: async (id) => {
    const payload = await apiClient.delete(`/customers/${id}`)
    return payload.data
  },
}

