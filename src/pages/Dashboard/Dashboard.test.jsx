import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import Dashboard from './Dashboard.jsx'
import { DemoDataProvider } from '../../data/DemoDataContext.jsx'
import { vehiclesApi } from '../../services/vehiclesApi.js'
import { customersApi } from '../../services/customersApi.js'
import { AuthProvider, useAuth } from '../../providers/AuthProvider.jsx'
import { authApi } from '../../services/authApi.js'
import * as apiClient from '../../services/apiClient.js'
import { queryClient } from '../../providers/QueryProvider.jsx'

vi.mock('../../services/vehiclesApi.js', () => ({
  vehiclesApi: {
    listVehicles: vi.fn(),
  },
}))

vi.mock('../../services/customersApi.js', () => ({
  customersApi: {
    getCustomerMetrics: vi.fn(),
  },
}))

vi.mock('../../services/authApi.js', () => ({
  authApi: {
    login: vi.fn(),
    logout: vi.fn(),
  },
}))

vi.mock('../../services/apiClient.js', () => ({
  refreshAccessToken: vi.fn(),
  setAccessToken: vi.fn(),
  setAuthenticationFailureHandler: vi.fn(),
}))

function renderDashboard(customClient) {
  const client =
    customClient ||
    new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    })

  return render(
    <QueryClientProvider client={client}>
      <DemoDataProvider>
        <MemoryRouter>
          <Dashboard />
        </MemoryRouter>
      </DemoDataProvider>
    </QueryClientProvider>
  )
}

describe('Dashboard real tenant metric cards (Option B - 5 cards)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders real numbers for vehicles and customers from api meta and metrics', async () => {
    vi.mocked(vehiclesApi.listVehicles).mockResolvedValue({
      items: [],
      meta: { total: 14, page: 1, limit: 1 },
    })
    vi.mocked(customersApi.getCustomerMetrics).mockResolvedValue({
      totalCustomers: 28,
      verifiedProfiles: 24,
      totalCollected: null,
      pendingDues: null,
    })

    renderDashboard()

    await waitFor(() => {
      expect(screen.getByTestId('total-vehicles-value')).toHaveTextContent('14')
      expect(screen.getByTestId('total-customers-value')).toHaveTextContent('28')
    })

    expect(vehiclesApi.listVehicles).toHaveBeenCalledWith({ limit: 1 })
    expect(customersApi.getCustomerMetrics).toHaveBeenCalled()
  })

  it('shows loading state on metric cards while queries are pending', () => {
    vi.mocked(vehiclesApi.listVehicles).mockReturnValue(new Promise(() => {}))
    vi.mocked(customersApi.getCustomerMetrics).mockReturnValue(new Promise(() => {}))

    renderDashboard()

    expect(screen.getByTestId('total-vehicles-loading')).toBeInTheDocument()
    expect(screen.getByTestId('total-customers-loading')).toBeInTheDocument()
  })

  it('shows error state with retry button and recovers on user retry', async () => {
    vi.mocked(vehiclesApi.listVehicles).mockRejectedValueOnce(new Error('Network error'))
    vi.mocked(customersApi.getCustomerMetrics).mockResolvedValue({
      totalCustomers: 8,
      verifiedProfiles: 6,
    })

    renderDashboard()

    await waitFor(() => {
      expect(screen.getByTestId('total-vehicles-error')).toHaveTextContent('Failed to load')
      expect(screen.getByRole('button', { name: /retry loading total vehicles/i })).toBeInTheDocument()
    })

    // Setup recovery response
    vi.mocked(vehiclesApi.listVehicles).mockResolvedValueOnce({
      items: [],
      meta: { total: 19, page: 1, limit: 1 },
    })

    fireEvent.click(screen.getByRole('button', { name: /retry loading total vehicles/i }))

    await waitFor(() => {
      expect(screen.getByTestId('total-vehicles-value')).toHaveTextContent('19')
    })
  })

  it('renders zero state with 0 and empty captions when totals are zero', async () => {
    vi.mocked(vehiclesApi.listVehicles).mockResolvedValue({
      items: [],
      meta: { total: 0, page: 1, limit: 1 },
    })
    vi.mocked(customersApi.getCustomerMetrics).mockResolvedValue({
      totalCustomers: 0,
      verifiedProfiles: 0,
      totalCollected: null,
      pendingDues: null,
    })

    renderDashboard()

    await waitFor(() => {
      expect(screen.getByTestId('total-vehicles-value')).toHaveTextContent('0')
      expect(screen.getByText('0 vehicles in fleet')).toBeInTheDocument()
      expect(screen.getByTestId('total-customers-value')).toHaveTextContent('0')
      expect(screen.getByText('0 registered customers')).toBeInTheDocument()
    })
  })

  it('displays visible "Demo data until Phase 5" badge on remaining demo cards', async () => {
    vi.mocked(vehiclesApi.listVehicles).mockResolvedValue({
      items: [],
      meta: { total: 5, page: 1, limit: 1 },
    })
    vi.mocked(customersApi.getCustomerMetrics).mockResolvedValue({
      totalCustomers: 12,
    })

    renderDashboard()

    const demoBadges = screen.getAllByText('Demo data until Phase 5')
    // 3 demo cards: Available vehicles, Active bookings, Revenue
    expect(demoBadges.length).toBe(3)
  })

  it('clears query cache and shows no old data when switching tenants through AuthProvider logout and login', async () => {
    const clearSpy = vi.spyOn(queryClient, 'clear')

    // Initial session: Tenant A is logged in
    vi.mocked(apiClient.refreshAccessToken).mockResolvedValue({
      user: { id: 'u_tenant_a', email: 'owner@tenant-a.com', tenantId: 'tenant_a' },
    })
    vi.mocked(vehiclesApi.listVehicles).mockResolvedValue({
      items: [],
      meta: { total: 10, page: 1, limit: 1 },
    })
    vi.mocked(customersApi.getCustomerMetrics).mockResolvedValue({
      totalCustomers: 25,
      verifiedProfiles: 20,
    })

    function IntegratedAuthDashboard() {
      const { logout, login } = useAuth()
      return (
        <div>
          <button onClick={() => logout()}>Logout Tenant</button>
          <button onClick={() => login('owner@tenant-b.com', 'secret')}>Login Tenant B</button>
          <Dashboard />
        </div>
      )
    }

    await act(async () => {
      render(
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <DemoDataProvider>
              <MemoryRouter>
                <IntegratedAuthDashboard />
              </MemoryRouter>
            </DemoDataProvider>
          </AuthProvider>
        </QueryClientProvider>
      )
    })

    // Tenant A metrics appear
    await waitFor(() => {
      expect(screen.getByTestId('total-vehicles-value')).toHaveTextContent('10')
      expect(screen.getByTestId('total-customers-value')).toHaveTextContent('25')
    })

    clearSpy.mockClear()
    vi.mocked(authApi.logout).mockResolvedValue({ success: true })

    // Tenant A logs out through real AuthProvider logout()
    await act(async () => {
      screen.getByText('Logout Tenant').click()
    })

    // queryClient.clear was invoked
    expect(clearSpy).toHaveBeenCalled()

    // Configure Tenant B API responses
    vi.mocked(authApi.login).mockResolvedValue({
      data: {
        accessToken: 'token_tenant_b',
        user: { id: 'u_tenant_b', email: 'owner@tenant-b.com', tenantId: 'tenant_b' },
      },
    })
    vi.mocked(vehiclesApi.listVehicles).mockResolvedValue({
      items: [],
      meta: { total: 2, page: 1, limit: 1 },
    })
    vi.mocked(customersApi.getCustomerMetrics).mockResolvedValue({
      totalCustomers: 5,
      verifiedProfiles: 4,
    })

    clearSpy.mockClear()

    // Tenant B logs in through real AuthProvider login()
    await act(async () => {
      screen.getByText('Login Tenant B').click()
    })

    // queryClient.clear was invoked again upon login
    expect(clearSpy).toHaveBeenCalled()

    // Tenant B metrics load, Tenant A numbers (10 and 25) are completely gone
    await waitFor(() => {
      expect(screen.getByTestId('total-vehicles-value')).toHaveTextContent('2')
      expect(screen.getByTestId('total-customers-value')).toHaveTextContent('5')
    })

    expect(screen.queryByText('10')).not.toBeInTheDocument()
    expect(screen.queryByText('25')).not.toBeInTheDocument()
  })
})

