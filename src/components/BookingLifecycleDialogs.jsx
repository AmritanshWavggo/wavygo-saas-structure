import { useEffect, useState } from 'react'
import { AlertCircle, Check, Clock, CreditCard, KeyRound, RefreshCw, Smartphone, X } from 'lucide-react'
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

  // Post-return payment collection states
  const [collectAmount, setCollectAmount] = useState('')
  const [collectMethod, setCollectMethod] = useState('UPI')
  const [collectRef, setCollectRef] = useState('')
  const [collectingPayment, setCollectingPayment] = useState(false)
  const [paymentSuccessMsg, setPaymentSuccessMsg] = useState('')
  const [paymentError, setPaymentError] = useState('')

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
      setCollectAmount('')
      setCollectMethod('UPI')
      setCollectRef('')
      setCollectingPayment(false)
      setPaymentSuccessMsg('')
      setPaymentError('')
    }
  }, [action, booking?.id])

  if (!action || !booking) return null

  const isReturn = action === 'return'
  const isComplete = action === 'complete'
  const title = action === 'handover' ? 'Mark as Rented / Handover' : isReturn ? 'Mark as Returned' : 'Complete Booking'
  const maxDateTime = localDateTimeNow()
  const amount = Number(extraCharges || 0)
  const existingBill = booking.finalBill

  const bookingId = booking.id || booking._id || ''
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
        booking_id: bookingId,
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

  async function handleCollectPayment(e) {
    e?.preventDefault()
    setPaymentError('')
    setPaymentSuccessMsg('')
    const num = Number(collectAmount)
    if (isNaN(num) || num <= 0) {
      setPaymentError('Please enter a valid positive amount.')
      return
    }
    if (collectMethod === 'UPI' && !collectRef.trim()) {
      setPaymentError('UPI reference / UTR transaction ID is required.')
      return
    }
    setCollectingPayment(true)
    try {
      await bookingService.recordPayment(bookingId, {
        amount: num,
        method: collectMethod,
        transaction_reference: collectRef.trim() || undefined,
      })
      const oldPaid = Number(returnResult.finalBill?.paid || 0)
      const oldTotal = Number(returnResult.finalBill?.finalTotal || returnResult.total_amount || 0)
      const newPaid = oldPaid + num
      const newOutstanding = Math.max(0, oldTotal - newPaid)

      setReturnResult({
        ...returnResult,
        paid: newPaid,
        pending: newOutstanding,
        finalBill: {
          ...returnResult.finalBill,
          paid: newPaid,
          outstanding: newOutstanding,
        },
      })
      setCollectAmount(newOutstanding > 0 ? String(newOutstanding) : '')
      setPaymentSuccessMsg(`Payment of ${currency(num)} recorded! Outstanding balance updated. ✓`)
    } catch (err) {
      setPaymentError(errorMessage(err))
    } finally {
      setCollectingPayment(false)
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
      if (action === 'handover') updated = await bookingService.handoverOfflineBooking(bookingId, { occurredAt: timestamp.toISOString(), notes: notes.trim() || undefined })
      if (action === 'return') updated = await bookingService.returnOfflineBooking(bookingId, { occurredAt: timestamp.toISOString(), notes: notes.trim() || undefined, extraCharges: amount, extraChargeReason: extraChargeReason.trim() || undefined })
      if (action === 'complete') updated = await bookingService.completeOfflineBooking(bookingId, { occurredAt: timestamp.toISOString(), notes: notes.trim() || undefined })
      if (action === 'return') {
        setReturnResult(updated)
        const initialOut = Number(updated.finalBill?.outstanding || 0)
        setCollectAmount(initialOut > 0 ? String(initialOut) : '')
        setCollectMethod('UPI')
        setCollectRef('')
        setPaymentSuccessMsg('')
        setPaymentError('')
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
    const lateCharge = charges.find((c) => c.type === 'late')
    const hasLate = !!lateCharge
    const outstanding = Number(finalBill.outstanding || 0)

    const allottedDate = booking.rental_details?.end_date || booking.dates || 'N/A'
    const allottedTime = booking.rental_details?.return_time || '10:00'
    const actualReturnedAt = returnResult.returnedAt
      ? new Date(returnResult.returnedAt).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })
      : 'Just now'

    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-xs" role="dialog" aria-modal="true" aria-label="Return final bill">
        <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl max-h-[90vh] overflow-y-auto">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div>
              <h2 className="text-base font-semibold text-slate-900">
                {hasLate ? '⏰ Extra Time Return · Bill Calculated' : 'Ride Return Recorded'}
              </h2>
              <p className="text-xs text-slate-500">Booking {booking.id} · Customer: {customerName}</p>
            </div>
            <button type="button" onClick={doneWithReturn} className="rounded-lg p-1 text-slate-400 hover:bg-slate-100"><X size={18} /></button>
          </div>

          {/* Extra Time / Late Return Alert Banner */}
          {hasLate ? (
            <div className="mt-4 rounded-xl border border-amber-300 bg-amber-50 p-3.5 text-xs text-amber-950 space-y-2">
              <div className="flex items-center gap-2 font-bold text-amber-900 text-sm">
                <Clock size={17} className="text-amber-700 shrink-0" />
                <span>Ride Exceeded Allotted Time (Late Return)</span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs bg-white/70 p-2.5 rounded-lg border border-amber-200">
                <div>
                  <span className="text-slate-500 block text-[11px]">Allotted Return Time:</span>
                  <span className="font-semibold text-slate-800">{allottedDate} · {allottedTime}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[11px]">Actual Return Time:</span>
                  <span className="font-semibold text-slate-800">{actualReturnedAt}</span>
                </div>
              </div>
              <div className="flex items-center justify-between font-semibold text-xs pt-1 border-t border-amber-200/80">
                <span className="text-amber-900">Extra Time Charge Calculated:</span>
                <span className="text-sm font-bold text-rose-700">{currency(lateCharge.amount)}</span>
              </div>
            </div>
          ) : (
            <div className="mt-4 flex items-center gap-2 rounded-xl bg-emerald-50 border border-emerald-200 p-3 text-xs text-emerald-800 font-medium">
              <Check size={16} className="text-emerald-600 shrink-0" />
              <span>Bike returned successfully. OTP verification verified and vehicle moved to Under Review.</span>
            </div>
          )}

          {/* Breakdown summary */}
          <div className="mt-4 grid grid-cols-2 gap-2 rounded-xl bg-slate-50 p-3.5 text-xs text-slate-700 border border-slate-100">
            <span>Base Rental: {currency(finalBill.base)}</span>
            <span>Discount: {currency(finalBill.discount)}</span>
            <span>Security Deposit: {currency(finalBill.deposit)}</span>
            <span>Extra Charges (Late/Damage): <strong className="text-rose-600">{currency(finalBill.additionalCharges)}</strong></span>
            <span>Final Total: <strong>{currency(finalBill.finalTotal)}</strong></span>
            <span>Total Paid: <strong className="text-emerald-700">{currency(finalBill.paid)}</strong></span>
            <div className="col-span-2 pt-2 border-t border-slate-200 flex items-center justify-between">
              <span className="font-bold text-sm text-slate-900">Total Outstanding Due:</span>
              <span className={`text-base font-extrabold ${outstanding > 0 ? 'text-rose-600' : 'text-emerald-700'}`}>
                {currency(outstanding)}
              </span>
            </div>
          </div>

          {/* Charges list if multiple */}
          {charges.length > 0 && (
            <div className="mt-3 space-y-1.5 text-xs">
              <span className="font-medium text-slate-600">Charge Details:</span>
              {charges.map((charge, index) => (
                <div key={index} className="flex items-center justify-between rounded-lg border border-slate-100 bg-white px-3 py-1.5 text-slate-700">
                  <span>{charge.reason || 'Extra Charge'} ({charge.type})</span>
                  <span className="font-semibold text-rose-600">+{currency(charge.amount)}</span>
                </div>
              ))}
            </div>
          )}

          {/* Immediate Payment Collection if Outstanding > 0 */}
          {outstanding > 0 ? (
            <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50/70 p-3.5">
              <div className="flex items-center gap-1.5 text-xs font-bold text-slate-800 mb-2">
                <CreditCard size={15} className="text-emerald-700" />
                <span>Collect Remaining Amount from Customer Now</span>
              </div>

              {paymentError && (
                <div className="mb-2 flex items-center gap-1.5 rounded-lg bg-rose-50 p-2 text-xs text-rose-700">
                  <AlertCircle size={14} />{paymentError}
                </div>
              )}
              {paymentSuccessMsg && (
                <div className="mb-2 flex items-center gap-1.5 rounded-lg bg-emerald-50 p-2 text-xs text-emerald-800 font-semibold">
                  <Check size={14} />{paymentSuccessMsg}
                </div>
              )}

              <form onSubmit={handleCollectPayment} className="space-y-2.5">
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-600 mb-1">Amount to Collect (₹)</label>
                    <input
                      type="number"
                      min="1"
                      max={outstanding}
                      value={collectAmount}
                      onChange={(e) => setCollectAmount(e.target.value)}
                      disabled={collectingPayment}
                      className="h-9 w-full rounded-lg border border-slate-300 bg-white px-3 text-xs font-semibold text-slate-800 outline-none focus:border-emerald-600"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-600 mb-1">Payment Method</label>
                    <select
                      value={collectMethod}
                      onChange={(e) => setCollectMethod(e.target.value)}
                      disabled={collectingPayment}
                      className="h-9 w-full rounded-lg border border-slate-300 bg-white px-2.5 text-xs font-medium text-slate-800 outline-none focus:border-emerald-600"
                    >
                      <option value="UPI">UPI</option>
                      <option value="Cash">Cash</option>
                    </select>
                  </div>
                </div>

                {collectMethod === 'UPI' && (
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-600 mb-1">UPI Reference / UTR Number</label>
                    <input
                      type="text"
                      placeholder="e.g. 432109876543"
                      value={collectRef}
                      onChange={(e) => setCollectRef(e.target.value)}
                      disabled={collectingPayment}
                      className="h-9 w-full rounded-lg border border-slate-300 bg-white px-3 text-xs text-slate-800 outline-none focus:border-emerald-600"
                    />
                  </div>
                )}

                <button
                  type="submit"
                  disabled={collectingPayment || !Number(collectAmount)}
                  className="w-full inline-flex h-9 items-center justify-center gap-2 rounded-lg bg-emerald-700 px-4 text-xs font-bold text-white shadow-xs hover:bg-emerald-800 disabled:opacity-50 transition cursor-pointer"
                >
                  {collectingPayment ? <RefreshCw size={14} className="animate-spin" /> : <Check size={14} />}
                  <span>Collect {currency(collectAmount || outstanding)} & Settle Balance</span>
                </button>
              </form>
            </div>
          ) : (
            <div className="mt-3 flex items-center gap-1.5 rounded-lg bg-emerald-50 p-2 text-xs font-semibold text-emerald-800">
              <Check size={15} /> All dues settled! Outstanding balance is ₹0.
            </div>
          )}

          {/* Action buttons */}
          <div className="mt-5 flex justify-end gap-2 border-t border-slate-100 pt-3">
            <button
              type="button"
              onClick={doneWithReturn}
              className="rounded-lg bg-slate-900 hover:bg-slate-800 px-5 py-2 text-xs font-bold text-white transition shadow-sm cursor-pointer"
            >
              Done & Close
            </button>
          </div>
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
                <span>Send an OTP to the customer's phone to verify and confirm vehicle return.</span>
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
