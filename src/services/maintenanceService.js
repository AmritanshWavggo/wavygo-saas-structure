import { apiFetch } from './apiClient.js'

/**
 * Service to interact with the backend Maintenance API
 */
export const maintenanceService = {
  /**
   * List all maintenance records with optional status, vehicle, or search query filter
   */
  async listMaintenance({ status, vehicle_id, query, skip = 0, limit = 50 } = {}) {
    const params = new URLSearchParams()
    if (status && status !== 'All') params.append('status', status)
    if (vehicle_id) params.append('vehicle_id', vehicle_id)
    if (query && query.trim()) params.append('query', query.trim())
    if (skip > 0) params.append('skip', String(skip))
    if (limit) params.append('limit', String(limit))

    const qs = params.toString() ? `?${params.toString()}` : ''
    return apiFetch(`/maintenance${qs}`)
  },

  /**
   * Get maintenance stats (open jobs, completed jobs, total cost)
   */
  async getMaintenanceStats() {
    return apiFetch('/maintenance/stats')
  },

  /**
   * Get single maintenance record by ID
   */
  async getMaintenance(maintenanceId) {
    return apiFetch(`/maintenance/${encodeURIComponent(maintenanceId)}`)
  },

  /**
   * Create new maintenance record (sends vehicle to Maintenance)
   */
  async createMaintenance(payload) {
    return apiFetch('/maintenance', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  /**
   * Update maintenance record details
   */
  async updateMaintenance(maintenanceId, updates) {
    return apiFetch(`/maintenance/${encodeURIComponent(maintenanceId)}`, {
      method: 'PATCH',
      body: JSON.stringify(updates),
    })
  },

  /**
   * Complete maintenance job and release vehicle back to Available status
   */
  async completeMaintenance(maintenanceId, returnToAvailable = true) {
    return apiFetch(
      `/maintenance/${encodeURIComponent(maintenanceId)}/complete?return_to_available=${returnToAvailable}`,
      {
        method: 'POST',
      },
    )
  },

  /**
   * Delete maintenance record
   */
  async deleteMaintenance(maintenanceId) {
    return apiFetch(`/maintenance/${encodeURIComponent(maintenanceId)}`, {
      method: 'DELETE',
    })
  },

  /**
   * Transition vehicle operational status (e.g. Under Review, Available, Maintenance, Rented)
   */
  async updateVehicleReviewStatus({ vehicle_id, status, notes }) {
    return apiFetch('/maintenance/vehicle-status', {
      method: 'POST',
      body: JSON.stringify({ vehicle_id, status, notes }),
    })
  },
}
