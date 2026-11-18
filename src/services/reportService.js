import { API_BASE_URL, apiFetch } from './apiClient.js'

export const reportService = {
  /**
   * Get overall reports KPIs
   */
  async getSummary() {
    return apiFetch('/reports/summary', { method: 'GET' })
  },

  /**
   * Get fleet utilization breakdown by vehicle type
   */
  async getUtilizationByType() {
    return apiFetch('/reports/utilization-by-type', { method: 'GET' })
  },

  /**
   * Get top vehicles ranked by actual bookings
   */
  async getTopVehicles(limit = 5) {
    return apiFetch(`/reports/top-vehicles?limit=${limit}`, { method: 'GET' })
  },

  /**
   * Get trend chart data for a specific section
   * @param {string} section e.g. "Overview", "Bookings", "Vehicles", "Maintenance", "Revenue"
   * @param {string} range e.g. "Last 6 months", "This month", "Last 30 days"
   */
  async getTrend(section = 'Overview', range = 'Last 6 months') {
    const params = new URLSearchParams({ section, range })
    return apiFetch(`/reports/trend?${params.toString()}`, { method: 'GET' })
  },

  /**
   * Get full unified reports payload in a single call
   */
  async getFullReport(range = 'Last 6 months') {
    return apiFetch(`/reports/full?range=${encodeURIComponent(range)}`, { method: 'GET' })
  },

  /**
   * Export bookings CSV URL (or triggers direct download)
   */
  getExportCsvUrl() {
    return `${API_BASE_URL}/reports/export/csv`
  },
}

export default reportService

