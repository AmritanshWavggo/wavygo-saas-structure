import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Customers, { CustomerFormModal } from './Customers.jsx'
import { customersApi } from '../../services/customersApi.js'
import * as AuthModule from '../../providers/AuthProvider.jsx'

vi.mock('../../services/customersApi.js', () => ({
  customersApi: {
    listCustomers: vi.fn(),
    getCustomerMetrics: vi.fn(),
    getCustomer: vi.fn(),
    createCustomer: vi.fn(),
    updateCustomer: vi.fn(),
    deleteCustomer: vi.fn(),
  },
}))

function createTestWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  })
  return ({ children }) => (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  )
}

describe('Customers screen & CustomerFormModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('CustomerFormModal error mapping', () => {
    it('maps 409 CONFLICT error to the phone field', async () => {
      vi.mocked(customersApi.createCustomer).mockRejectedValue({
        status: 409,
        code: 'CONFLICT',
        message: 'A customer with this phone number already exists in your fleet.',
      })

      const onClose = vi.fn()
      render(
        <CustomerFormModal
          isOpen={true}
          onClose={onClose}
          isStaff={false}
        />,
        { wrapper: createTestWrapper() }
      )

      fireEvent.change(screen.getByPlaceholderText('e.g. Aarav Mehta'), {
        target: { value: 'Aarav Mehta' },
      })
      fireEvent.change(screen.getByPlaceholderText('e.g. 9876543210 or +919876543210'), {
        target: { value: '+919876543210' },
      })

      fireEvent.click(screen.getByText('Save customer'))

      await waitFor(() => {
        expect(
          screen.getByText('A customer with this phone number already exists in your fleet.')
        ).toBeInTheDocument()
      })
    })

    it('maps 422 VALIDATION_ERROR field details to corresponding inputs', async () => {
      vi.mocked(customersApi.createCustomer).mockRejectedValue({
        status: 422,
        code: 'VALIDATION_ERROR',
        message: 'Validation failed.',
        details: [
          { field: 'phone', message: '10-digit Indian phone numbers must start with 6, 7, 8, or 9.' },
          { field: 'email', message: 'Enter a valid email address.' },
        ],
      })

      const onClose = vi.fn()
      render(
        <CustomerFormModal
          isOpen={true}
          onClose={onClose}
          isStaff={false}
        />,
        { wrapper: createTestWrapper() }
      )

      fireEvent.change(screen.getByPlaceholderText('e.g. Aarav Mehta'), {
        target: { value: 'Aarav Mehta' },
      })
      fireEvent.change(screen.getByPlaceholderText('e.g. 9876543210 or +919876543210'), {
        target: { value: '5123456789' },
      })
      fireEvent.change(screen.getByPlaceholderText('e.g. aarav@example.com'), {
        target: { value: 'bad-email' },
      })

      fireEvent.click(screen.getByText('Save customer'))

      await waitFor(() => {
        expect(
          screen.getByText('10-digit Indian phone numbers must start with 6, 7, 8, or 9.')
        ).toBeInTheDocument()
        expect(screen.getByText('Enter a valid email address.')).toBeInTheDocument()
      })
    })

    it('locks status to Review for staff users', () => {
      render(
        <CustomerFormModal
          isOpen={true}
          onClose={vi.fn()}
          isStaff={true}
        />,
        { wrapper: createTestWrapper() }
      )

      expect(screen.getByText(/Staff-created customers are automatically set to Review/)).toBeInTheDocument()
      expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
    })
  })

  describe('Customers screen role-based actions & empty states', () => {
    it('renders customer list and hides delete action from staff', async () => {
      vi.spyOn(AuthModule, 'useAuth').mockReturnValue({
        user: { id: 'u_staff', email: 'staff@example.com', role: 'staff' },
      })

      vi.mocked(customersApi.listCustomers).mockResolvedValue({
        items: [
          {
            id: '6727289faabbcc1122334455',
            name: 'Isha Patel',
            phone: '+919765432109',
            email: 'isha@test.com',
            status: 'Verified',
            createdAt: '2026-11-03T10:00:00Z',
          },
        ],
        meta: { total: 1, page: 1, limit: 10 },
      })
      vi.mocked(customersApi.getCustomerMetrics).mockResolvedValue({
        totalCustomers: 1,
        verifiedProfiles: 1,
        totalCollected: null,
        pendingDues: null,
      })

      render(<Customers />, { wrapper: createTestWrapper() })

      await waitFor(() => {
        expect(screen.getByText('Isha Patel')).toBeInTheDocument()
        expect(screen.getByText('+919765432109')).toBeInTheDocument()
      })

      // Staff can View and Edit
      expect(screen.getByRole('button', { name: /View Isha Patel/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Edit Isha Patel/i })).toBeInTheDocument()

      // Staff CANNOT see Delete button
      expect(screen.queryByRole('button', { name: /Delete Isha Patel/i })).not.toBeInTheDocument()
    })

    it('renders delete action for owner and displays delete confirmation', async () => {
      vi.spyOn(AuthModule, 'useAuth').mockReturnValue({
        user: { id: 'u_owner', email: 'owner@example.com', role: 'owner' },
      })

      vi.mocked(customersApi.listCustomers).mockResolvedValue({
        items: [
          {
            id: '6727289faabbcc1122334455',
            name: 'Aarav Mehta',
            phone: '+919876543210',
            email: 'aarav@test.com',
            status: 'Review',
            createdAt: '2026-11-03T10:00:00Z',
          },
        ],
        meta: { total: 1, page: 1, limit: 10 },
      })
      vi.mocked(customersApi.getCustomerMetrics).mockResolvedValue({
        totalCustomers: 1,
        verifiedProfiles: 0,
        totalCollected: null,
        pendingDues: null,
      })

      render(<Customers />, { wrapper: createTestWrapper() })

      await waitFor(() => {
        expect(screen.getByText('Aarav Mehta')).toBeInTheDocument()
      })

      // Owner can see Delete button
      const deleteBtn = screen.getByRole('button', { name: /Delete Aarav Mehta/i })
      expect(deleteBtn).toBeInTheDocument()

      fireEvent.click(deleteBtn)

      // Confirm modal opens
      expect(screen.getByText(/Are you sure you want to remove/)).toBeInTheDocument()
    })
  })
})

