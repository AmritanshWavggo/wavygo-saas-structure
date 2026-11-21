import React, { useState, useEffect } from 'react'
import { X, Check, AlertCircle, RefreshCw } from 'lucide-react'
import { paymentService } from '../services/paymentService.js'

function currency(amount) {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(amount || 0)
}

export function RecordPaymentModal({ isOpen, onClose, booking, onSuccess }) {
  if (!isOpen || !booking) return null

  const totalAmount = Number(booking.total_amount || 0)
  const paidAmount = Number(booking.paid || 0)
  const outstandingAmount = booking.outstanding !== undefined
    ? Number(booking.outstanding)
    : Math.max(0, totalAmount - paidAmount)

  const [amount, setAmount] = useState('')
  const [method, setMethod] = useState('UPI')
  const [transactionReference, setTransactionReference] = useState('')
  const [paymentDate, setPaymentDate] = useState('')
  const [notes, setNotes] = useState('')
  const [idempotencyKey, setIdempotencyKey] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')

  // Initialize once per modal open
  useEffect(() => {
    if (isOpen) {
      setAmount(outstandingAmount > 0 ? String(outstandingAmount) : '')
      setMethod('UPI')
      setTransactionReference('')
      setNotes('')
      setError('')
      const today = new Date().toISOString().split('T')[0]
      setPaymentDate(today)
      const newKey = typeof crypto !== 'undefined' && crypto.randomUUID
        ? crypto.randomUUID()
        : `idemp-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`
      setIdempotencyKey(newKey)
    }
  }, [isOpen, booking.id])

  function handlePayFull() {
    setAmount(String(outstandingAmount))
    setError('')
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')

    const numAmount = Number(amount)
    if (isNaN(numAmount) || numAmount <= 0) {
      setError('Please enter a valid positive payment amount.')
      return
    }

    if (numAmount > outstandingAmount + 0.001) {
      setError(`Payment amount cannot exceed outstanding balance of ${currency(outstandingAmount)}.`)
      return
    }

    const trimmedRef = transactionReference.trim()
    if (method !== 'Cash' && !trimmedRef) {
      setError(`Transaction reference is required for ${method} payments.`)
      return
    }

    setIsSubmitting(true)
    try {
      const payload = {
        booking_id: booking.id,
        amount: numAmount,
        method,
        transaction_reference: trimmedRef || null,
        payment_date: paymentDate || undefined,
        notes: notes.trim() || null,
        idempotency_key: idempotencyKey,
      }

      await paymentService.recordPayment(payload)

      if (onSuccess) {
        await onSuccess()
      }
      onClose()
    } catch (err) {
      const errMsg = err?.response?.data?.detail || err?.message || 'Failed to record payment. Please try again.'
      setError(typeof errMsg === 'string' ? errMsg : JSON.stringify(errMsg))
      // Retain the same idempotencyKey so retrying the exact request replays safely
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-xs">
      <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl ring-1 ring-slate-900/10">
        <div className="flex items-center justify-between border-b border-slate-100 pb-4">
          <div>
            <h2 className="text-base font-semibold text-slate-900">Record Payment</h2>
            <p className="text-xs text-slate-500">Booking {booking.id} · {booking.customer}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 disabled:opacity-50"
            aria-label="Close modal"
          >
            <X size={18} />
          </button>
        </div>

        <div className="my-4 grid grid-cols-3 gap-3 rounded-xl bg-slate-50 p-3.5 text-center">
          <div>
            <span className="block text-[11px] font-medium text-slate-500 uppercase">Total</span>
            <span className="mt-0.5 block text-sm font-semibold text-slate-800">{currency(totalAmount)}</span>
          </div>
          <div>
            <span className="block text-[11px] font-medium text-slate-500 uppercase">Already Paid</span>
            <span className="mt-0.5 block text-sm font-semibold text-emerald-600">{currency(paidAmount)}</span>
          </div>
          <div>
            <span className="block text-[11px] font-medium text-slate-500 uppercase">Outstanding</span>
            <span className="mt-0.5 block text-sm font-semibold text-amber-600">{currency(outstandingAmount)}</span>
          </div>
        </div>

        {error && (
          <div className="mb-4 flex items-start gap-2.5 rounded-lg bg-rose-50 p-3 text-xs text-rose-700 ring-1 ring-rose-200">
            <AlertCircle size={16} className="mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <div className="flex items-center justify-between">
              <label htmlFor="payment-amount" className="block text-xs font-medium text-slate-700">
                Amount to Collect (₹) *
              </label>
              {outstandingAmount > 0 && (
                <button
                  type="button"
                  onClick={handlePayFull}
                  className="text-xs font-semibold text-emerald-700 hover:underline"
                >
                  Pay full ({currency(outstandingAmount)})
                </button>
              )}
            </div>
            <input
              id="payment-amount"
              type="number"
              step="0.01"
              min="0.01"
              max={outstandingAmount || undefined}
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              required
              disabled={isSubmitting}
              className="mt-1 block w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900 shadow-xs focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 disabled:bg-slate-50"
              placeholder="Enter amount"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="payment-method" className="block text-xs font-medium text-slate-700">
                Payment Method *
              </label>
              <select
                id="payment-method"
                value={method}
                onChange={(e) => setMethod(e.target.value)}
                disabled={isSubmitting}
                className="mt-1 block w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900 shadow-xs focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 disabled:bg-slate-50"
              >
                <option value="UPI">UPI / QR</option>
                <option value="Cash">Cash</option>
                <option value="Card">Card / POS</option>
                <option value="Net Banking">Net Banking</option>
                <option value="Bank Transfer">Bank Transfer</option>
              </select>
            </div>

            <div>
              <label htmlFor="payment-date" className="block text-xs font-medium text-slate-700">
                Payment Date *
              </label>
              <input
                id="payment-date"
                type="date"
                value={paymentDate}
                onChange={(e) => setPaymentDate(e.target.value)}
                disabled={isSubmitting}
                required
                className="mt-1 block w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900 shadow-xs focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 disabled:bg-slate-50"
              />
            </div>
          </div>

          <div>
            <label htmlFor="payment-ref" className="block text-xs font-medium text-slate-700">
              Transaction Reference {method !== 'Cash' ? '*' : '(Optional)'}
            </label>
            <input
              id="payment-ref"
              type="text"
              value={transactionReference}
              onChange={(e) => setTransactionReference(e.target.value)}
              placeholder={method === 'Cash' ? 'e.g. Receipt #104' : 'e.g. UPI Ref / UTR / Card last 4'}
              disabled={isSubmitting}
              required={method !== 'Cash'}
              className="mt-1 block w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900 shadow-xs focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 disabled:bg-slate-50"
            />
          </div>

          <div>
            <label htmlFor="payment-notes" className="block text-xs font-medium text-slate-700">
              Notes (Optional)
            </label>
            <input
              id="payment-notes"
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. Collected at front desk"
              disabled={isSubmitting}
              className="mt-1 block w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900 shadow-xs focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 disabled:bg-slate-50"
            />
          </div>

          <div className="flex items-center justify-end gap-2 border-t border-slate-100 pt-4">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || outstandingAmount <= 0}
              className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white shadow-xs hover:bg-emerald-700 focus:outline-hidden focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 disabled:opacity-50"
            >
              {isSubmitting ? (
                <>
                  <RefreshCw size={15} className="animate-spin" />
                  Recording...
                </>
              ) : (
                <>
                  <Check size={16} />
                  Record Payment
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default RecordPaymentModal
