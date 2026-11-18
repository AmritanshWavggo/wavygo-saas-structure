import { apiFetch } from './apiClient.js'

export const staffService = {
  async listStaff() {
    return apiFetch('/staff', { method: 'GET' })
  },

  async createStaff(payload) {
    return apiFetch('/staff', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  async updateStaffStatus(staffId, status) {
    return apiFetch(`/staff/${staffId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    })
  },

  async uploadStaffDocument(staffId, category, file) {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('category', category)
    return apiFetch(`/staff/${staffId}/documents`, {
      method: 'POST',
      body: formData,
    })
  },

  async deleteStaffDocument(staffId, documentId) {
    return apiFetch(`/staff/${staffId}/documents/${documentId}`, {
      method: 'DELETE',
    })
  },

  async deleteStaff(staffId) {
    return apiFetch(`/staff/${staffId}`, {
      method: 'DELETE',
    })
  },
}

export default staffService

