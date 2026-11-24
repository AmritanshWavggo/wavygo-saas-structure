import { API_BASE_URL, apiFetch } from './apiClient.js'

export const vehicleService = {
  /**
   * List vehicles with optional filters
   */
  async listVehicles({ search, type, fuel, fleetAvailability, listing = 'all', page = 1, limit = 50 } = {}) {
    const params = new URLSearchParams()
    if (search && search.trim()) params.append('search', search.trim())
    if (type && type !== 'All' && type !== 'All types') params.append('type', type)
    if (fuel && fuel !== 'All' && fuel !== 'All fuels') params.append('fuel', fuel)
    if (fleetAvailability && fleetAvailability !== 'All' && fleetAvailability !== 'All availability') {
      params.append('fleetAvailability', fleetAvailability)
    }
    if (listing && listing !== 'all') params.append('listing', listing.toLowerCase())
    if (page > 1) params.append('page', String(page))
    if (limit) params.append('limit', String(limit))

    const qs = params.toString() ? `?${params.toString()}` : ''
    return apiFetch(`/vehicles${qs}`)
  },

  /**
   * Get single vehicle by ID
   */
  async getVehicle(vehicleId) {
    return apiFetch(`/vehicles/${encodeURIComponent(vehicleId)}`)
  },

  /**
   * Create a new vehicle (multipart/form-data)
   * @param {FormData} formData
   */
  async createVehicle(formData) {
    return apiFetch('/vehicles', {
      method: 'POST',
      body: formData,
    })
  },

  /**
   * Toggle vehicle Show on WavyGo status
   */
  async toggleShowOnWavygo(vehicleId, showOnWavygo) {
    return apiFetch(`/vehicles/${encodeURIComponent(vehicleId)}/show-on-wavygo`, {
      method: 'PATCH',
      body: JSON.stringify({ showOnWavygo }),
    })
  },

  /**
   * Update vehicle (multipart/form-data or JSON object)
   */
  async updateVehicle(vehicleId, updates) {
    let body = updates
    if (!(updates instanceof FormData)) {
      body = new FormData()
      Object.entries(updates).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          body.append(key, String(value))
        }
      })
    }
    return apiFetch(`/vehicles/${encodeURIComponent(vehicleId)}`, {
      method: 'PATCH',
      body,
    })
  },

  /**
   * Delete vehicle
   */
  async deleteVehicle(vehicleId) {
    return apiFetch(`/vehicles/${encodeURIComponent(vehicleId)}`, {
      method: 'DELETE',
    })
  },
}

export default vehicleService

