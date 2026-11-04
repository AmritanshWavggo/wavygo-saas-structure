import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import AddBooking from './AddBooking.jsx'
import { vehiclesApi } from '../../services/vehiclesApi.js'
import { customersApi } from '../../services/customersApi.js'
import { bookingsApi } from '../../services/bookingsApi.js'

const mockedNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockedNavigate,
  }
})

vi.mock('../../services/vehiclesApi.js', () => ({
  vehiclesApi: {
    listVehicles: vi.fn(),
  },
}))

vi.mock('../../services/customersApi.js', () => ({
  customersApi: {
    listCustomers: vi.fn(),
  },
}))

vi.mock('../../services/bookingsApi.js', () => ({
  bookingsApi: {
    createBooking: vi.fn(),
  },
}))

function renderAddBooking() {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  })

  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <AddBooking />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('AddBooking Page (Real Hooks & Wizard)', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    vehiclesApi.listVehicles.mockResolvedValue({
      items: [
        {
          id: 'v1',
          name: 'Royal Enfield Classic',
          registration: 'KA 01 AB 1234',
          type: 'Motorcycle',
          dailyRate: 1500,
          price: 1500,
          availability: 'Available',
          pickupLocation: { address: 'Indiranagar Hub' },
        },
      ],
      meta: { total: 1, page: 1, limit: 100 },
    })

    customersApi.listCustomers.mockResolvedValue({
      items: [
        {
          id: 'c1',
          name: 'Aarav Sharma',
          phone: '+919876543210',
          email: 'aarav@example.com',
        },
      ],
      meta: { total: 1, page: 1, limit: 100 },
    })
  })

  it('renders available vehicles and allows stepping through wizard to completion', async () => {
    bookingsApi.createBooking.mockResolvedValue({
      id: 'b_new',
      bookingNumber: 'BK-2026-0099',
    })

    renderAddBooking()

    // Step 0: Select Vehicle
    await waitFor(() => {
      expect(screen.getByText('Royal Enfield Classic')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('Royal Enfield Classic'))
    fireEvent.click(screen.getByRole('button', { name: /continue/i }))

    // Step 1: Select Customer
    await waitFor(() => {
      expect(screen.getByText('Aarav Sharma')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('Aarav Sharma'))
    fireEvent.click(screen.getByRole('button', { name: /continue/i }))

    // Step 2: Rental details
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Rental details' })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: /continue/i }))

    // Step 3: Payment (shows Phase 5 note)
    await waitFor(() => {
      expect(screen.getByText(/TODO: Payment gateway & ledger in Phase 5/i)).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: /continue/i }))

    // Step 4: Review and submit
    await waitFor(() => {
      expect(screen.getByText('Review booking')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /confirm booking/i })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: /confirm booking/i }))

    await waitFor(() => {
      expect(bookingsApi.createBooking).toHaveBeenCalledWith(
        expect.objectContaining({
          vehicleId: 'v1',
          customerId: 'c1',
          status: 'Confirmed',
        })
      )
      expect(mockedNavigate).toHaveBeenCalledWith('/app/bookings')
    })
  })
})
