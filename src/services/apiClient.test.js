import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import {
  apiClient,
  apiRequest,
  parseResponse,
  ApiError,
  setAccessToken,
  getAccessToken,
  setAuthenticationFailureHandler,
  API_BASE_URL,
} from './apiClient.js'

describe('apiClient', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    setAccessToken(null)
    setAuthenticationFailureHandler(() => {})
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('envelope unwrapping and error parsing', () => {
    it('unwraps successful API response payload', async () => {
      const mockPayload = { success: true, data: { id: 'veh_123', makeModel: 'Ather 450X' } }
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => mockPayload,
      })

      const res = await apiRequest('/vehicles')
      expect(res).toEqual(mockPayload)
      expect(res.data.id).toBe('veh_123')
    })

    it('throws ApiError with code, message and status on unsuccessful envelope', async () => {
      const mockErrorPayload = {
        success: false,
        data: null,
        error: { code: 'NOT_FOUND', message: 'Vehicle does not exist.' },
      }
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        json: async () => mockErrorPayload,
      })

      await expect(apiRequest('/vehicles/999')).rejects.toThrow('Vehicle does not exist.')
      try {
        await apiRequest('/vehicles/999')
      } catch (err) {
        expect(err).toBeInstanceOf(ApiError)
        expect(err.code).toBe('NOT_FOUND')
        expect(err.status).toBe(404)
        expect(err.details).toEqual([])
      }
    })

    it('extracts field-level details on 422 validation errors', async () => {
      const mockValidationPayload = {
        success: false,
        data: null,
        error: {
          code: 'VALIDATION_ERROR',
          message: 'Validation failed.',
          details: [{ field: 'year', message: 'Model year must be 2000 or later.' }],
        },
      }
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        json: async () => mockValidationPayload,
      })

      try {
        await apiRequest('/vehicles')
        expect.fail('Should have thrown ApiError')
      } catch (err) {
        expect(err).toBeInstanceOf(ApiError)
        expect(err.status).toBe(422)
        expect(err.code).toBe('VALIDATION_ERROR')
        expect(err.details).toEqual([{ field: 'year', message: 'Model year must be 2000 or later.' }])
      }
    })
  })

  describe('concurrent 401 handling', () => {
    it('triggers exactly ONE shared refresh call when concurrent 401s occur', async () => {
      setAccessToken('expired_token')

      let refreshCount = 0
      let vehicleCallCount = 0

      global.fetch = vi.fn().mockImplementation(async (url) => {
        if (url.endsWith('/auth/refresh')) {
          refreshCount++
          // Artificial micro-delay to simulate in-flight network refresh
          await new Promise((resolve) => setTimeout(resolve, 20))
          return {
            ok: true,
            status: 200,
            json: async () => ({
              success: true,
              data: {
                accessToken: 'fresh_token_xyz',
                user: { id: 'u_1', role: 'owner' },
              },
            }),
          }
        }

        if (url.includes('/vehicles')) {
          vehicleCallCount++
          // First calls fail with 401, retried calls succeed with new token
          if (getAccessToken() === 'fresh_token_xyz') {
            return {
              ok: true,
              status: 200,
              json: async () => ({ success: true, data: { items: [{ id: 'veh_1' }] } }),
            }
          }
          return {
            ok: false,
            status: 401,
            json: async () => ({
              success: false,
              data: null,
              error: { code: 'UNAUTHORIZED', message: 'Token expired.' },
            }),
          }
        }

        return {
          ok: false,
          status: 500,
          json: async () => ({ success: false, error: { message: 'Unexpected' } }),
        }
      })

      // Fire two concurrent requests that both encounter 401
      const [res1, res2] = await Promise.all([
        apiClient.get('/vehicles'),
        apiClient.get('/vehicles'),
      ])

      expect(res1.success).toBe(true)
      expect(res2.success).toBe(true)
      expect(res1.data.items[0].id).toBe('veh_1')
      expect(res2.data.items[0].id).toBe('veh_1')

      // Key assertion: /auth/refresh was called exactly ONCE
      expect(refreshCount).toBe(1)
      expect(getAccessToken()).toBe('fresh_token_xyz')
    })
  })

  describe('retry once then redirect on failure', () => {
    it('calls onAuthenticationFailure when refresh fails after 401', async () => {
      setAccessToken('bad_token')
      const authFailureHandler = vi.fn()
      setAuthenticationFailureHandler(authFailureHandler)

      global.fetch = vi.fn().mockImplementation(async (url) => {
        if (url.endsWith('/auth/refresh')) {
          return {
            ok: false,
            status: 401,
            json: async () => ({
              success: false,
              data: null,
              error: { code: 'SESSION_EXPIRED', message: 'Refresh token invalid' },
            }),
          }
        }
        return {
          ok: false,
          status: 401,
          json: async () => ({
            success: false,
            data: null,
            error: { code: 'UNAUTHORIZED', message: 'Unauthorized' },
          }),
        }
      })

      await expect(apiClient.get('/vehicles')).rejects.toThrow()
      expect(authFailureHandler).toHaveBeenCalled()
      expect(getAccessToken()).toBeNull()
    })
  })

  describe('FormData headers handling', () => {
    it('sends FormData without a manual Content-Type header', async () => {
      setAccessToken('test_token')
      let capturedHeaders = null

      global.fetch = vi.fn().mockImplementation(async (url, init) => {
        capturedHeaders = init.headers
        return {
          ok: true,
          status: 201,
          json: async () => ({ success: true, data: { id: 'veh_new' } }),
        }
      })

      const formData = new FormData()
      formData.append('makeModel', 'Royal Enfield Hunter 350')

      await apiClient.postForm('/vehicles', formData)

      expect(global.fetch).toHaveBeenCalled()
      expect(capturedHeaders).toBeInstanceOf(Headers)
      // Content-Type must NOT be manually set so browser adds multipart boundary
      expect(capturedHeaders.get('Content-Type')).toBeNull()
      // Authorization header must still be present
      expect(capturedHeaders.get('Authorization')).toBe('Bearer test_token')
    })
  })
})

