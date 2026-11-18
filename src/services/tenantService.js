import { apiFetch } from './apiClient.js'

export const tenantService = {
  /**
   * Get current authenticated tenant/vendor profile & settings
   */
  async getCurrentTenant() {
    return apiFetch('/tenants/current')
  },

  /**
   * Update tenant profile, address, rental rules, notifications
   */
  async updateCurrentTenant(updates) {
    return apiFetch('/tenants/current', {
      method: 'PUT',
      body: JSON.stringify(updates),
    })
  },

  /**
   * Get real-time aggregated metrics for the tenant
   */
  async getTenantStats() {
    return apiFetch('/tenants/stats')
  },
}

