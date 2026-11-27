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
  async recordPayment(bookingId, { amount, method = 'Cash', notes, transaction_reference, idempotency_key, payment_date }) {
    return apiFetch(`/bookings/offline/${encodeURIComponent(bookingId)}/payments`, {
      method: 'POST',
      body: JSON.stringify({
        amount: Number(amount),
        method,
        notes,
        transaction_reference,
        idempotency_key: idempotency_key || (typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : `idemp-${Date.now()}`),
        payment_date,
      }),
    })
  },

  /**
   * Send booking OTP for pickup (rent) or return confirmation
   * @param {Object} param0 { phone, purpose, booking_id, vehicle_name, customer_name }
   */
  async sendBookingOtp({ phone, purpose = 'pickup', booking_id, vehicle_name, customer_name }) {
    return apiFetch('/bookings/offline/send-otp', {
      method: 'POST',
      body: JSON.stringify({ phone, purpose, booking_id, vehicle_name, customer_name }),
    })
  },

  /**
   * Verify booking OTP for pickup or return confirmation
   * @param {Object} param0 { phone, purpose, otp, booking_id }
   */
  async verifyBookingOtp({ phone, purpose = 'pickup', otp, booking_id }) {
    return apiFetch('/bookings/offline/verify-otp', {
      method: 'POST',
      body: JSON.stringify({ phone, purpose, otp, booking_id }),
    })
  },
}

export default bookingService
