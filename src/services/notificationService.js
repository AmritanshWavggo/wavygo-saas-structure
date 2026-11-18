import { apiFetch } from './apiClient.js'

export const notificationService = {
  /**
   * List all notifications from backend
   */
  async listNotifications({ unreadOnly = false, type, limit = 50 } = {}) {
    const params = new URLSearchParams()
    if (unreadOnly) params.append('unread_only', 'true')
    if (type && type !== 'all') params.append('type', type)
    if (limit) params.append('limit', String(limit))

    const qs = params.toString() ? `?${params.toString()}` : ''
    return apiFetch(`/notifications${qs}`, { method: 'GET' })
  },

  /**
   * Get count of unread notifications
   */
  async getUnreadCount() {
    return apiFetch('/notifications/unread-count', { method: 'GET' })
  },

  /**
   * Mark a single notification as read
   */
  async markRead(notificationId) {
    return apiFetch(`/notifications/${encodeURIComponent(notificationId)}/read`, {
      method: 'PATCH',
    })
  },

  /**
   * Mark all notifications as read
   */
  async markAllRead() {
    return apiFetch('/notifications/mark-all-read', {
      method: 'POST',
    })
  },

  /**
   * Delete a notification
   */
  async deleteNotification(notificationId) {
    return apiFetch(`/notifications/${encodeURIComponent(notificationId)}`, {
      method: 'DELETE',
    })
  },
}

export default notificationService

