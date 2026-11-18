import { apiFetch } from './apiClient.js'

/**
 * Service to interact with the backend Offline Bookings API endpoints.
 */
export const bookingService = {
  /**
   * Check if backend API is reachable and healthy
   */
  async checkHealth() {
    try {
      const data = await apiFetch('/health')
      return { ok: true, data }
    } catch (error) {
      return { ok: false, error: error.message }
    }
  },

  /**
   * Create an offline booking in the backend
   * @param {Object} payload Payload formatted according to backend OfflineBookingCreate schema
   */
  async createOfflineBooking(payload) {
    return apiFetch('/bookings/offline', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  /**
   * List offline bookings from the backend with optional status and query filter
   */
  async listOfflineBookings({ status, query, skip = 0, limit = 50 } = {}) {
    const params = new URLSearchParams()
    if (status && status !== 'All') params.append('status', status)
    if (query && query.trim()) params.append('query', query.trim())
    if (skip > 0) params.append('skip', String(skip))
    if (limit) params.append('limit', String(limit))

    const qs = params.toString() ? `?${params.toString()}` : ''
    return apiFetch(`/bookings/offline${qs}`, {
      method: 'GET',
    })
  },

  /**
   * Fetch a single offline booking by ID
   */
  async getOfflineBooking(bookingId) {
    return apiFetch(`/bookings/offline/${encodeURIComponent(bookingId)}`, {
      method: 'GET',
    })
  },

  /**
   * Update booking status or notes
   */
  async updateOfflineBooking(bookingId, { status, pickupLocation, notes }) {
    return apiFetch(`/bookings/offline/${encodeURIComponent(bookingId)}`, {
      method: 'PATCH',
      body: JSON.stringify({
        status,
        pickup_location: pickupLocation,
        notes,
      }),
    })
  },

  /**
   * Record a payment against an offline booking
   */
  async recordPayment(bookingId, { amount, method = 'Cash', notes }) {
    return apiFetch(`/bookings/offline/${encodeURIComponent(bookingId)}/payments`, {
      method: 'POST',
      body: JSON.stringify({
        amount: Number(amount),
        method,
        notes,
      }),
    })
  },
}

export default bookingService
