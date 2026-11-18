import { apiFetch } from './apiClient.js'

export const customerService = {
  /**
   * List customers from the backend
   * @param {Object} options { skip, limit, status }
   */
  async listCustomers({ skip = 0, limit = 50, status } = {}) {
    const params = new URLSearchParams()
    if (skip > 0) params.append('skip', String(skip))
    if (limit) params.append('limit', String(limit))
    if (status && status !== 'All') params.append('status', status)

    const qs = params.toString() ? `?${params.toString()}` : ''
    return apiFetch(`/customers/${qs}`, {
      method: 'GET',
    })
  },

  /**
   * Get single customer by ID
   */
  async getCustomer(customerId) {
    return apiFetch(`/customers/${encodeURIComponent(customerId)}`, {
      method: 'GET',
    })
  },

  /**
   * Create a new customer in backend
   * @param {Object} payload { name, phone, email, status }
   */
  async createCustomer(payload) {
    return apiFetch('/customers/', {
      method: 'POST',
      body: JSON.stringify({
        name: payload.name.trim(),
        phone: payload.phone.trim(),
        email: payload.email && payload.email.trim() ? payload.email.trim().toLowerCase() : null,
        status: payload.status || 'Review',
      }),
    })
  },

  /**
   * Update an existing customer
   */
  async updateCustomer(customerId, payload) {
    return apiFetch(`/customers/${encodeURIComponent(customerId)}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    })
  },

  /**
   * Delete a customer
   */
  async deleteCustomer(customerId) {
    return apiFetch(`/customers/${encodeURIComponent(customerId)}`, {
      method: 'DELETE',
    })
  },
}

export default customerService

