import { createContext, useContext, useEffect, useState } from 'react'
import { authApi } from '../services/authApi.js'
import { refreshAccessToken, setAccessToken, setAuthenticationFailureHandler } from '../services/apiClient.js'
import { queryClient } from './QueryProvider.jsx'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    setAuthenticationFailureHandler(() => {
      setUser(null)
      queryClient.clear()
    })
    refreshAccessToken()
      .then(({ user: nextUser }) => setUser(nextUser))
      .catch(() => {
        setUser(null)
        queryClient.clear()
      })
      .finally(() => setReady(true))
  }, [])

  async function login(email, password) {
    queryClient.clear()
    const payload = await authApi.login(email, password)
    setAccessToken(payload.data.accessToken)
    setUser(payload.data.user)
  }

  async function logout() {
    try {
      await authApi.logout()
    } finally {
      setAccessToken(null)
      setUser(null)
      queryClient.clear()
    }
  }

  return <AuthContext.Provider value={{ user, ready, login, logout }}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within AuthProvider.')
  return context
}
