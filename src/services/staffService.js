import { apiFetch, API_BASE_URL } from './apiClient.js'

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

  async updateStaff(staffId, payload) {
    return apiFetch(`/staff/${encodeURIComponent(staffId)}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    })
  },

  async updateStaffStatus(staffId, status) {
    return apiFetch(`/staff/${staffId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    })
  },

  async listStaffDocuments(staffId) {
    return apiFetch(`/staff/${encodeURIComponent(staffId)}/documents`, {
      method: 'GET',
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

  async replaceStaffDocument(staffId, documentId, file) {
    const formData = new FormData()
    formData.append('file', file)
    return apiFetch(`/staff/${encodeURIComponent(staffId)}/documents/${encodeURIComponent(documentId)}`, {
      method: 'PUT',
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

  async downloadStaffDocument(staffId, documentId, filename) {
    const token =
      typeof localStorage !== 'undefined'
        ? localStorage.getItem('access_token') ||
          sessionStorage.getItem('access_token')
        : null

    const res = await fetch(
      `${API_BASE_URL}/staff/${encodeURIComponent(staffId)}/documents/${encodeURIComponent(documentId)}/download`,
      {
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      }
    )
    if (!res.ok) {
      throw new Error(`Failed to download document: ${res.statusText}`)
    }
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename || 'document'
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 10000)
  },

  async getStaffDocumentBlobUrl(staffId, documentId) {
    const token =
      typeof localStorage !== 'undefined'
        ? localStorage.getItem('access_token') ||
          sessionStorage.getItem('access_token')
        : null

    const res = await fetch(
      `${API_BASE_URL}/staff/${encodeURIComponent(staffId)}/documents/${encodeURIComponent(documentId)}/download`,
      {
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      }
    )
    if (!res.ok) {
      throw new Error(`Failed to load document preview: ${res.statusText}`)
    }
    const blob = await res.blob()
    return URL.createObjectURL(blob)
  },
}


export default staffService

