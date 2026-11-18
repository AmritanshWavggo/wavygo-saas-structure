const rawApiUrl =
  import.meta.env.API_URL ||
  import.meta.env.VITE_API_URL ||
  import.meta.env.VITE_API_BASE_URL ||
  'http://127.0.0.1:8001/api/v1'

const cleanApiUrl = String(rawApiUrl).trim().replace(/\/+$/, '')
const API_BASE_URL = cleanApiUrl.endsWith('/api/v1')
  ? cleanApiUrl
  : `${cleanApiUrl}/api/v1`

/**
 * Universal API request wrapper
 */
export async function apiFetch(endpoint, options = {}) {
  const url = endpoint.startsWith('http')
    ? endpoint
    : `${API_BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`

  const token =
    typeof localStorage !== 'undefined'
      ? localStorage.getItem('access_token') || sessionStorage.getItem('access_token')
      : null

  const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData

  const headers = {
    ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  }

  const response = await fetch(url, {
    ...options,
    headers,
  })

  if (!response.ok) {
    if (response.status === 401) {
      if (typeof localStorage !== 'undefined') {
        localStorage.removeItem('access_token')
      }
      if (typeof sessionStorage !== 'undefined') {
        sessionStorage.removeItem('access_token')
        sessionStorage.removeItem('wavygo-demo-access')
      }
    }

    let errorDetail = `Request failed with status ${response.status}`
    try {
      const errJson = await response.json()
      if (errJson && errJson.detail) {
        errorDetail = typeof errJson.detail === 'string'
          ? errJson.detail
          : JSON.stringify(errJson.detail)
      }
    } catch {
      // Body not JSON
    }
    const error = new Error(errorDetail)
    error.status = response.status
    throw error
  }

  if (response.status === 204) {
    return null
  }

  return response.json()
}

export { API_BASE_URL }
