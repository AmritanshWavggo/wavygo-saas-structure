// @vitest-environment jsdom
import React from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import BookingLifecycleDialog from './BookingLifecycleDialogs.jsx'
import { bookingService } from '../services/bookingService.js'

vi.mock('../services/bookingService.js', () => ({ bookingService: {
  handoverOfflineBooking: vi.fn(), returnOfflineBooking: vi.fn(), completeOfflineBooking: vi.fn(),
} }))

const booking = { id: 'BK-1', total_amount: 1000, paid: 250, outstanding: 750 }

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('BookingLifecycleDialog', () => {
  it('renders the state-specific dialog and completion balance warning', () => {
    render(<BookingLifecycleDialog action="complete" booking={booking} onClose={vi.fn()} onSuccess={vi.fn()} />)
    expect(screen.getByRole('heading', { name: /complete booking/i })).toBeInTheDocument()
    expect(screen.getByText(/balance due/i)).toBeInTheDocument()
  })

  it('rejects a future action time with the datetime maximum', async () => {
    render(<BookingLifecycleDialog action="handover" booking={booking} onClose={vi.fn()} onSuccess={vi.fn()} />)
    fireEvent.change(screen.getByLabelText(/action date and time/i), { target: { value: '2099-01-01T10:00' } })
    expect(screen.getByLabelText(/action date and time/i).validity.valid).toBe(false)
    fireEvent.click(screen.getByRole('button', { name: /confirm/i }))
    expect(bookingService.handoverOfflineBooking).not.toHaveBeenCalled()
  })

  it('shows backend errors and disables controls while submitting', async () => {
    let reject
    bookingService.returnOfflineBooking.mockReturnValueOnce(new Promise((_, fail) => { reject = fail }))
    render(<BookingLifecycleDialog action="return" booking={booking} onClose={vi.fn()} onSuccess={vi.fn()} />)
    fireEvent.change(screen.getByLabelText(/extra charge reason/i), { target: { value: 'Fuel' } })
    fireEvent.change(screen.getByLabelText(/manual extra charge/i), { target: { value: '20' } })
    fireEvent.click(screen.getByRole('button', { name: /confirm/i }))
    expect(screen.getByRole('button', { name: /saving/i })).toBeDisabled()
    reject(new Error('Booking is not Active'))
    expect(await screen.findByRole('alert')).toHaveTextContent(/not active/i)
  })

  it('submits handover and calls the success refresh callback', async () => {
    bookingService.handoverOfflineBooking.mockResolvedValueOnce({ ...booking, status: 'Active' })
    const success = vi.fn()
    render(<BookingLifecycleDialog action="handover" booking={booking} onClose={vi.fn()} onSuccess={success} />)
    fireEvent.click(screen.getByRole('button', { name: /confirm/i }))
    await waitFor(() => expect(bookingService.handoverOfflineBooking).toHaveBeenCalled())
    expect(success).toHaveBeenCalled()
  })

  it('shows the backend return bill until Done triggers sync and close', async () => {
    bookingService.returnOfflineBooking.mockResolvedValueOnce({
      ...booking,
      additionalCharges: [{ amount: 50, reason: 'Fuel', type: 'manual', createdAt: '2026-01-01T00:00:00Z' }],
      finalBill: { base: 1000, discount: 0, deposit: 0, additionalCharges: 50, finalTotal: 1050, paid: 250, outstanding: 800 },
    })
    const close = vi.fn()
    const success = vi.fn()
    render(<BookingLifecycleDialog action="return" booking={booking} onClose={close} onSuccess={success} />)
    fireEvent.click(screen.getByRole('button', { name: /confirm/i }))
    expect(await screen.findByRole('heading', { name: /return recorded/i })).toBeInTheDocument()
    expect(screen.getByText(/₹50.*fuel/i)).toBeInTheDocument()
    expect(screen.getByText(/final total: ₹1,050/i)).toBeInTheDocument()
    expect(success).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: /done/i }))
    await waitFor(() => expect(success).toHaveBeenCalled())
    expect(close).toHaveBeenCalled()
  })
})
