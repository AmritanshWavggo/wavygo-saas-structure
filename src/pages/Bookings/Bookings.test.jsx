import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import Bookings from './Bookings.jsx'
import { bookingsApi } from '../../services/bookingsApi.js'
import * as AuthProvider from '../../providers/AuthProvider.jsx'

vi.mock('../../services/bookingsApi.js', () => ({
  bookingsApi: {
    listBookings: vi.fn(),
    transitionStatus: vi.fn(),
    deleteBooking: vi.fn(),
  },
}))

function renderBookings(role = 'owner') {
  vi.spyOn(AuthProvider, 'useAuth').mockReturnValue({
    user: { id: 'u1', name: 'Test User', role },
  })

  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  })

  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Bookings />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

const mockBookingsData = {
  items: [
    {
      id: 'b1',
      bookingNumber: 'BK-2026-0001',
      status: 'Pending',
      startDate: '2026-11-15T10:00:00Z',
      endDate: '2026-11-18T10:00:00Z',
      billableDays: 3,
      dailyRatePaise: 250000,
      baseAmountPaise: 750000,
      discountPaise: 0,
      totalAmountPaise: 750000,
      customerSnapshot: { name: 'Aarav Sharma', phone: '+919876543210' },
      vehicleSnapshot: { name: 'Hyundai Creta', registration: 'KA 01 AB 1234' },
      createdAt: '2026-11-10T12:00:00Z',
    },
    {
      id: 'b2',
      bookingNumber: 'BK-2026-0002',
      status: 'Confirmed',
      startDate: '2026-11-20T10:00:00Z',
      endDate: '2026-11-22T10:00:00Z',
      billableDays: 2,
      dailyRatePaise: 150000,
      baseAmountPaise: 300000,
      discountPaise: 0,
      totalAmountPaise: 300000,
      customerSnapshot: { name: 'Neha Patel', phone: '+919123456789' },
      vehicleSnapshot: { name: 'Royal Enfield Hunter', registration: 'KA 01 CD 5678' },
      createdAt: '2026-11-10T12:00:00Z',
      confirmedAt: '2026-11-10T14:00:00Z',
    },
    {
      id: 'b3',
      bookingNumber: 'BK-2026-0003',
      status: 'Active',
      startDate: '2026-11-05T10:00:00Z',
      endDate: '2026-11-12T10:00:00Z',
      billableDays: 7,
      dailyRatePaise: 250000,
      baseAmountPaise: 1750000,
      discountPaise: 0,
      totalAmountPaise: 1750000,
      customerSnapshot: { name: 'Rohit Verma', phone: '+919988776655' },
      vehicleSnapshot: { name: 'Hyundai Creta', registration: 'KA 01 AB 1234' },
      createdAt: '2026-11-05T09:00:00Z',
      activatedAt: '2026-11-05T10:00:00Z',
    },
    {
      id: 'b4',
      bookingNumber: 'BK-2026-0004',
      status: 'Completed',
      startDate: '2026-11-01T10:00:00Z',
      endDate: '2026-11-03T10:00:00Z',
      billableDays: 2,
      dailyRatePaise: 250000,
      baseAmountPaise: 500000,
      discountPaise: 0,
      totalAmountPaise: 500000,
      customerSnapshot: { name: 'Pooja Nair', phone: '+919554433221' },
      vehicleSnapshot: { name: 'Hyundai Creta', registration: 'KA 01 AB 1234' },
      createdAt: '2026-11-01T08:00:00Z',
      completedAt: '2026-11-03T10:00:00Z',
    },
    {
      id: 'b5',
      bookingNumber: 'BK-2026-0005',
      status: 'Cancelled',
      startDate: '2026-11-02T10:00:00Z',
      endDate: '2026-11-04T10:00:00Z',
      billableDays: 2,
      dailyRatePaise: 250000,
      baseAmountPaise: 500000,
      discountPaise: 0,
      totalAmountPaise: 500000,
      customerSnapshot: { name: 'Karan Mehra', phone: '+919443322110' },
      vehicleSnapshot: { name: 'Hyundai Creta', registration: 'KA 01 AB 1234' },
      createdAt: '2026-11-01T08:00:00Z',
      cancelledAt: '2026-11-01T09:00:00Z',
      cancelReason: 'Customer request',
    },
  ],
  meta: { total: 5, page: 1, limit: 20 },
}

describe('Bookings Page (Phase 3b Lifecycle & CRUD)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    bookingsApi.listBookings.mockResolvedValue(mockBookingsData)
  })

  it('renders booking items and meta successfully', async () => {
    renderBookings('owner')

    expect(screen.getByText('Loading bookings…')).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText('BK-2026-0001')).toBeInTheDocument()
      expect(screen.getByText('BK-2026-0002')).toBeInTheDocument()
      expect(screen.getByText('BK-2026-0003')).toBeInTheDocument()
      expect(screen.getByText('BK-2026-0004')).toBeInTheDocument()
      expect(screen.getByText('BK-2026-0005')).toBeInTheDocument()
    })

    expect(screen.getByText('Aarav Sharma')).toBeInTheDocument()
    expect(screen.getByText('Neha Patel')).toBeInTheDocument()
    expect(screen.getByText('Showing 5 of 5 bookings')).toBeInTheDocument()
  })

  it('shows Delete button only on Pending and Cancelled bookings for Owner and Manager', async () => {
    renderBookings('owner')

    await waitFor(() => {
      expect(screen.getByText('BK-2026-0001')).toBeInTheDocument()
    })

    // Delete buttons should exist for BK-2026-0001 (Pending) and BK-2026-0005 (Cancelled)
    const deletePending = screen.getByLabelText('Delete BK-2026-0001')
    const deleteCancelled = screen.getByLabelText('Delete BK-2026-0005')

    expect(deletePending).toBeInTheDocument()
    expect(deleteCancelled).toBeInTheDocument()

    // Completed (BK-2026-0004), Confirmed (BK-2026-0002), and Active (BK-2026-0003) MUST NOT have delete buttons
    expect(screen.queryByLabelText('Delete BK-2026-0002')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Delete BK-2026-0003')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Delete BK-2026-0004')).not.toBeInTheDocument()
  })

  it('hides all Delete buttons when user has Staff role', async () => {
    renderBookings('staff')

    await waitFor(() => {
      expect(screen.getByText('BK-2026-0001')).toBeInTheDocument()
    })

    expect(screen.queryByLabelText('Delete BK-2026-0001')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Delete BK-2026-0005')).not.toBeInTheDocument()
  })

  it('staff can cancel Pending, but CANNOT cancel Confirmed', async () => {
    renderBookings('staff')

    await waitFor(() => {
      expect(screen.getByText('BK-2026-0001')).toBeInTheDocument()
    })

    // Staff can see Confirm and Cancel for Pending
    expect(screen.getByRole('button', { name: 'Confirm' })).toBeInTheDocument()

    // Confirmed booking should have Activate, but staff cannot see Cancel for Confirmed
    expect(screen.getByRole('button', { name: 'Activate' })).toBeInTheDocument()
  })

  it('opens details modal when clicking on booking number', async () => {
    renderBookings('owner')

    await waitFor(() => {
      expect(screen.getByText('BK-2026-0001')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('BK-2026-0001'))

    await waitFor(() => {
      expect(screen.getByText('Booking BK-2026-0001')).toBeInTheDocument()
      expect(screen.getByText('Billable days')).toBeInTheDocument()
      expect(screen.getByText('Daily rate (snapshot)')).toBeInTheDocument()
    })
  })

  it('displays empty state when list is empty', async () => {
    bookingsApi.listBookings.mockResolvedValueOnce({ items: [], meta: { total: 0, page: 1, limit: 20 } })
    renderBookings('owner')

    await waitFor(() => {
      expect(screen.getByText('No bookings found')).toBeInTheDocument()
    })
  })

  it('displays error state with retry button on failure', async () => {
    bookingsApi.listBookings.mockRejectedValueOnce(new Error('Network error'))
    renderBookings('owner')

    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
    })
  })
})
