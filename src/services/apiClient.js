const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

export class ApiError extends Error {
  constructor(error, status) {
    super(error?.message || 'Request failed.')
    this.name = 'ApiError'
    this.code = error?.code || 'REQUEST_ERROR'
    this.status = status
    this.details = error?.details || []
  }
}

let accessToken = null
let refreshPromise = null
let onAuthenticationFailure = () => {}

export function setAccessToken(token) {
  accessToken = token || null
}

export function getAccessToken() {
  return accessToken
}

export function setAuthenticationFailureHandler(handler) {
  onAuthenticationFailure = handler || (() => {})
}

export async function parseResponse(response) {
  const payload = await response.json().catch(() => null)
  if (!response.ok || !payload?.success) {
    throw new ApiError(payload?.error, response.status)
  }
  return payload
}

export async function refreshAccessToken() {
  if (!refreshPromise) {
    refreshPromise = fetch(`${API_BASE_URL}/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
    })
      .then(parseResponse)
      .then((payload) => {
        setAccessToken(payload.data.accessToken)
        return payload.data
      })
      .catch((err) => {
        setAccessToken(null)
        onAuthenticationFailure()
        throw err
      })
      .finally(() => {
        refreshPromise = null
      })
  }
  return refreshPromise
}

export async function apiRequest(path, options = {}, retried = false) {
  const headers = new Headers(options.headers || {})
  if (accessToken) {
    headers.set('Authorization', `Bearer ${accessToken}`)
  }

  // If sending FormData, remove Content-Type so browser sets multipart boundary automatically
  if (options.body instanceof FormData) {
    headers.delete('Content-Type')
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
    credentials: 'include',
  })

  if (response.status === 401 && !retried && !path.startsWith('/auth/')) {
    try {
      await refreshAccessToken()
      return await apiRequest(path, options, true)
    } catch {
      setAccessToken(null)
      onAuthenticationFailure()
      throw new ApiError({ code: 'UNAUTHORIZED', message: 'Session expired.' }, 401)
    }
  }

  return parseResponse(response)
}

export const apiClient = {
  get: (path, params) => {
    let url = path
    if (params) {
      const searchParams = new URLSearchParams()
      for (const [key, value] of Object.entries(params)) {
        if (value !== undefined && value !== null && value !== '') {
          searchParams.append(key, String(value))
        }
      }
      const qs = searchParams.toString()
      if (qs) {
        url += (url.includes('?') ? '&' : '?') + qs
      }
    }
    return apiRequest(url)
  },
  post: (path, body) =>
    apiRequest(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  postForm: (path, formData) =>
    apiRequest(path, {
      method: 'POST',
      body: formData,
    }),
  patch: (path, body) =>
    apiRequest(path, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  patchForm: (path, formData) =>
    apiRequest(path, {
      method: 'PATCH',
      body: formData,
    }),
  delete: (path) => apiRequest(path, { method: 'DELETE' }),
}

export { API_BASE_URL }
