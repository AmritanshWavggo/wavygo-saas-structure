import { apiFetch } from './apiClient.js'

export const dashboardService = {
  /**
   * Fetch aggregated live dashboard statistics, fleet utilization, revenue trend, and recent bookings.
   * @param {string} range e.g. "Last 30 days", "Last 7 days", "This month", "Last 90 days"
   */
  async getStats(range = 'Last 30 days') {
    const params = new URLSearchParams()
    if (range) params.append('range', range)
    const qs = params.toString() ? `?${params.toString()}` : ''
    return apiFetch(`/dashboard/stats${qs}`, { method: 'GET' })
  },

  /**
   * Mark an upcoming vehicle arrival as arrived.
   * This completes the booking and moves the rented bike into 'Under Review'.
   * @param {string} bookingId
   */
  async markArrival(bookingId) {
    return apiFetch(`/dashboard/arrivals/${encodeURIComponent(bookingId)}/arrive`, {
      method: 'POST',
    })
  },
}

export default dashboardService

