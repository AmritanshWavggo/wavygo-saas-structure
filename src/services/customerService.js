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
        email_verified: Boolean(payload.email_verified),
        phone_verified: Boolean(payload.phone_verified),
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

  /**
   * Send verification OTP to customer email or phone
   * @param {Object} param0 { target, channel, customer_name }
   */
  async sendCustomerOtp({ target, channel, customer_name }) {
    return apiFetch('/customers/send-otp', {
      method: 'POST',
      body: JSON.stringify({ target, channel, customer_name }),
    })
  },

  /**
   * Verify customer OTP for email or phone
   * @param {Object} param0 { target, channel, otp }
   */
  async verifyCustomerOtp({ target, channel, otp }) {
    return apiFetch('/customers/verify-otp', {
      method: 'POST',
      body: JSON.stringify({ target, channel, otp }),
    })
  },

  /**
   * Manually or confirmedly mark a customer as Verified
   */
  async verifyCustomer(customerId) {
    return apiFetch(`/customers/${encodeURIComponent(customerId)}/verify`, {
      method: 'POST',
    })
  },
}

export default customerService

