// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import '@testing-library/jest-dom/vitest'
import React from 'react'
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import RecordPaymentModal from './RecordPaymentModal.jsx'
import { paymentService } from '../services/paymentService.js'

vi.mock('../services/paymentService.js', () => ({
  paymentService: {
    recordPayment: vi.fn(),
  },
}))

describe('RecordPaymentModal Component', () => {
  const mockBooking = {
    id: 'BK-123456',
    customer: 'Aarav Mehta',
    total_amount: 5000,
    paid: 2000,
    outstanding: 3000,
    payment_status: 'Partially Paid',
  }

  const mockOnClose = vi.fn()
  const mockOnSuccess = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    cleanup()
  })

  it('renders modal with total, already paid, and outstanding amounts', () => {
    render(
      <RecordPaymentModal
        isOpen={true}
        onClose={mockOnClose}
        booking={mockBooking}
        onSuccess={mockOnSuccess}
      />
    )

    expect(screen.getByRole('heading', { name: /Record Payment/i })).toBeInTheDocument()
    expect(screen.getByText(/Booking BK-123456 · Aarav Mehta/i)).toBeInTheDocument()
    expect(screen.getByText('₹5,000')).toBeInTheDocument()
    expect(screen.getByText('₹2,000')).toBeInTheDocument()
    expect(screen.getAllByText(/₹3,000/i).length).toBeGreaterThanOrEqual(1)
  })

  it('prefills amount with outstanding and provides Pay full button', () => {
    render(
      <RecordPaymentModal
        isOpen={true}
        onClose={mockOnClose}
        booking={mockBooking}
        onSuccess={mockOnSuccess}
      />
    )

    const amountInput = screen.getByLabelText(/Amount to Collect/i)
    expect(amountInput.value).toBe('3000')

    // Change amount
    fireEvent.change(amountInput, { target: { value: '1500' } })
    expect(amountInput.value).toBe('1500')

    // Click Pay full button
    const payFullBtn = screen.getByRole('button', { name: /Pay full/i })
    fireEvent.click(payFullBtn)
    expect(amountInput.value).toBe('3000')
  })

  it('requires transaction reference for non-Cash payment methods', async () => {
    const { container } = render(
      <RecordPaymentModal
        isOpen={true}
        onClose={mockOnClose}
        booking={mockBooking}
        onSuccess={mockOnSuccess}
      />
    )

    const methodSelect = screen.getByLabelText(/Payment Method/i)
    fireEvent.change(methodSelect, { target: { value: 'UPI' } })

    const form = container.querySelector('form')
    fireEvent.submit(form)

    await waitFor(() => {
      expect(screen.getByText(/Transaction reference is required for UPI payments/i)).toBeInTheDocument()
    })
    expect(paymentService.recordPayment).not.toHaveBeenCalled()
  })

  it('allows Cash payment without transaction reference and submits payload', async () => {
    paymentService.recordPayment.mockResolvedValueOnce({ id: 'TX-9999', status: 'Paid' })

    const { container } = render(
      <RecordPaymentModal
        isOpen={true}
        onClose={mockOnClose}
        booking={mockBooking}
        onSuccess={mockOnSuccess}
      />
    )

    const methodSelect = screen.getByLabelText(/Payment Method/i)
    fireEvent.change(methodSelect, { target: { value: 'Cash' } })

    const form = container.querySelector('form')
    fireEvent.submit(form)

    await waitFor(() => {
      expect(paymentService.recordPayment).toHaveBeenCalledTimes(1)
      const callArgs = paymentService.recordPayment.mock.calls[0][0]
      expect(callArgs.booking_id).toBe('BK-123456')
      expect(callArgs.amount).toBe(3000)
      expect(callArgs.method).toBe('Cash')
      expect(callArgs.idempotency_key).toBeDefined()
    })
  })

  it('surfaces backend error messages and reuses idempotency key on retry', async () => {
    paymentService.recordPayment.mockRejectedValueOnce({
      response: { data: { detail: 'Payment amount exceeds outstanding balance.' } },
    })

    const { container } = render(
      <RecordPaymentModal
        isOpen={true}
        onClose={mockOnClose}
        booking={mockBooking}
        onSuccess={mockOnSuccess}
      />
    )

    const methodSelect = screen.getByLabelText(/Payment Method/i)
    fireEvent.change(methodSelect, { target: { value: 'Cash' } })

    const form = container.querySelector('form')
    fireEvent.submit(form)

    await waitFor(() => {
      expect(screen.getByText(/Payment amount exceeds outstanding balance/i)).toBeInTheDocument()
    })

    const firstKey = paymentService.recordPayment.mock.calls[0][0].idempotency_key
    expect(firstKey).toBeTruthy()

    // Retry submit
    paymentService.recordPayment.mockResolvedValueOnce({ id: 'TX-9999', status: 'Paid' })
    fireEvent.submit(form)

    await waitFor(() => {
      expect(paymentService.recordPayment).toHaveBeenCalledTimes(2)
      const secondKey = paymentService.recordPayment.mock.calls[1][0].idempotency_key
      expect(secondKey).toBe(firstKey) // Key must be reused on retry!
    })
  })
})
