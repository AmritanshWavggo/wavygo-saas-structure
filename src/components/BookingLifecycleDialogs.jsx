import { useEffect, useState } from 'react'
import { AlertCircle, Check, KeyRound, RefreshCw, Smartphone, X } from 'lucide-react'
import { bookingService } from '../services/bookingService.js'

function localDateTimeNow() {
  const value = new Date()
  value.setMinutes(value.getMinutes() - value.getTimezoneOffset())
  return value.toISOString().slice(0, 16)
}

function currency(value) {
  return `₹${Number(value || 0).toLocaleString('en-IN')}`
}

function errorMessage(error) {
  return error?.response?.data?.detail || error?.data?.detail || error?.message || 'Unable to update this booking.'
}

export function BookingLifecycleDialog({ action, booking, onClose, onSuccess }) {
  const [occurredAt, setOccurredAt] = useState(localDateTimeNow())
  const [notes, setNotes] = useState('')
  const [extraCharges, setExtraCharges] = useState('0')
  const [extraChargeReason, setExtraChargeReason] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [returnResult, setReturnResult] = useState(null)

  // Return OTP states
  const [returnOtp, setReturnOtp] = useState('')
  const [otpSent, setOtpSent] = useState(false)
  const [otpSending, setOtpSending] = useState(false)
  const [otpVerifying, setOtpVerifying] = useState(false)
  const [otpVerified, setOtpVerified] = useState(false)
  const [otpBypassed, setOtpBypassed] = useState(false)
  const [otpMsg, setOtpMsg] = useState({ type: '', text: '' })

  useEffect(() => {
    if (action) {
      setOccurredAt(localDateTimeNow())
      setNotes('')
      setExtraCharges('0')
      setExtraChargeReason('')
      setError('')
      setReturnResult(null)
      setReturnOtp('')
      setOtpSent(false)
      setOtpSending(false)
      setOtpVerifying(false)
      setOtpVerified(false)
      setOtpBypassed(false)
      setOtpMsg({ type: '', text: '' })
    }
  }, [action, booking?.id])

  if (!action || !booking) return null

  const isReturn = action === 'return'
  const isComplete = action === 'complete'
  const title = action === 'handover' ? 'Mark as Rented / Handover' : isReturn ? 'Mark as Returned' : 'Complete Booking'
  const maxDateTime = localDateTimeNow()
  const amount = Number(extraCharges || 0)
  const existingBill = booking.finalBill

  const phone = booking.phone || booking.customer_details?.phone || booking.customerPhone || ''
  const customerName = booking.customer || booking.customer_details?.name || 'Customer'
  const vehicleName = booking.vehicle || booking.vehicle_details?.name || ''

  async function handleSendOtp() {
    if (!phone) {
      setOtpMsg({ type: 'error', text: 'No phone number linked to this booking.' })
      return
    }
    setOtpSending(true)
    setOtpMsg({ type: '', text: '' })
    try {
      await bookingService.sendBookingOtp?.({
        phone,
        purpose: 'return',
        booking_id: booking.id,
        customer_name: customerName,
        vehicle_name: vehicleName,
      })
      setOtpSent(true)
      setOtpMsg({ type: 'success', text: `Return OTP sent to ${phone} via SMS.` })
    } catch (err) {
      setOtpMsg({ type: 'error', text: err?.message || 'Failed to send return OTP.' })
    } finally {
      setOtpSending(false)
    }
  }

  async function handleVerifyOtp(codeToVerify) {
    const code = (codeToVerify !== undefined ? codeToVerify : returnOtp).trim()
    if (!code || code.length < 4) {
      setOtpMsg({ type: 'error', text: 'Please enter the 6-digit OTP code.' })
      return false
    }
    setOtpVerifying(true)
    setOtpMsg({ type: '', text: '' })
    try {
      await bookingService.verifyBookingOtp?.({
        phone,
        purpose: 'return',
        otp: code,
        booking_id: booking.id,
      })
      setOtpVerified(true)
      setOtpMsg({ type: 'success', text: 'Return OTP verified successfully! ✓' })
      return true
    } catch (err) {
      setOtpMsg({ type: 'error', text: err?.message || 'Invalid or expired OTP code.' })
      return false
    } finally {
      setOtpVerifying(false)
    }
  }

  function handleOtpChange(e) {
    const cleaned = e.target.value.replace(/\D/g, '')
    setReturnOtp(cleaned)
    if (cleaned.length === 6 && !otpVerifying && !otpVerified) {
      handleVerifyOtp(cleaned)
    }
  }

  async function doneWithReturn() {
    await onSuccess?.(returnResult)
    onClose()
  }

  async function submit(event) {
    event.preventDefault()
    setError('')
    const timestamp = new Date(occurredAt)
    if (!occurredAt || Number.isNaN(timestamp.getTime()) || timestamp.getTime() > Date.now() + 5 * 60_000) {
      setError('The action date and time cannot be in the future.')
      return
    }
    if (isReturn && (amount < 0 || (amount > 0 && !extraChargeReason.trim()))) {
      setError(amount < 0 ? 'Extra charges cannot be negative.' : 'A reason is required for manual extra charges.')
      return
    }
    if (isReturn && phone && !otpVerified && !otpBypassed) {
      if (returnOtp.length === 6) {
        const verified = await handleVerifyOtp(returnOtp)
        if (!verified) {
          setError('Return OTP verification failed. Please enter the correct OTP or skip OTP if customer is offline.')
          return
        }
      } else {
        setError('Please verify the Return OTP sent to customer mobile, or skip OTP verification if phone is unreachable.')
        return
      }
    }
    setSubmitting(true)
    try {
      let updated
      if (action === 'handover') updated = await bookingService.handoverOfflineBooking(booking.id, { occurredAt: timestamp.toISOString(), notes: notes.trim() || undefined })
      if (action === 'return') updated = await bookingService.returnOfflineBooking(booking.id, { occurredAt: timestamp.toISOString(), notes: notes.trim() || undefined, extraCharges: amount, extraChargeReason: extraChargeReason.trim() || undefined })
      if (action === 'complete') updated = await bookingService.completeOfflineBooking(booking.id, { occurredAt: timestamp.toISOString(), notes: notes.trim() || undefined })
      if (action === 'return') {
        setReturnResult(updated)
        return
      }
      await onSuccess?.(updated)
      onClose()
    } catch (requestError) {
      setError(errorMessage(requestError))
    } finally {
      setSubmitting(false)
    }
  }

  if (returnResult) {
    const finalBill = returnResult.finalBill || {}
    const charges = returnResult.additionalCharges || []
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-xs" role="dialog" aria-modal="true" aria-label="Return final bill">
        <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl">
          <h2 className="text-base font-semibold text-slate-900">Return recorded</h2>
          <p className="mt-1 text-xs text-slate-500">Final bill for booking {booking.id}</p>
          <div className="mt-4 grid grid-cols-2 gap-2 rounded-lg bg-slate-50 p-3 text-xs text-slate-700">
            <span>Base: {currency(finalBill.base)}</span><span>Discount: {currency(finalBill.discount)}</span>
            <span>Deposit: {currency(finalBill.deposit)}</span><span>Additional: {currency(finalBill.additionalCharges)}</span>
            <span>Final total: {currency(finalBill.finalTotal)}</span><span>Paid: {currency(finalBill.paid)}</span>
            <span className="col-span-2 font-semibold text-amber-700">Outstanding: {currency(finalBill.outstanding)}</span>
          </div>
          <div className="mt-4 space-y-2 text-xs text-slate-700"><span className="font-medium">Additional charge line items</span>{charges.length ? charges.map((charge, index) => <div key={`${charge.createdAt || index}-${charge.reason || ''}`} className="rounded-md border border-slate-100 p-2">{currency(charge.amount)} · {charge.reason} ({charge.type})</div>) : <span>No additional charges.</span>}</div>
          <div className="mt-5 flex justify-end border-t border-slate-100 pt-4"><button type="button" onClick={doneWithReturn} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white">Done</button></div>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-xs" role="dialog" aria-modal="true" aria-label={title}>
      <form onSubmit={submit} className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-100 pb-4">
          <div><h2 className="text-base font-semibold text-slate-900">{title}</h2><p className="text-xs text-slate-500">Booking {booking.id}</p></div>
          <button type="button" onClick={onClose} disabled={submitting} aria-label="Close" className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100"><X size={18} /></button>
        </div>
        {error && <div role="alert" className="mt-4 flex gap-2 rounded-lg bg-rose-50 p-3 text-xs text-rose-700"><AlertCircle size={16} />{error}</div>}
        {isComplete && Number(booking.outstanding ?? Math.max(0, Number(booking.total_amount || 0) - Number(booking.paid || 0))) > 0 && <p className="mt-4 rounded-lg bg-amber-50 p-3 text-xs text-amber-800">This booking still has a balance due. Completing it will not remove the balance; it can be collected later.</p>}
        <div className="mt-4 grid grid-cols-2 gap-3">
          <label className="text-xs font-medium text-slate-700">Date and time<input aria-label="Action date and time" type="datetime-local" max={maxDateTime} value={occurredAt} onChange={(event) => setOccurredAt(event.target.value)} disabled={submitting} className="mt-1 block w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" /></label>
          <label className="text-xs font-medium text-slate-700">Notes<textarea aria-label="Notes" value={notes} onChange={(event) => setNotes(event.target.value)} disabled={submitting} className="mt-1 block w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" /></label>
        </div>
        {isReturn && <>
          {/* OTP Verification Card for Return */}
          <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50/50 p-3.5 text-xs text-slate-700">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Smartphone size={16} className="text-amber-700 shrink-0" />
                <div>
                  <span className="font-semibold text-slate-900">Return Confirmation Mobile OTP</span>
                  {phone ? (
                    <p className="text-[11px] text-slate-500 mt-0.5">
                      Customer Phone: <span className="font-semibold text-slate-800">{phone}</span>
                    </p>
                  ) : (
                    <p className="text-[11px] text-slate-400 mt-0.5">No phone number attached to this booking.</p>
                  )}
                </div>
              </div>
              {phone && (
                otpVerified ? (
                  <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-1 text-[11px] font-semibold text-emerald-800">
                    <Check size={12} /> Verified ✓
                  </span>
                ) : otpBypassed ? (
                  <span className="inline-flex items-center gap-1 rounded-full bg-slate-200 px-2.5 py-1 text-[11px] font-medium text-slate-700">
                    Skipped (Offline)
                  </span>
                ) : (
                  <button
                    type="button"
                    onClick={handleSendOtp}
                    disabled={otpSending || submitting}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-amber-300 bg-white px-2.5 py-1 text-xs font-semibold text-amber-900 shadow-xs hover:bg-amber-100 disabled:opacity-50"
                  >
                    {otpSending ? <RefreshCw size={12} className="animate-spin" /> : <KeyRound size={12} />}
                    {otpSent ? 'Resend OTP' : 'Send Return OTP'}
                  </button>
                )
              )}
            </div>

            {phone && !otpVerified && !otpBypassed && (
              <div className="mt-2.5 flex items-center justify-between border-t border-amber-200/60 pt-2 text-[11px]">
                <span>Bike return confirm karne ke liye customer ke phone par OTP bhejein.</span>
                <button
                  type="button"
                  onClick={() => { setOtpBypassed(true); setOtpMsg({ type: '', text: '' }) }}
                  className="text-slate-500 underline hover:text-slate-800 cursor-pointer"
                >
                  Skip OTP (Customer offline)
                </button>
              </div>
            )}

            {otpMsg.text && (
              <div className={`mt-2 flex items-center gap-1.5 text-xs font-medium ${otpMsg.type === 'error' ? 'text-rose-700' : 'text-emerald-800'}`}>
                {otpMsg.type === 'error' ? <AlertCircle size={14} /> : <Check size={14} />}
                {otpMsg.text}
              </div>
            )}

            {phone && otpSent && !otpVerified && !otpBypassed && (
              <div className="mt-3 flex items-center gap-2">
                <input
                  type="text"
                  placeholder="6-digit OTP"
                  maxLength={6}
                  value={returnOtp}
                  onChange={handleOtpChange}
                  disabled={otpVerifying || submitting}
                  className="h-9 w-36 rounded-lg border border-slate-300 bg-white px-3 text-center font-mono text-sm tracking-widest outline-none focus:border-amber-600 focus:ring-2 focus:ring-amber-100"
                />
                <button
                  type="button"
                  onClick={() => handleVerifyOtp()}
                  disabled={otpVerifying || returnOtp.length < 4 || submitting}
                  className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-amber-600 px-3.5 text-xs font-semibold text-white shadow-xs hover:bg-amber-700 disabled:opacity-50"
                >
                  {otpVerifying ? <RefreshCw size={13} className="animate-spin" /> : 'Verify Code'}
                </button>
              </div>
            )}
          </div>

          <p className="mt-4 text-xs text-slate-500">Late charges are calculated by the backend using the booked return time.</p>
          <div className="mt-3 grid grid-cols-2 gap-3"><label className="text-xs font-medium text-slate-700">Manual extra charge<input aria-label="Manual extra charge" type="number" min="0" step="0.01" value={extraCharges} onChange={(event) => setExtraCharges(event.target.value)} disabled={submitting} className="mt-1 block w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" /></label><label className="text-xs font-medium text-slate-700">Reason<input aria-label="Extra charge reason" value={extraChargeReason} onChange={(event) => setExtraChargeReason(event.target.value)} disabled={submitting} className="mt-1 block w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" /></label></div>
          {existingBill && <div className="mt-4 grid grid-cols-2 gap-2 rounded-lg bg-slate-50 p-3 text-xs text-slate-600"><span>Base: {currency(existingBill.base)}</span><span>Discount: {currency(existingBill.discount)}</span><span>Deposit: {currency(existingBill.deposit)}</span><span>Additional: {currency(existingBill.additionalCharges)}</span><span>Final: {currency(existingBill.finalTotal)}</span><span>Outstanding: {currency(existingBill.outstanding)}</span></div>}
        </>}
        <div className="mt-5 flex justify-end gap-2 border-t border-slate-100 pt-4"><button type="button" onClick={onClose} disabled={submitting} className="rounded-lg border border-slate-200 px-4 py-2 text-sm">Cancel</button><button type="submit" disabled={submitting} className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{submitting ? <><RefreshCw size={15} className="animate-spin" />Saving...</> : <><Check size={16} />Confirm</>}</button></div>
      </form>
    </div>
  )
}

export default BookingLifecycleDialog
