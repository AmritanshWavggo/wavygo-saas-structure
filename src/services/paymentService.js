import { API_BASE_URL, apiFetch } from './apiClient.js'

/**
 * Service to interact with the backend Payments API
 */
export const paymentService = {
  /**
   * List all payment transactions with optional filtering
   */
  async listPayments({ status, method, query, skip = 0, limit = 50 } = {}) {
    const params = new URLSearchParams()
    if (status && status !== 'All') params.append('status', status)
    if (method && method !== 'All') params.append('method', method)
    if (query && query.trim()) params.append('query', query.trim())
    if (skip > 0) params.append('skip', String(skip))
    if (limit) params.append('limit', String(limit))

    const qs = params.toString() ? `?${params.toString()}` : ''
    return apiFetch(`/payments${qs}`)
  },

  /**
   * Get payment & finance aggregated metrics
   */
  async getPaymentStats() {
    return apiFetch('/payments/stats')
  },

  /**
   * Get single transaction details by ID
   */
  async getPayment(paymentId) {
    return apiFetch(`/payments/${encodeURIComponent(paymentId)}`)
  },

  /**
   * Record a new payment transaction
   */
  async recordPayment(payload) {
    return apiFetch('/payments', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  /**
   * Update payment status or notes
   */
  async updatePayment(paymentId, updates) {
    return apiFetch(`/payments/${encodeURIComponent(paymentId)}`, {
      method: 'PATCH',
      body: JSON.stringify(updates),
    })
  },

  /**
   * Process a refund for a transaction
   */
  async refundPayment(paymentId, reason) {
    const qs = reason ? `?reason=${encodeURIComponent(reason)}` : ''
    return apiFetch(`/payments/${encodeURIComponent(paymentId)}/refund${qs}`, {
      method: 'POST',
    })
  },
}

export default paymentService
