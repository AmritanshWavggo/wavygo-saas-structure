import { apiClient } from './apiClient.js'

export const authApi = {
  login: (email, password) => apiClient.post('/auth/login', { email, password }),
  logout: () => apiClient.post('/auth/logout', {}),
  me: () => apiClient.get('/auth/me'),
}
