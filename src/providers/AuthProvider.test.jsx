import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import { AuthProvider, useAuth } from './AuthProvider.jsx'
import { queryClient } from './QueryProvider.jsx'
import { authApi } from '../services/authApi.js'
import * as apiClient from '../services/apiClient.js'

vi.mock('../services/authApi.js', () => ({
  authApi: {
    login: vi.fn(),
    logout: vi.fn(),
    me: vi.fn(),
  },
}))

vi.mock('../services/apiClient.js', () => ({
  refreshAccessToken: vi.fn(),
  setAccessToken: vi.fn(),
  setAuthenticationFailureHandler: vi.fn(),
}))

function TestConsumer() {
  const { user, ready, login, logout } = useAuth()
  return (
    <div>
      <div data-testid="status">{ready ? 'ready' : 'loading'}</div>
      <div data-testid="user">{user ? user.email : 'anonymous'}</div>
      <button onClick={() => login('owner@example.com', 'pass123')}>Login</button>
      <button onClick={() => logout()}>Logout</button>
    </div>
  )
}

describe('AuthProvider cache invalidation', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(queryClient, 'clear')
  })

  it('clears queryClient cache on failed session restore during initial mount', async () => {
    vi.mocked(apiClient.refreshAccessToken).mockRejectedValue(new Error('No active session'))

    await act(async () => {
      render(
        <AuthProvider>
          <TestConsumer />
        </AuthProvider>
      )
    })

    expect(screen.getByTestId('status').textContent).toBe('ready')
    expect(screen.getByTestId('user').textContent).toBe('anonymous')
    expect(queryClient.clear).toHaveBeenCalled()
  })

  it('clears queryClient cache on login', async () => {
    vi.mocked(apiClient.refreshAccessToken).mockResolvedValue({ user: null })
    vi.mocked(authApi.login).mockResolvedValue({
      data: {
        accessToken: 'mock_jwt_token',
        user: { id: 'u_owner', email: 'owner@example.com', role: 'owner' },
      },
    })

    await act(async () => {
      render(
        <AuthProvider>
          <TestConsumer />
        </AuthProvider>
      )
    })

    queryClient.clear.mockClear()

    await act(async () => {
      screen.getByText('Login').click()
    })

    expect(authApi.login).toHaveBeenCalledWith('owner@example.com', 'pass123')
    expect(queryClient.clear).toHaveBeenCalled()
    expect(screen.getByTestId('user').textContent).toBe('owner@example.com')
  })

  it('clears queryClient cache on logout', async () => {
    vi.mocked(apiClient.refreshAccessToken).mockResolvedValue({
      user: { id: 'u_owner', email: 'owner@example.com', role: 'owner' },
    })
    vi.mocked(authApi.logout).mockResolvedValue({ success: true })

    await act(async () => {
      render(
        <AuthProvider>
          <TestConsumer />
        </AuthProvider>
      )
    })

    queryClient.clear.mockClear()

    await act(async () => {
      screen.getByText('Logout').click()
    })

    expect(authApi.logout).toHaveBeenCalled()
    expect(queryClient.clear).toHaveBeenCalled()
    expect(screen.getByTestId('user').textContent).toBe('anonymous')
  })
})

