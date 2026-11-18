import { apiFetch } from './apiClient.js'

/**
 * Service to interact with the backend Documents API and Cloudinary uploads.
 */
export const documentService = {
  /**
   * Upload a document file to Cloudinary and store metadata + URL in database
   * @param {FormData} formData Contains file, name, category, scope, etc.
   */
  async uploadDocument(formData) {
    return apiFetch('/documents/upload', {
      method: 'POST',
      body: formData,
    })
  },

  /**
   * List documents with optional filters
   */
  async listDocuments({ scope, category, status, query, skip = 0, limit = 50 } = {}) {
    const params = new URLSearchParams()
    if (scope && scope !== 'All') params.append('scope', scope)
    if (category && category !== 'All') params.append('category', category)
    if (status && status !== 'All') params.append('status', status)
    if (query && query.trim()) params.append('query', query.trim())
    if (skip > 0) params.append('skip', String(skip))
    if (limit) params.append('limit', String(limit))

    const qs = params.toString() ? `?${params.toString()}` : ''
    return apiFetch(`/documents${qs}`)
  },

  /**
   * Fetch single document by ID
   */
  async getDocument(documentId) {
    return apiFetch(`/documents/${encodeURIComponent(documentId)}`)
  },

  /**
   * Update document details or status
   */
  async updateDocument(documentId, updates) {
    return apiFetch(`/documents/${encodeURIComponent(documentId)}`, {
      method: 'PATCH',
      body: JSON.stringify(updates),
    })
  },

  /**
   * Delete document from DB and Cloudinary
   */
  async deleteDocument(documentId) {
    return apiFetch(`/documents/${encodeURIComponent(documentId)}`, {
      method: 'DELETE',
    })
  },
}

export default documentService
