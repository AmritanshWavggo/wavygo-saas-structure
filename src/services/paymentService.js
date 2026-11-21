import { apiFetch } from './apiClient.js'

/**
 * Service to interact with the backend Payments API
 */
export const paymentService = {
  /**
   * List all payment transactions with optional filtering
   */
  async listPayments({ status, method, booking_id, query, skip = 0, limit = 50 } = {}) {
    const params = new URLSearchParams()
    if (status && status !== 'All') params.append('status', status)
    if (method && method !== 'All') params.append('method', method)
    if (booking_id) params.append('booking_id', booking_id)
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
   * Record a new payment transaction with idempotency and reference
   */
  async recordPayment(payload) {
    const body = {
      booking_id: payload.booking_id || payload.booking,
      amount: Number(payload.amount),
      method: payload.method || 'Cash',
      customer_name: payload.customer_name || payload.customer || undefined,
      transaction_reference: payload.transaction_reference ? String(payload.transaction_reference).trim() : null,
      payment_date: payload.payment_date || undefined,
      notes: payload.notes ? String(payload.notes).trim() : null,
      idempotency_key: payload.idempotency_key || (typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : `idemp-${Date.now()}`),
    }

    return apiFetch('/payments', {
      method: 'POST',
      body: JSON.stringify(body),
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
