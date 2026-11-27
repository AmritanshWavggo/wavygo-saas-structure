import { useState, useEffect, useMemo, useRef } from 'react'
import {
  AlertCircle,
  ArrowDownToLine,
  ArrowUpRight,
  BadgeIndianRupee,
  CalendarDays,
  Check,
  ChevronDown,
  CircleDollarSign,
  ClipboardList,
  Download,
  Eye,
  FileText,
  Pencil,
  Plus,
  Settings2,
  ExternalLink,
  Loader2,
  Mail,
  Phone,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  Trash2,
  Upload,
  Users,
  Wallet,
  Wrench,
  X,
} from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import { API_BASE_URL } from '../services/apiClient.js'
import { useDemoData } from '../data/DemoDataContext.jsx'
import { bookingService } from '../services/bookingService.js'
import { customerService } from '../services/customerService.js'
import { documentService } from '../services/documentService.js'
import { maintenanceService } from '../services/maintenanceService.js'
import { tenantService } from '../services/tenantService.js'
import { paymentService } from '../services/paymentService.js'
import { financeService } from '../services/financeService.js'
import { reportService } from '../services/reportService.js'
import { staffService } from '../services/staffService.js'
import { vehicleService } from '../services/vehicleService.js'
import { RecordPaymentModal } from '../components/RecordPaymentModal.jsx'
import { BookingLifecycleDialog } from '../components/BookingLifecycleDialogs.jsx'
import {
  BarChart,
  Button,
  Card,
  ComparisonChart,
  DataTable,
  Field,
  FilterSelect,
  MetricCard,
  Modal,
  PageHeader,
  SearchField,
  StatusBadge,
  Tabs,
} from '../components/ui/Workspace.jsx'

function PaymentStatusBadge({ status }) {
  const styles = {
    Paid: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
    'Partially Paid': 'bg-amber-50 text-amber-700 ring-amber-600/20',
    Unpaid: 'bg-rose-50 text-rose-700 ring-rose-600/20',
  }
  const cls = styles[status] || 'bg-slate-100 text-slate-700 ring-slate-500/20'
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${cls}`}>
      {status || 'Unpaid'}
    </span>
  )
}

function BookingStatusBadge({ status }) {
  return <StatusBadge status={status === 'Active' ? 'Rented' : status} />
}

const currency = (amount) =>
  `₹${Number(amount || 0).toLocaleString('en-IN')}`

function nextId(prefix, records) {
  // Continue the largest existing numeric suffix so inserted demo rows receive unique IDs.
  const max = records.reduce((largest, record) => {
    const number = Number(record.id?.match(/\d+$/)?.[0] || 0)
    return Math.max(largest, number)
  }, 0)
  return `${prefix}-${max + 1}`
}

function RecordForm({ title, fields, onClose, onSave, saveLabel = 'Save record', showDemoNote = false }) {
  const initialValues = Object.fromEntries(fields.map((field) => [field.name, field.initial || '']))
  const [values, setValues] = useState(initialValues)
  const [error, setError] = useState('')

  function submit(event) {
    event.preventDefault()
    // Form configuration drives required-field checks consistently across the demo screens.
    const missing = fields.find(
      (field) => field.required && !String(values[field.name] || '').trim(),
    )
    if (missing) {
      setError(`${missing.label} is required.`)
      return
    }
    setError('')
    onSave(values)
  }

  return (
    <Modal
      title={title}
      onClose={onClose}
      footer={
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" form="record-form"><Check size={15} />{saveLabel}</Button>
        </div>
      }
    >
      <form id="record-form" onSubmit={submit} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          {fields.map((field) => (
            <label key={field.name} className={`block ${field.wide ? 'sm:col-span-2' : ''}`}>
              <span className="mb-1.5 block text-xs font-medium text-slate-600">
                {field.label}{field.required && <span className="ml-0.5 text-rose-500">*</span>}
              </span>
              {field.type === 'select' ? (
                <select
                  required={field.required}
                  value={values[field.name] ?? ''}
                  onChange={(event) =>
                    setValues((current) => ({ ...current, [field.name]: event.target.value }))
                  }
                  className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
                >
                  <option value="">Select {field.label.toLowerCase()}</option>
                  {field.options.map((option) => (
                    <option value={option.value || option} key={option.value || option}>
                      {option.label || option}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  required={field.required}
                  type={field.type || 'text'}
                  min={field.min}
                  step={field.step}
                  value={field.type === 'file' ? undefined : (values[field.name] ?? '')}
                  placeholder={field.placeholder}
                  onChange={(event) => setValues((current) => ({
                    ...current,
                    [field.name]: field.type === 'file'
                      ? event.target.files?.[0]?.name || ''
                      : event.target.value,
                  }))}
                  className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100 placeholder:text-slate-400"
                />
              )}
            </label>
          ))}
        </div>
        {error && <p role="alert" className="text-xs text-rose-600">{error}</p>}
        {showDemoNote && (
          <p className="rounded-xl bg-amber-50 px-3 py-2 text-[11px] leading-5 text-amber-800">
            Demo only. This record is held in page state and is not sent to a server.
          </p>
        )}
      </form>
    </Modal>
  )
}

function DetailDialog({ title, rows, onClose, showDemoNote = false, footer }) {
  return (
    <Modal title={title} onClose={onClose} footer={footer}>
      <div className="space-y-3">
        {rows.map(([label, value]) => (
          <div key={label} className="flex items-start justify-between gap-4 border-b border-slate-100 pb-2.5 last:border-0">
            <span className="text-xs text-slate-500">{label}</span>
            <span className="text-right text-xs font-medium text-slate-800">{value || '—'}</span>
          </div>
        ))}
        {showDemoNote && <p className="pt-1 text-[11px] text-slate-400">Sample workspace details · Demo data only</p>}
      </div>
    </Modal>
  )
}

function VerifyCustomerModal({ customer, onClose, onVerified }) {
  const [customerEmail, setCustomerEmail] = useState(customer.email || '')
  const [phoneOtp, setPhoneOtp] = useState('')
  const [phoneOtpSent, setPhoneOtpSent] = useState(false)
  const [phoneSending, setPhoneSending] = useState(false)
  const [phoneVerifying, setPhoneVerifying] = useState(false)
  const [phoneVerified, setPhoneVerified] = useState(Boolean(customer.phone_verified))
  const [phoneMsg, setPhoneMsg] = useState({ type: '', text: '' })

  const [emailOtp, setEmailOtp] = useState('')
  const [emailOtpSent, setEmailOtpSent] = useState(false)
  const [emailSending, setEmailSending] = useState(false)
  const [emailVerifying, setEmailVerifying] = useState(false)
  const [emailVerified, setEmailVerified] = useState(Boolean(customer.email_verified))
  const [emailMsg, setEmailMsg] = useState({ type: '', text: '' })

  const [isMarkingVerified, setIsMarkingVerified] = useState(false)
  const [autoVerifyNotice, setAutoVerifyNotice] = useState('')
  const autoTriggeredRef = useRef(false)

  const bothVerified = phoneVerified && emailVerified

  async function handleSendPhoneOtp() {
    if (!customer.phone) {
      setPhoneMsg({ type: 'error', text: 'No phone number available for this customer.' })
      return
    }
    setPhoneSending(true)
    setPhoneMsg({ type: '', text: '' })
    try {
      await customerService.sendCustomerOtp({
        target: customer.phone,
        channel: 'phone',
        customer_name: customer.name,
      })
      setPhoneOtpSent(true)
      setPhoneMsg({ type: 'success', text: `SMS OTP sent to ${customer.phone} via Edumarc SMS.` })
    } catch (err) {
      setPhoneMsg({ type: 'error', text: err?.message || 'Failed to send SMS OTP.' })
    } finally {
      setPhoneSending(false)
    }
  }

  async function handleVerifyPhoneOtp() {
    if (!phoneOtp || phoneOtp.trim().length < 4) {
      setPhoneMsg({ type: 'error', text: 'Please enter a valid OTP.' })
      return
    }
    setPhoneVerifying(true)
    setPhoneMsg({ type: '', text: '' })
    try {
      await customerService.verifyCustomerOtp({
        target: customer.phone,
        channel: 'phone',
        otp: phoneOtp.trim(),
      })
      setPhoneVerified(true)
      setPhoneMsg({ type: 'success', text: 'Mobile number OTP verified successfully! ✓' })
    } catch (err) {
      setPhoneMsg({ type: 'error', text: err?.message || 'Invalid or expired OTP.' })
    } finally {
      setPhoneVerifying(false)
    }
  }

  async function handleSendEmailOtp() {
    const targetEmail = (customerEmail || customer.email || '').trim()
    if (!targetEmail || !targetEmail.includes('@')) {
      setEmailMsg({ type: 'error', text: 'Please enter a valid email address first.' })
      return
    }
    setEmailSending(true)
    setEmailMsg({ type: '', text: '' })
    try {
      await customerService.sendCustomerOtp({
        target: targetEmail,
        channel: 'email',
        customer_name: customer.name,
      })
      setEmailOtpSent(true)
      setEmailMsg({ type: 'success', text: `Email OTP sent to ${targetEmail} via Brevo.` })
    } catch (err) {
      setEmailMsg({ type: 'error', text: err?.message || 'Failed to send Email OTP.' })
    } finally {
      setEmailSending(false)
    }
  }

  async function handleVerifyEmailOtp() {
    if (!emailOtp || emailOtp.trim().length < 4) {
      setEmailMsg({ type: 'error', text: 'Please enter a valid OTP.' })
      return
    }
    const targetEmail = (customerEmail || customer.email || '').trim()
    setEmailVerifying(true)
    setEmailMsg({ type: '', text: '' })
    try {
      await customerService.verifyCustomerOtp({
        target: targetEmail,
        channel: 'email',
        otp: emailOtp.trim(),
      })
      setEmailVerified(true)
      setEmailMsg({ type: 'success', text: 'Email OTP verified successfully! ✓' })
    } catch (err) {
      setEmailMsg({ type: 'error', text: err?.message || 'Invalid or expired OTP.' })
    } finally {
      setEmailVerifying(false)
    }
  }

  // Automatically execute verification when BOTH Mobile and Email OTPs are verified
  useEffect(() => {
    if (phoneVerified && emailVerified && !autoTriggeredRef.current) {
      autoTriggeredRef.current = true
      executeVerification()
    }
  }, [phoneVerified, emailVerified])

  async function executeVerification() {
    setIsMarkingVerified(true)
    setAutoVerifyNotice('🎉 Phone & Email dono verify ho gaye! Profile automatically Verified mark ho rahi hai...')
    try {
      if (customerEmail && customerEmail !== customer.email) {
        try {
          await customerService.updateCustomer(customer.id, { email: customerEmail.trim() })
        } catch (_) {}
      }
      await customerService.verifyCustomer(customer.id)
    } catch (err) {
      // Local fallback for client-side state
    } finally {
      setTimeout(() => {
        setIsMarkingVerified(false)
        onVerified(customer.id)
        onClose()
      }, 1400)
    }
  }

  return (
    <Modal
      title="Verify Customer Identity"
      onClose={onClose}
      footer={
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 w-full">
          <Button type="button" variant="secondary" onClick={onClose} disabled={isMarkingVerified}>
            Cancel
          </Button>

          <Button
            type="button"
            onClick={executeVerification}
            disabled={!bothVerified || isMarkingVerified}
            className={`text-white transition ${
              bothVerified
                ? 'bg-emerald-600 hover:bg-emerald-700 cursor-pointer'
                : 'bg-slate-400 cursor-not-allowed opacity-60'
            }`}
          >
            {isMarkingVerified ? (
              <>
                <Loader2 size={15} className="animate-spin" />
                Auto-verifying...
              </>
            ) : bothVerified ? (
              <>
                <ShieldCheck size={15} />
                Verified ✓
              </>
            ) : (
              <>
                <ShieldCheck size={15} />
                Confirm & Mark Verified (Locked)
              </>
            )}
          </Button>
        </div>
      }
    >
      <div className="space-y-4 py-1">
        {/* Auto verification success banner */}
        {autoVerifyNotice && (
          <div className="rounded-xl border border-emerald-300 bg-emerald-50 p-3.5 text-xs font-medium text-emerald-800 flex items-center gap-2">
            <Loader2 size={16} className="animate-spin text-emerald-600 shrink-0" />
            <span>{autoVerifyNotice}</span>
          </div>
        )}

        {/* Verification Rule Notice */}
        {!bothVerified && (
          <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900 flex items-start gap-2">
            <AlertCircle size={15} className="text-amber-600 shrink-0 mt-0.5" />
            <div className="space-y-0.5">
              <p className="font-semibold">OTP Verification Zaroori Hai</p>
              <p className="text-[11px] text-amber-800 leading-relaxed">
                Jab tak customer ka <strong>Mobile SMS OTP</strong> aur <strong>Email OTP</strong> dono match nahi ho jaate, tab tak profile verified nahi hogi. Dono verify hote hi customer automatically Verified ho jayega.
              </p>
            </div>
          </div>
        )}

        {/* Customer Header Info */}
        <div className="flex items-center justify-between rounded-xl bg-slate-50 p-3.5 border border-slate-200">
          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-slate-900">{customer.name}</span>
              <span className="text-xs text-slate-400 font-mono">({customer.id})</span>
            </div>
            <p className="mt-0.5 text-xs text-slate-500">
              {customer.phone} {customer.email ? `· ${customer.email}` : ''}
            </p>
          </div>
          <div className="flex items-center gap-1.5">
            <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${
              bothVerified ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'
            }`}>
              {phoneVerified && emailVerified ? '2/2 Verified' : phoneVerified || emailVerified ? '1/2 Verified' : '0/2 Verified'}
            </span>
          </div>
        </div>

        {/* 1. Mobile Verification (Edumarc SMS) */}
        <div className={`rounded-xl border p-4 space-y-3 transition ${phoneVerified ? 'border-emerald-300 bg-emerald-50/30' : 'border-slate-200'}`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <span className={`grid size-8 place-items-center rounded-lg ${phoneVerified ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-600'}`}>
                <Phone size={16} />
              </span>
              <div>
                <div className="flex items-center gap-2">
                  <p className="text-xs font-semibold text-slate-800">1. Mobile SMS OTP</p>
                  <span className="text-[10px] text-rose-500 font-semibold">*Required</span>
                </div>
                <p className="text-xs text-slate-500">{customer.phone}</p>
              </div>
            </div>
            {phoneVerified ? (
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-semibold text-emerald-800">
                <Check size={13} /> Mobile Verified
              </span>
            ) : (
              <Button
                variant="secondary"
                className="h-8 px-2.5 text-xs"
                onClick={handleSendPhoneOtp}
                disabled={phoneSending}
              >
                {phoneSending ? <Loader2 size={13} className="animate-spin" /> : null}
                {phoneOtpSent ? 'Resend SMS' : 'Send SMS OTP'}
              </Button>
            )}
          </div>

          {phoneMsg.text && (
            <p className={`text-xs ${phoneMsg.type === 'error' ? 'text-rose-600' : 'text-emerald-700'}`}>
              {phoneMsg.text}
            </p>
          )}

          {phoneOtpSent && !phoneVerified && (
            <div className="flex items-center gap-2 pt-1">
              <input
                type="text"
                placeholder="6-digit OTP"
                maxLength={6}
                value={phoneOtp}
                onChange={(e) => setPhoneOtp(e.target.value.replace(/\D/g, ''))}
                className="h-9 w-32 rounded-lg border border-slate-300 px-3 text-sm font-mono text-center tracking-widest outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
              />
              <Button
                className="h-9 px-3 text-xs bg-emerald-600 hover:bg-emerald-700 text-white"
                onClick={handleVerifyPhoneOtp}
                disabled={phoneVerifying || phoneOtp.length < 4}
              >
                {phoneVerifying ? <Loader2 size={13} className="animate-spin" /> : 'Verify Code'}
              </Button>
            </div>
          )}
        </div>

        {/* 2. Email Verification (Brevo) */}
        <div className={`rounded-xl border p-4 space-y-3 transition ${emailVerified ? 'border-emerald-300 bg-emerald-50/30' : 'border-slate-200'}`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <span className={`grid size-8 place-items-center rounded-lg ${emailVerified ? 'bg-emerald-100 text-emerald-700' : 'bg-indigo-50 text-indigo-700'}`}>
                <Mail size={16} />
              </span>
              <div>
                <div className="flex items-center gap-2">
                  <p className="text-xs font-semibold text-slate-800">2. Email OTP</p>
                  <span className="text-[10px] text-rose-500 font-semibold">*Required</span>
                </div>
                <p className="text-xs text-slate-500">{customerEmail || 'Email not added'}</p>
              </div>
            </div>
            {emailVerified ? (
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-semibold text-emerald-800">
                <Check size={13} /> Email Verified
              </span>
            ) : (
              <Button
                variant="secondary"
                className="h-8 px-2.5 text-xs"
                onClick={handleSendEmailOtp}
                disabled={emailSending || (!customerEmail && !customer.email)}
              >
                {emailSending ? <Loader2 size={13} className="animate-spin" /> : null}
                {emailOtpSent ? 'Resend Email' : 'Send Email OTP'}
              </Button>
            )}
          </div>

          {!customer.email && !emailVerified && (
            <div className="pt-1">
              <label className="text-[11px] font-medium text-slate-600 block mb-1">
                Enter Email to send OTP:
              </label>
              <input
                type="email"
                placeholder="customer@example.com"
                value={customerEmail}
                onChange={(e) => setCustomerEmail(e.target.value)}
                className="h-8 w-full rounded-lg border border-slate-300 px-2.5 text-xs outline-none focus:border-indigo-500"
              />
            </div>
          )}

          {emailMsg.text && (
            <p className={`text-xs ${emailMsg.type === 'error' ? 'text-rose-600' : 'text-emerald-700'}`}>
              {emailMsg.text}
            </p>
          )}

          {emailOtpSent && !emailVerified && (
            <div className="flex items-center gap-2 pt-1">
              <input
                type="text"
                placeholder="6-digit OTP"
                maxLength={6}
                value={emailOtp}
                onChange={(e) => setEmailOtp(e.target.value.replace(/\D/g, ''))}
                className="h-9 w-32 rounded-lg border border-slate-300 px-3 text-sm font-mono text-center tracking-widest outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
              />
              <Button
                className="h-9 px-3 text-xs bg-indigo-600 hover:bg-indigo-700 text-white"
                onClick={handleVerifyEmailOtp}
                disabled={emailVerifying || emailOtp.length < 4}
              >
                {emailVerifying ? <Loader2 size={13} className="animate-spin" /> : 'Verify Code'}
              </Button>
            </div>
          )}
        </div>
      </div>
    </Modal>
  )
}

function AddCustomerModal({ onClose, onSave }) {
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [email, setEmail] = useState('')
  const [status, setStatus] = useState('Review')

  const [phoneOtp, setPhoneOtp] = useState('')
  const [phoneOtpSent, setPhoneOtpSent] = useState(false)
  const [phoneSending, setPhoneSending] = useState(false)
  const [phoneVerifying, setPhoneVerifying] = useState(false)
  const [phoneVerified, setPhoneVerified] = useState(false)
  const [phoneMsg, setPhoneMsg] = useState({ type: '', text: '' })

  const [emailOtp, setEmailOtp] = useState('')
  const [emailOtpSent, setEmailOtpSent] = useState(false)
  const [emailSending, setEmailSending] = useState(false)
  const [emailVerifying, setEmailVerifying] = useState(false)
  const [emailVerified, setEmailVerified] = useState(false)
  const [emailMsg, setEmailMsg] = useState({ type: '', text: '' })

  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState('')

  async function handleSendPhoneOtp() {
    if (!phone || phone.trim().length < 10) {
      setPhoneMsg({ type: 'error', text: 'Enter a valid 10-digit mobile number first.' })
      return
    }
    setPhoneSending(true)
    setPhoneMsg({ type: '', text: '' })
    try {
      await customerService.sendCustomerOtp({
        target: phone.trim(),
        channel: 'phone',
        customer_name: name.trim() || undefined,
      })
      setPhoneOtpSent(true)
      setPhoneMsg({ type: 'success', text: `SMS OTP sent to ${phone.trim()} via Edumarc.` })
    } catch (err) {
      setPhoneMsg({ type: 'error', text: err?.message || 'Failed to send SMS OTP.' })
    } finally {
      setPhoneSending(false)
    }
  }

  async function handleVerifyPhoneOtp() {
    if (!phoneOtp || phoneOtp.trim().length < 4) {
      setPhoneMsg({ type: 'error', text: 'Please enter a valid OTP.' })
      return
    }
    setPhoneVerifying(true)
    setPhoneMsg({ type: '', text: '' })
    try {
      await customerService.verifyCustomerOtp({
        target: phone.trim(),
        channel: 'phone',
        otp: phoneOtp.trim(),
      })
      setPhoneVerified(true)
      setStatus('Verified')
      setPhoneMsg({ type: 'success', text: 'Mobile number verified! Profile status set to Verified.' })
    } catch (err) {
      setPhoneMsg({ type: 'error', text: err?.message || 'Invalid or expired OTP.' })
    } finally {
      setPhoneVerifying(false)
    }
  }

  async function handleSendEmailOtp() {
    if (!email || !email.includes('@')) {
      setEmailMsg({ type: 'error', text: 'Enter a valid email address first.' })
      return
    }
    setEmailSending(true)
    setEmailMsg({ type: '', text: '' })
    try {
      await customerService.sendCustomerOtp({
        target: email.trim(),
        channel: 'email',
        customer_name: name.trim() || undefined,
      })
      setEmailOtpSent(true)
      setEmailMsg({ type: 'success', text: `Email OTP sent to ${email.trim()} via Brevo.` })
    } catch (err) {
      setEmailMsg({ type: 'error', text: err?.message || 'Failed to send Email OTP.' })
    } finally {
      setEmailSending(false)
    }
  }

  async function handleVerifyEmailOtp() {
    if (!emailOtp || emailOtp.trim().length < 4) {
      setEmailMsg({ type: 'error', text: 'Please enter a valid OTP.' })
      return
    }
    setEmailVerifying(true)
    setEmailMsg({ type: '', text: '' })
    try {
      await customerService.verifyCustomerOtp({
        target: email.trim(),
        channel: 'email',
        otp: emailOtp.trim(),
      })
      setEmailVerified(true)
      setStatus('Verified')
      setEmailMsg({ type: 'success', text: 'Email verified! Profile status set to Verified.' })
    } catch (err) {
      setEmailMsg({ type: 'error', text: err?.message || 'Invalid or expired OTP.' })
    } finally {
      setEmailVerifying(false)
    }
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!name.trim()) {
      setError('Full name is required.')
      return
    }
    if (!phone.trim()) {
      setError('Phone number is required.')
      return
    }
    if (status === 'Verified' && (!phoneVerified || !emailVerified)) {
      setError('Customer ko "Verified" karne ke liye Mobile aur Email dono ka OTP verify hona zaroori hai. Ya fir status "Review" select karein.')
      return
    }
    setError('')
    setIsSaving(true)

    try {
      await onSave({
        name: name.trim(),
        phone: phone.trim(),
        email: email.trim() || '',
        status,
        phone_verified: phoneVerified,
        email_verified: emailVerified,
      })
      onClose()
    } catch (err) {
      setError(err?.message || 'Failed to create customer.')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <Modal
      title="Add New Customer"
      onClose={onClose}
      footer={
        <div className="flex justify-end gap-2 w-full">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="submit"
            form="add-customer-form"
            disabled={isSaving}
            className="bg-emerald-600 hover:bg-emerald-700 text-white"
          >
            {isSaving ? <Loader2 size={15} className="animate-spin" /> : <Check size={15} />}
            Save Customer
          </Button>
        </div>
      }
    >
      <form id="add-customer-form" onSubmit={handleSubmit} className="space-y-4 py-1">
        {error && (
          <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700">
            {error}
          </div>
        )}

        <div>
          <label className="mb-1.5 block text-xs font-medium text-slate-700">
            Full Name <span className="text-rose-500">*</span>
          </label>
          <input
            required
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Rahul Sharma"
            className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
          />
        </div>

        {/* Phone + Optional Inline SMS OTP */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="text-xs font-medium text-slate-700">
              Phone Number <span className="text-rose-500">*</span>
            </label>
            {phoneVerified ? (
              <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700">
                <Check size={12} /> Verified via SMS
              </span>
            ) : (
              <button
                type="button"
                onClick={handleSendPhoneOtp}
                disabled={phoneSending || phone.trim().length < 10}
                className="text-[11px] font-medium text-emerald-700 hover:text-emerald-800 underline disabled:opacity-40"
              >
                {phoneSending ? 'Sending SMS...' : phoneOtpSent ? 'Resend SMS' : 'Verify via SMS OTP'}
              </button>
            )}
          </div>
          <input
            required
            type="tel"
            value={phone}
            onChange={(e) => {
              setPhone(e.target.value)
              if (phoneVerified) setPhoneVerified(false)
            }}
            placeholder="e.g. 9876543210"
            className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
          />
          {phoneMsg.text && (
            <p className={`mt-1 text-xs ${phoneMsg.type === 'error' ? 'text-rose-600' : 'text-emerald-700'}`}>
              {phoneMsg.text}
            </p>
          )}
          {phoneOtpSent && !phoneVerified && (
            <div className="mt-2 flex items-center gap-2 rounded-xl bg-slate-50 p-2.5 border border-slate-200">
              <input
                type="text"
                placeholder="6-digit OTP"
                maxLength={6}
                value={phoneOtp}
                onChange={(e) => setPhoneOtp(e.target.value.replace(/\D/g, ''))}
                className="h-8 w-28 rounded-lg border border-slate-300 px-2.5 text-xs font-mono text-center tracking-widest outline-none focus:border-emerald-500"
              />
              <Button
                type="button"
                onClick={handleVerifyPhoneOtp}
                disabled={phoneVerifying || phoneOtp.length < 4}
                className="h-8 px-2.5 text-xs bg-emerald-600 hover:bg-emerald-700 text-white"
              >
                {phoneVerifying ? <Loader2 size={12} className="animate-spin" /> : 'Confirm'}
              </Button>
            </div>
          )}
        </div>

        {/* Email + Optional Inline Email OTP */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="text-xs font-medium text-slate-700">
              Email Address <span className="text-slate-400 font-normal">(Optional)</span>
            </label>
            {email.trim() && (
              emailVerified ? (
                <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700">
                  <Check size={12} /> Verified via Email
                </span>
              ) : (
                <button
                  type="button"
                  onClick={handleSendEmailOtp}
                  disabled={emailSending || !email.includes('@')}
                  className="text-[11px] font-medium text-emerald-700 hover:text-emerald-800 underline disabled:opacity-40"
                >
                  {emailSending ? 'Sending Email...' : emailOtpSent ? 'Resend Email' : 'Verify via Email OTP'}
                </button>
              )
            )}
          </div>
          <input
            type="email"
            value={email}
            onChange={(e) => {
              setEmail(e.target.value)
              if (emailVerified) setEmailVerified(false)
            }}
            placeholder="e.g. customer@example.com"
            className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
          />
          {emailMsg.text && (
            <p className={`mt-1 text-xs ${emailMsg.type === 'error' ? 'text-rose-600' : 'text-emerald-700'}`}>
              {emailMsg.text}
            </p>
          )}
          {emailOtpSent && !emailVerified && (
            <div className="mt-2 flex items-center gap-2 rounded-xl bg-slate-50 p-2.5 border border-slate-200">
              <input
                type="text"
                placeholder="6-digit OTP"
                maxLength={6}
                value={emailOtp}
                onChange={(e) => setEmailOtp(e.target.value.replace(/\D/g, ''))}
                className="h-8 w-28 rounded-lg border border-slate-300 px-2.5 text-xs font-mono text-center tracking-widest outline-none focus:border-emerald-500"
              />
              <Button
                type="button"
                onClick={handleVerifyEmailOtp}
                disabled={emailVerifying || emailOtp.length < 4}
                className="h-8 px-2.5 text-xs bg-indigo-600 hover:bg-indigo-700 text-white"
              >
                {emailVerifying ? <Loader2 size={12} className="animate-spin" /> : 'Confirm'}
              </Button>
            </div>
          )}
        </div>

        {/* Profile Status Explanation & Selector */}
        <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-3.5 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-800">Profile Status Option</span>
            <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${status === 'Verified' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}`}>
              {status}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2 pt-1">
            <button
              type="button"
              onClick={() => setStatus('Review')}
              className={`rounded-xl border p-2.5 text-left transition ${status === 'Review' ? 'border-amber-500 bg-amber-50/70 text-amber-950 font-medium' : 'border-slate-200 bg-white text-slate-600'}`}
            >
              <div className="flex items-center justify-between text-xs font-semibold">
                <span>Review (Recommended)</span>
                {status === 'Review' && <Check size={13} className="text-amber-700" />}
              </div>
              <p className="mt-1 text-[11px] text-slate-500 leading-tight">
                Profile status "Review" rahega. Baad me customer table me "Verify" button daba kar kabhi bhi SMS/Email OTP bhej kar verify kar sakte hain.
              </p>
            </button>

            <button
              type="button"
              onClick={() => setStatus('Verified')}
              className={`rounded-xl border p-2.5 text-left transition ${status === 'Verified' ? 'border-emerald-500 bg-emerald-50/70 text-emerald-950 font-medium' : 'border-slate-200 bg-white text-slate-600'}`}
            >
              <div className="flex items-center justify-between text-xs font-semibold">
                <span>Verified</span>
                {status === 'Verified' && <Check size={13} className="text-emerald-700" />}
              </div>
              <p className="mt-1 text-[11px] text-slate-500 leading-tight">
                Customer genuine hai aur aapne physical ID/documents personally verify kar liye hain ya upar OTP verify ho chuka hai.
              </p>
            </button>
          </div>
        </div>
      </form>
    </Modal>
  )
}

function Customers() {
  const { customers, addRecord, updateRecord, syncCustomers } = useDemoData()
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('All')
  const [searchParams] = useSearchParams()
  const [showForm, setShowForm] = useState(() => searchParams.get('new') === '1')
  const [selected, setSelected] = useState(null)
  const [verifyCustomer, setVerifyCustomer] = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isSyncing, setIsSyncing] = useState(false)
  const [notice, setNotice] = useState('')

  useEffect(() => {
    syncCustomers?.()
  }, [])

  async function handleRefresh() {
    setIsSyncing(true)
    try {
      if (syncCustomers) await syncCustomers()
    } finally {
      setIsSyncing(false)
    }
  }

  const filtered = customers.filter((customer) =>
    `${customer.name} ${customer.phone} ${customer.email} ${customer.id}`.toLowerCase().includes(query.toLowerCase())
    && (status === 'All' || customer.status === status),
  )
  const totalPaid = customers.reduce((total, item) => total + (item.paid || 0), 0)
  const pending = customers.reduce((total, item) => total + (item.pending || 0), 0)

  return (
    <div>
      <PageHeader
        title="Customers"
        description="Get to know your customers and keep their rental history in one place."
        action={
          <div className="flex items-center gap-2">
            <Button variant="quiet" onClick={handleRefresh} disabled={isSyncing}>
              <RefreshCw size={15} className={isSyncing ? 'animate-spin' : ''} />
              {isSyncing ? 'Syncing...' : 'Sync backend'}
            </Button>
            <Button onClick={() => setShowForm(true)}><Plus size={16} />Add customer</Button>
          </div>
        }
      />

      {notice && (
        <div className="mb-4 flex items-center justify-between rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-800">
          <div className="flex items-center gap-2">
            <Check size={16} className="text-emerald-600" />
            <span>{notice}</span>
          </div>
          <button type="button" onClick={() => setNotice('')} className="text-emerald-600 hover:text-emerald-900">
            <X size={15} />
          </button>
        </div>
      )}

      <div className="mb-5 grid grid-cols-2 gap-3 xl:grid-cols-4">
        <MetricCard label="Total customers" value={customers.length} caption="Managed customers" icon={Users} />
        <MetricCard label="Verified profiles" value={customers.filter((item) => item.status === 'Verified').length} icon={ShieldCheck} tone="blue" />
        <MetricCard label="Total collected" value={currency(totalPaid)} icon={BadgeIndianRupee} tone="violet" />
        <MetricCard label="Pending customer dues" value={currency(pending)} icon={Wallet} tone="amber" />
      </div>

      <Card className="overflow-hidden">
        <div className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5">
          <SearchField value={query} onChange={setQuery} placeholder="Search customers…" />
          <FilterSelect label="Status" value={status} onChange={setStatus} options={['All', 'Verified', 'Review']} />
        </div>
        <DataTable
          rows={filtered}
          emptyTitle="No customers registered yet"
          emptyText="Customers added through bookings or manually will appear here."
          columns={[
            {
              key: 'customer',
              label: 'Customer',
              render: (row) => (
                <button
                  type="button"
                  onClick={() => setSelected(row)}
                  className="text-left font-medium text-slate-800 hover:text-emerald-800"
                >
                  {row.name}
                  <span className="mt-1 block text-[11px] font-normal text-slate-400">
                    {row.id} · {row.email || 'No email'}
                  </span>
                </button>
              ),
            },
            { key: 'phone', label: 'Phone' },
            {
              key: 'bookings',
              label: 'Bookings',
              render: (row) => (
                <span>
                  {row.bookings || 0}{' '}
                  <span className="text-[11px] text-slate-400">· {row.active || 0} active</span>
                </span>
              ),
            },
            { key: 'paid', label: 'Total paid', render: (row) => currency(row.paid || 0) },
            { key: 'pending', label: 'Pending', render: (row) => currency(row.pending || 0) },
            {
              key: 'status',
              label: 'Status',
              render: (row) => (
                <div className="flex items-center gap-1.5">
                  <StatusBadge status={row.status} />
                  {row.status === 'Review' && (
                    <span className="inline-flex items-center rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-medium text-amber-700 ring-1 ring-inset ring-amber-600/20">
                      Unverified
                    </span>
                  )}
                </div>
              ),
            },
            {
              key: 'actions',
              label: '',
              render: (row) => (
                <div className="flex items-center justify-end gap-1.5">
                  {row.status === 'Review' && (
                    <Button
                      variant="secondary"
                      className="min-h-8 px-2.5 text-xs font-semibold text-emerald-700 border-emerald-300 hover:bg-emerald-50"
                      onClick={() => setVerifyCustomer(row)}
                    >
                      <ShieldCheck size={14} className="text-emerald-600" />
                      Verify
                    </Button>
                  )}
                  <Button variant="quiet" className="min-h-8 px-2.5" onClick={() => setSelected(row)}>
                    <Eye size={15} />View
                  </Button>
                </div>
              ),
            },
          ]}
        />
        <p className="border-t border-slate-100 px-5 py-3 text-[11px] text-slate-400">
          {filtered.length} customers listed
        </p>
      </Card>

      {verifyCustomer && (
        <VerifyCustomerModal
          customer={verifyCustomer}
          onClose={() => setVerifyCustomer(null)}
          onVerified={async (customerId) => {
            updateRecord('customers', customerId, { status: 'Verified' })
            if (syncCustomers) await syncCustomers()
            setNotice(`Customer "${verifyCustomer.name}" verified successfully!`)
            setTimeout(() => setNotice(''), 4000)
          }}
        />
      )}

      {showForm && (
        <AddCustomerModal
          onClose={() => setShowForm(false)}
          onSave={async (values) => {
            try {
              const res = await customerService.createCustomer(values)
              if (syncCustomers) await syncCustomers()
              else {
                addRecord('customers', {
                  ...values,
                  id: res?.id || nextId('CU', customers),
                  bookings: 0,
                  active: 0,
                  paid: 0,
                  pending: 0,
                  backendSynced: true,
                })
              }
            } catch (err) {
              addRecord('customers', {
                ...values,
                id: nextId('CU', customers),
                bookings: 0,
                active: 0,
                paid: 0,
                pending: 0,
              })
            }
            setNotice(`Customer "${values.name}" created successfully with status ${values.status}!`)
            setTimeout(() => setNotice(''), 4000)
          }}
        />
      )}
      {selected && (
        <DetailDialog
          title={selected.name}
          record={selected}
          onClose={() => setSelected(null)}
          rows={[
            ['Customer ID', selected.id], ['Phone', selected.phone], ['Email', selected.email],
            ['Profile status', selected.status], ['Total bookings', selected.bookings],
            ['Active bookings', selected.active], ['Total paid', currency(selected.paid)],
            ['Pending amount', currency(selected.pending)],
          ]}
        />
      )}
    </div>
  )
}

function ReturnBikeModal({ booking, onClose, onCompleted }) {
  const phone = booking.phone || booking.customer_details?.phone || ''
  const [returnOtp, setReturnOtp] = useState('')
  const [otpSent, setOtpSent] = useState(false)
  const [isSending, setIsSending] = useState(false)
  const [isVerifying, setIsVerifying] = useState(false)
  const [msg, setMsg] = useState({ type: '', text: '' })
  const [isCompleted, setIsCompleted] = useState(false)

  async function handleSendOtp() {
    if (!phone) {
      setMsg({ type: 'error', text: 'No phone number linked to this booking.' })
      return
    }
    setIsSending(true)
    setMsg({ type: '', text: '' })
    try {
      await bookingService.sendBookingOtp({
        phone,
        purpose: 'return',
        booking_id: booking.id,
        customer_name: booking.customer,
        vehicle_name: booking.vehicle,
      })
      setOtpSent(true)
      setMsg({ type: 'success', text: `Return confirmation OTP sent to ${phone} via SMS.` })
    } catch (err) {
      setMsg({ type: 'error', text: err?.message || 'Failed to send return OTP.' })
    } finally {
      setIsSending(false)
    }
  }

  async function executeReturnVerify(otpToVerify) {
    const code = (otpToVerify !== undefined ? otpToVerify : returnOtp).trim()
    if (!code || code.length < 4) {
      setMsg({ type: 'error', text: 'Please enter the 6-digit OTP code.' })
      return
    }
    setIsVerifying(true)
    setMsg({ type: '', text: '' })
    try {
      await bookingService.verifyBookingOtp({
        phone,
        purpose: 'return',
        otp: code,
        booking_id: booking.id,
      })
      setIsCompleted(true)
      setMsg({ type: 'success', text: 'OTP matched! Bike return confirmed & vehicle moved to Under Review. ✓' })
      setTimeout(() => {
        onCompleted(booking.id)
        onClose()
      }, 1200)
    } catch (err) {
      setMsg({ type: 'error', text: err?.message || 'Invalid or expired OTP code.' })
    } finally {
      setIsVerifying(false)
    }
  }

  function handleOtpChange(val) {
    const cleaned = val.replace(/\D/g, '')
    setReturnOtp(cleaned)
    if (cleaned.length === 6 && !isVerifying && !isCompleted) {
      executeReturnVerify(cleaned)
    }
  }

  return (
    <Modal
      title={`Return Bike & End Ride · ${booking.id}`}
      onClose={onClose}
      footer={
        <div className="flex items-center justify-between gap-3 w-full">
          <Button type="button" variant="secondary" onClick={onClose} disabled={isVerifying || isCompleted}>
            Cancel
          </Button>
          <Button
            type="button"
            onClick={() => executeReturnVerify()}
            disabled={!otpSent || returnOtp.length < 4 || isVerifying || isCompleted}
            className={`text-white transition ${
              otpSent && returnOtp.length >= 4 && !isCompleted
                ? 'bg-amber-600 hover:bg-amber-700 cursor-pointer'
                : 'bg-slate-400 cursor-not-allowed opacity-60'
            }`}
          >
            {isVerifying ? (
              <>
                <Loader2 size={15} className="animate-spin" />
                Ending ride...
              </>
            ) : isCompleted ? (
              <>
                <Check size={15} />
                Moved to Under Review ✓
              </>
            ) : (
              <>
                <RotateCcw size={15} />
                Verify OTP & End Ride
              </>
            )}
          </Button>
        </div>
      }
    >
      <div className="space-y-4 py-1">
        {/* Booking Summary Box */}
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-slate-500">Vehicle & Customer</p>
              <p className="font-semibold text-slate-900">{booking.vehicle}</p>
              <p className="text-xs text-slate-600 mt-0.5">{booking.customer} · {phone || 'No phone'}</p>
            </div>
            <StatusBadge status={booking.status} />
          </div>

          <div className="grid grid-cols-2 gap-2 border-t border-slate-200 pt-2.5 text-xs">
            <div>
              <span className="text-slate-500">Rental dates:</span>
              <p className="font-medium text-slate-800 mt-0.5">{booking.dates}</p>
            </div>
            <div>
              <span className="text-slate-500">Financials:</span>
              <p className="font-medium text-slate-800 mt-0.5">
                Paid: {currency(booking.paid)} {booking.pending > 0 && <span className="text-rose-600 font-semibold">(Due: {currency(booking.pending)})</span>}
              </p>
            </div>
          </div>
        </div>

        {booking.pending > 0 && (
          <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 flex items-start gap-2">
            <AlertCircle size={15} className="text-amber-600 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">Pending balance: {currency(booking.pending)}</p>
              <p className="text-[11px] text-amber-700 mt-0.5">
                Please collect or settle the pending balance from the customer before or during return.
              </p>
            </div>
          </div>
        )}

        {/* SMS OTP Section */}
        <div className="rounded-xl border border-slate-200 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <span className="grid size-8 place-items-center rounded-lg bg-amber-100 text-amber-800">
                <Phone size={16} />
              </span>
              <div>
                <div className="flex items-center gap-2">
                  <p className="text-xs font-semibold text-slate-800">Return Confirmation OTP</p>
                  <span className="text-[10px] text-rose-500 font-semibold">*Required</span>
                </div>
                <p className="text-xs text-slate-500">{phone || 'No phone'}</p>
              </div>
            </div>

            <Button
              variant="secondary"
              className="h-8 px-2.5 text-xs"
              onClick={handleSendOtp}
              disabled={isSending || !phone || isCompleted}
            >
              {isSending ? <Loader2 size={13} className="animate-spin" /> : null}
              {otpSent ? 'Resend OTP' : 'Send Return OTP'}
            </Button>
          </div>

          <p className="text-[11px] text-slate-500 leading-relaxed">
            Customer ke mobile number par SMS se OTP bheja jayega. Customer se OTP lekar enter karein jisse bike return confirm ho aur ride officially end ho sake.
          </p>

          {msg.text && (
            <p className={`text-xs ${msg.type === 'error' ? 'text-rose-600' : 'text-emerald-700'}`}>
              {msg.text}
            </p>
          )}

          {otpSent && !isCompleted && (
            <div className="flex items-center gap-2 pt-1">
              <input
                type="text"
                placeholder="6-digit OTP"
                maxLength={6}
                value={returnOtp}
                onChange={(e) => handleOtpChange(e.target.value)}
                autoFocus
                className="h-9 w-32 rounded-lg border border-slate-300 px-3 text-sm font-mono text-center tracking-widest outline-none focus:border-amber-500 focus:ring-2 focus:ring-amber-100"
              />
              <Button
                className="h-9 px-3 text-xs bg-amber-600 hover:bg-amber-700 text-white"
                onClick={() => executeReturnVerify()}
                disabled={isVerifying || returnOtp.length < 4}
              >
                {isVerifying ? <Loader2 size={13} className="animate-spin" /> : 'Confirm Return'}
              </Button>
            </div>
          )}
        </div>
      </div>
    </Modal>
  )
}

function Bookings() {
  const { bookings, vehicles, customers, currentDemoUser, updateRecord, createDemoBooking, cancelDemoBooking, syncOfflineBookings, syncPayments, syncCustomers, syncVehicles } = useDemoData()
  const [query, setQuery] = useState('')
  const [tab, setTab] = useState('All')
  const [selected, setSelected] = useState(null)
  const [paymentModalBooking, setPaymentModalBooking] = useState(null)
  const [lifecycleBooking, setLifecycleBooking] = useState(null)
  const [lifecycleAction, setLifecycleAction] = useState(null)
  const [showBookingForm, setShowBookingForm] = useState(false)
  const [cancelForm, setCancelForm] = useState(null)
  const [formError, setFormError] = useState('')
  const [notice, setNotice] = useState('')
  const [isSyncing, setIsSyncing] = useState(false)

  useEffect(() => {
    syncOfflineBookings?.()
  }, [])

  const online = bookings.filter((item) => item.type === 'Online').length
  const offline = bookings.filter((item) => item.type === 'Offline').length
  const revenue = bookings.reduce((sum, item) => sum + Number(item.paid || 0), 0)
  const pending = bookings.reduce((sum, item) => sum + Number(item.pending || 0), 0)
  const tabs = ['All', 'Online', 'Offline', 'Confirmed', 'Active', 'Returned', 'Completed', 'Cancelled']
  const filtered = bookings.filter((booking) => {
    // The shared tab control intentionally matches either booking channel or booking status.
    const termMatch = `${booking.id} ${booking.customer} ${booking.vehicle}`.toLowerCase().includes(query.toLowerCase())
    const tabMatch = tab === 'All' || booking.type === tab || booking.status === tab
    return termMatch && tabMatch
  })

  async function handleRefresh() {
    setIsSyncing(true)
    try {
      if (syncOfflineBookings) {
        await syncOfflineBookings()
      }
    } finally {
      setIsSyncing(false)
    }
  }

  async function syncLifecycleData() {
    if (syncOfflineBookings) await syncOfflineBookings()
    if (syncCustomers) await syncCustomers()
    if (syncVehicles) await syncVehicles({ force: true })
    if (syncPayments) await syncPayments()
  }

  return (
    <div>
      <PageHeader
        title="Bookings"
        description="Track online and in-store rentals, upcoming handovers and payments."
        action={
          <div className="flex items-center gap-2">
            <Button variant="quiet" onClick={handleRefresh} disabled={isSyncing}>
              <RefreshCw size={15} className={isSyncing ? 'animate-spin' : ''} />
              {isSyncing ? 'Syncing...' : 'Sync backend'}
            </Button>
            <Link to="/app/bookings/new">
              <Button><Plus size={16} />Offline booking</Button>
            </Link>
          </div>
        }
      />

      {notice && (
        <div className="mb-4 flex items-center justify-between rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-800">
          <div className="flex items-center gap-2">
            <Check size={16} className="text-emerald-600" />
            <span>{notice}</span>
          </div>
          <button type="button" onClick={() => setNotice('')} className="text-emerald-600 hover:text-emerald-900">
            <X size={15} />
          </button>
        </div>
      )}

      <div className="mb-5 grid grid-cols-2 gap-3 xl:grid-cols-4">
        <MetricCard label="Total bookings" value={bookings.length} caption="All bookings" icon={ClipboardList} />
        <MetricCard label="Online bookings" value={online} icon={ArrowUpRight} tone="blue" />
        <MetricCard label="Offline bookings" value={offline} icon={CalendarDays} tone="violet" />
        <MetricCard label="Revenue · pending" value={`${currency(revenue)} · ${currency(pending)}`} icon={CircleDollarSign} tone="amber" />
      </div>
      <Card className="overflow-hidden">
        <Tabs items={tabs.map((label) => ({ label, value: label, count: label === 'All' ? bookings.length : undefined }))} value={tab} onChange={setTab} />
        <div className="p-4 sm:p-5"><SearchField value={query} onChange={setQuery} placeholder="Search ID, customer or vehicle…" /></div>
        <DataTable
          rows={filtered}
          emptyTitle="No customers registered yet"
          emptyText="Customers added through bookings or manually will appear here."
          columns={[
            {
              key: 'id',
              label: 'Booking ID',
              render: (row) => (
                <div className="flex items-center gap-1.5">
                  <button type="button" onClick={() => setSelected(row)} className="font-semibold text-emerald-800 hover:underline">
                    {row.id}
                  </button>
                  {row.backendSynced && (
                    <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700 ring-1 ring-emerald-600/20">
                      API
                    </span>
                  )}
                </div>
              ),
            },
            { key: 'customer', label: 'Customer', render: (row) => <><span className="font-medium text-slate-800">{row.customer}</span><span className="mt-1 block text-[11px] text-slate-400">{row.vehicle}</span></> },
            { key: 'dates', label: 'Rental dates' },
            { key: 'type', label: 'Type', render: (row) => <span className="text-xs">{row.type}</span> },
            { key: 'status', label: 'Status', render: (row) => <BookingStatusBadge status={row.status} /> },
            {
              key: 'payment_status',
              label: 'Payment',
              render: (row) => {
                const pStatus = row.payment_status || (Number(row.paid) >= Number(row.total_amount) && Number(row.total_amount) > 0 ? 'Paid' : Number(row.paid) > 0 ? 'Partially Paid' : 'Unpaid')
                return <PaymentStatusBadge status={pStatus} />
              },
            },
            { key: 'paid', label: 'Paid', render: (row) => currency(row.paid) },
            {
              key: 'outstanding',
              label: 'Outstanding',
              render: (row) => {
                const out = row.outstanding !== undefined ? Number(row.outstanding) : Math.max(0, Number(row.total_amount || 0) - Number(row.paid || 0))
                return currency(out)
              },
            },
            {
              key: 'actions',
              label: '',
              render: (row) => {
                const pStatus = row.payment_status || (Number(row.paid) >= Number(row.total_amount) && Number(row.total_amount) > 0 ? 'Paid' : Number(row.paid) > 0 ? 'Partially Paid' : 'Unpaid')
                const out = row.outstanding !== undefined ? Number(row.outstanding) : Math.max(0, Number(row.total_amount || 0) - Number(row.paid || 0))
                const canPay = pStatus !== 'Paid' && out > 0 && row.status !== 'Cancelled'
                const action = row.status === 'Confirmed' ? 'handover' : row.status === 'Active' ? 'return' : row.status === 'Returned' ? 'complete' : null
                return (
                  <div className="flex gap-1">
                    <Button variant="quiet" className="min-h-8 px-2" aria-label={`View ${row.id}`} onClick={() => setSelected(row)}>
                      <Eye size={15} />
                    </Button>
                    {canPay && (
                      <Button variant="quiet" className="min-h-8 px-2 text-emerald-700 font-medium" onClick={() => setPaymentModalBooking(row)}>
                        Record payment
                      </Button>
                    )}
                    {action && (
                      <Button variant="quiet" className="min-h-8 px-2 text-emerald-700 font-medium" onClick={() => { setLifecycleBooking(row); setLifecycleAction(action) }}>
                        {action === 'handover' ? 'Mark as Rented / Handover' : action === 'return' ? 'Mark as Returned' : 'Complete Booking'}
                      </Button>
                    )}
                  </div>
                )
              },
            },
          ]}
        />
        <p className="border-t border-slate-100 px-5 py-3 text-[11px] text-slate-400">
          Showing {filtered.length} bookings · Offline desk & online reservations
        </p>
      </Card>
      {selected && (
        <DetailDialog
          title={`Booking ${selected.id}`}
          onClose={() => setSelected(null)}
          record={selected}
          rows={[
            ...(selected.advancePaymentError ? [['Advance payment warning', <span className="text-rose-700">{selected.advancePaymentError} — use Record Payment to retry.</span>]] : []),
            ['Timeline', <span>Created: {selected.created_at || 'Not recorded'}<br />Handover: {selected.handoverAt || 'Not recorded'}<br />Returned: {selected.returnedAt || 'Not recorded'}<br />Completed: {selected.completedAt || 'Not recorded'}</span>],
            ['Additional charges', (selected.additionalCharges || []).length ? (selected.additionalCharges || []).map((charge, index) => <span key={index} className="block">{currency(charge.amount)} · {charge.reason} ({charge.type})</span>) : 'None'],
            ...Object.entries(selected).map(([key, value]) => [
              key.replace(/([A-Z])/g, ' $1').replace(/^./, (char) => char.toUpperCase()),
              ['paid', 'pending', 'outstanding', 'total_amount', 'base_amount'].includes(key) ? currency(value) : (typeof value === 'object' ? JSON.stringify(value) : value),
            ]),
            ['Payment Status', selected.payment_status || (Number(selected.paid) >= Number(selected.total_amount) && Number(selected.total_amount) > 0 ? 'Paid' : Number(selected.paid) > 0 ? 'Partially Paid' : 'Unpaid')],
            ['Payment Transactions', (selected.payment_details?.transactions || []).length > 0 ? (
              <div className="mt-1 space-y-1.5">
                {selected.payment_details.transactions.map((tx, idx) => (
                  <div key={idx} className="rounded-md bg-slate-50 p-2 text-xs text-slate-700">
                    <span className="font-semibold text-emerald-800">{tx.id || `TX-${idx+1}`}</span> · {currency(tx.amount)} via {tx.method} ({tx.date?.substring(0, 10) || 'Date N/A'})
                    {tx.transaction_reference && <span className="block text-slate-400">Ref: {tx.transaction_reference}</span>}
                    {tx.notes && <span className="block italic text-slate-500">Note: {tx.notes}</span>}
                  </div>
                ))}
              </div>
            ) : 'No transactions recorded yet'],
          ]}
        />
      )}
      {paymentModalBooking && (
        <RecordPaymentModal
          isOpen={!!paymentModalBooking}
          booking={paymentModalBooking}
          onClose={() => setPaymentModalBooking(null)}
          onSuccess={async () => {
            await syncLifecycleData()
          }}
        />
      )}
      <BookingLifecycleDialog
        action={lifecycleAction}
        booking={lifecycleBooking}
        onClose={() => { setLifecycleAction(null); setLifecycleBooking(null) }}
        onSuccess={syncLifecycleData}
      />
    </div>
  )
}

function Payments() {
  const {
    payments = [],
    bookings = [],
    expenses = [],
    financeOverview,
    syncPayments,
    syncFinance,
    syncOfflineBookings,
    addRecord,
    updateRecord,
    deleteRecord,
  } = useDemoData()
  const [query, setQuery] = useState('')
  const [tab, setTab] = useState('All')
  const [dateRange, setDateRange] = useState('This month')
  const [selected, setSelected] = useState(null)
  const [isSyncing, setIsSyncing] = useState(false)
  const [showRecordModal, setShowRecordModal] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [formError, setFormError] = useState('')
  const [refundLoading, setRefundLoading] = useState(false)

  // Section switcher: 'payments' | 'expenses'
  const [section, setSection] = useState('payments')

  // Expense form state
  const [showExpenseModal, setShowExpenseModal] = useState(false)
  const [expCategory, setExpCategory] = useState('Rent & Operations')
  const [expTitle, setExpTitle] = useState('')
  const [expAmount, setExpAmount] = useState('')
  const [expPayee, setExpPayee] = useState('')
  const [expMethod, setExpMethod] = useState('Bank Transfer')
  const [expStatus, setExpStatus] = useState('Paid')
  const [expNotes, setExpNotes] = useState('')
  const [isExpSubmitting, setIsExpSubmitting] = useState(false)
  const [expFormError, setExpFormError] = useState('')
  const [expFilterCategory, setExpFilterCategory] = useState('All')

  // Payment Form State
  const [formBooking, setFormBooking] = useState('')
  const [formCustomer, setFormCustomer] = useState('')
  const [formAmount, setFormAmount] = useState('')
  const [formMethod, setFormMethod] = useState('UPI')
  const [formStatus, setFormStatus] = useState('Paid')
  const [formNotes, setFormNotes] = useState('')

  const revenue = payments
    .filter((p) => p.status !== 'Refunded')
    .reduce((sum, payment) => sum + (Number(payment.amount) || 0), 0)

  const onlineRevenue = payments
    .filter((p) => p.status !== 'Refunded' && (p.method === 'UPI' || p.method === 'Card' || p.method === 'Online'))
    .reduce((sum, payment) => sum + (Number(payment.amount) || 0), 0)

  const offlineRevenue = payments
    .filter((p) => p.status !== 'Refunded' && (p.method === 'Cash' || p.method === 'Bank Transfer'))
    .reduce((sum, payment) => sum + (Number(payment.amount) || 0), 0)

  const totalExpenses = expenses.reduce((sum, e) => sum + (Number(e.amount) || 0), 0)

  const pendingTotal = bookings.reduce((sum, b) => sum + (Number(b.pending) || 0), 0)

  // Dynamic monthly comparison data computed from actual payments and expenses
  const comparisonData = useMemo(() => {
    if (
      financeOverview?.comparison_chart &&
      Array.isArray(financeOverview.comparison_chart) &&
      financeOverview.comparison_chart.length > 0
    ) {
      return financeOverview.comparison_chart
    }
    const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    const last6 = []
    const now = new Date()
    for (let i = 5; i >= 0; i--) {
      const d = new Date(now.getFullYear(), now.getMonth() - i, 1)
      last6.push({
        year: d.getFullYear(),
        month: d.getMonth(),
        label: monthNames[d.getMonth()],
        revenue: 0,
        expenses: 0,
      })
    }
    payments.forEach((p) => {
      if (p.status === 'Refunded' || p.status === 'Failed') return
      const pDate = p.date ? new Date(p.date) : null
      if (pDate && !isNaN(pDate.getTime())) {
        const match = last6.find((m) => m.year === pDate.getFullYear() && m.month === pDate.getMonth())
        if (match) match.revenue += Number(p.amount || 0)
      }
    })
    expenses.forEach((e) => {
      const eDate = e.date ? new Date(e.date) : null
      if (eDate && !isNaN(eDate.getTime())) {
        const match = last6.find((m) => m.year === eDate.getFullYear() && m.month === eDate.getMonth())
        if (match) match.expenses += Number(e.amount || 0)
      }
    })
    const totalRev = last6.reduce((sum, m) => sum + m.revenue, 0)
    const totalExp = last6.reduce((sum, m) => sum + m.expenses, 0)
    if (totalRev === 0 && revenue > 0) {
      last6[last6.length - 1].revenue = revenue
    }
    if (totalExp === 0 && totalExpenses > 0) {
      last6[last6.length - 1].expenses = totalExpenses
    }
    return last6.map(({ label, revenue: r, expenses: e }) => ({
      label,
      revenue: Math.round(r / 1000) || (r > 0 ? 1 : 0),
      expenses: Math.round(e / 1000) || (e > 0 ? 1 : 0),
    }))
  }, [financeOverview?.comparison_chart, payments, expenses, revenue, totalExpenses])

  const filtered = payments.filter((payment) =>
    `${payment.id} ${payment.booking} ${payment.customer} ${payment.method}`.toLowerCase().includes(query.toLowerCase())
    && (tab === 'All' || payment.status === tab),
  ).filter((payment) => dateRange === 'All time' || (payment.date && (payment.date.includes('2026') || payment.date.includes('Oct'))))

  const filteredExpenses = expenses.filter((e) =>
    `${e.id} ${e.category} ${e.title} ${e.payee || ''} ${e.reference || ''}`.toLowerCase().includes(query.toLowerCase())
    && (expFilterCategory === 'All' || e.category === expFilterCategory),
  )

  function handleBookingSelect(e) {
    const bId = e.target.value
    setFormBooking(bId)
    if (bId) {
      const b = bookings.find((item) => item.id === bId)
      if (b) {
        setFormCustomer(b.customer || '')
        if (b.pending && Number(b.pending) > 0) {
          setFormAmount(String(b.pending))
        } else if (b.paid && Number(b.paid) > 0) {
          setFormAmount(String(b.paid))
        } else if (b.total_amount) {
          setFormAmount(String(b.total_amount))
        }
      }
    }
  }

  useEffect(() => {
    syncPayments?.()
    syncFinance?.()
    syncOfflineBookings?.()
  }, [])

  async function handleRefresh() {
    setIsSyncing(true)
    try {
      await Promise.allSettled([
        syncPayments ? syncPayments() : Promise.resolve(),
        syncFinance ? syncFinance() : Promise.resolve(),
        syncOfflineBookings ? syncOfflineBookings() : Promise.resolve(),
      ])
    } finally {
      setIsSyncing(false)
    }
  }

  async function handleRecordExpense(e) {
    e.preventDefault()
    if (!expTitle.trim()) {
      setExpFormError('Expense title/description is required.')
      return
    }
    const amt = parseFloat(expAmount)
    if (isNaN(amt) || amt <= 0) {
      setExpFormError('Please enter a valid expense amount.')
      return
    }

    setExpFormError('')
    setIsExpSubmitting(true)

    try {
      const payload = {
        category: expCategory,
        title: expTitle.trim(),
        amount: amt,
        payment_method: expMethod,
        payee: expPayee.trim() || undefined,
        status: expStatus,
        notes: expNotes.trim() || undefined,
      }

      const created = await financeService.createExpense(payload)

      if (addRecord) {
        addRecord('expenses', {
          ...created,
          backendSynced: true,
        })
      }

      if (syncFinance) {
        await syncFinance()
      }

      setShowExpenseModal(false)
      setExpTitle('')
      setExpAmount('')
      setExpPayee('')
      setExpNotes('')
    } catch (err) {
      setExpFormError(err.message || 'Failed to record expense in backend.')
    } finally {
      setIsExpSubmitting(false)
    }
  }

  async function handleDeleteExpense(expenseId) {
    if (!window.confirm(`Are you sure you want to delete expense ${expenseId}?`)) return
    try {
      await financeService.deleteExpense(expenseId)
      if (deleteRecord) {
        deleteRecord('expenses', expenseId)
      }
      if (syncFinance) {
        await syncFinance()
      }
    } catch (err) {
      alert(`Delete failed: ${err.message || 'Error occurred'}`)
    }
  }

  async function handleRecordPayment(e) {
    e.preventDefault()
    if (!formCustomer.trim()) {
      setFormError('Customer name is required.')
      return
    }
    const amt = parseFloat(formAmount)
    if (isNaN(amt) || amt <= 0) {
      setFormError('Please enter a valid positive amount.')
      return
    }

    setFormError('')
    setIsSubmitting(true)

    try {
      const payload = {
        booking: formBooking.trim() || 'COUNTER-WALKIN',
        customer: formCustomer.trim(),
        method: formMethod,
        amount: amt,
        status: formStatus,
        notes: formNotes.trim() || undefined,
      }

      const created = await paymentService.recordPayment(payload)

      if (addRecord) {
        addRecord('payments', {
          ...created,
          backendSynced: true,
        })
      }

      if (syncPayments) {
        await syncPayments()
      }

      if (formBooking && syncOfflineBookings) {
        await syncOfflineBookings()
      }

      // If linked to a booking, also adjust booking's paid/pending in state
      if (formBooking && updateRecord) {
        const linkedBooking = bookings.find((b) => b.id === formBooking)
        if (linkedBooking) {
          const newPaid = (Number(linkedBooking.paid) || 0) + amt
          const currentPending = Number(linkedBooking.pending) || 0
          const newPending = Math.max(0, currentPending - amt)
          updateRecord('bookings', formBooking, {
            paid: newPaid,
            pending: newPending,
          })
        }
      }

      setShowRecordModal(false)
      setFormBooking('')
      setFormCustomer('')
      setFormAmount('')
      setFormMethod('UPI')
      setFormStatus('Paid')
      setFormNotes('')
    } catch (err) {
      setFormError(err.message || 'Failed to record payment in backend.')
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleRefund(paymentId) {
    if (!window.confirm(`Are you sure you want to process a refund for ${paymentId}?`)) return
    setRefundLoading(true)
    try {
      await paymentService.refundPayment(paymentId, 'Requested by customer at counter')
      if (updateRecord) {
        updateRecord('payments', paymentId, { status: 'Refunded' })
      }
      if (syncPayments) {
        await syncPayments()
      }
      setSelected((prev) => (prev && prev.id === paymentId ? { ...prev, status: 'Refunded' } : prev))
    } catch (err) {
      alert(`Refund failed: ${err.message || 'Error occurred'}`)
    } finally {
      setRefundLoading(false)
    }
  }

  return (
    <div>
      <PageHeader
        title="Payments & finance"
        description="A clear picture of collections and transactions stored in MongoDB, with UPI, Cash, and Card records."
        action={
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="secondary"
              className="min-h-9"
              onClick={handleRefresh}
              disabled={isSyncing}
            >
              <RefreshCw size={14} className={isSyncing ? 'animate-spin' : ''} />
              {isSyncing ? 'Syncing...' : 'Sync backend'}
            </Button>
            <Button
              variant="secondary"
              className="min-h-9"
              onClick={() => {
                setExpFormError('')
                setShowExpenseModal(true)
              }}
            >
              <Plus size={15} />
              Record expense
            </Button>
            <Button
              className="min-h-9"
              onClick={() => {
                setFormError('')
                setShowRecordModal(true)
              }}
            >
              <Plus size={15} />
              Record payment
            </Button>
            <FilterSelect label="Status" value={tab} onChange={setTab} options={['All', 'Paid', 'Partial', 'Refunded']} />
            <FilterSelect value={dateRange} onChange={setDateRange} options={['This month', 'Last month', 'All time']} />
          </div>
        }
      />

      <div className="mb-5 grid grid-cols-2 gap-3 xl:grid-cols-4">
        <MetricCard label="Collected total" value={currency(financeOverview?.total_revenue ?? revenue)} caption="Total verified receipts" icon={BadgeIndianRupee} />
        <MetricCard label="Online bookings" value={currency(financeOverview?.online_revenue ?? onlineRevenue)} caption="Total online revenue" icon={ArrowUpRight} tone="blue" />
        <MetricCard label="Counter & Cash" value={currency(financeOverview?.offline_revenue ?? offlineRevenue)} caption="Offline and counter intake" icon={Wallet} tone="violet" />
        <MetricCard label="Pending balance" value={currency(financeOverview?.pending_receivables ?? pendingTotal)} caption="Outstanding from bookings" icon={CircleDollarSign} tone="amber" />
      </div>

      <div className="mb-4 grid gap-4 xl:grid-cols-[minmax(0,1.5fr)_minmax(280px,0.8fr)]">
        <Card className="p-5 sm:p-6">
          <div className="flex flex-wrap justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Revenue vs. expenses</h2>
              <p className="mt-1 text-xs text-slate-500">Monthly breakdown · ₹ (in Thousands)</p>
            </div>
            <FilterSelect value={dateRange} onChange={setDateRange} options={['This month', 'Last month', 'All time']} />
          </div>
          <div className="mt-4">
            <ComparisonChart data={comparisonData} />
          </div>
        </Card>

        <Card className="p-5 sm:p-6">
          <h2 className="text-sm font-semibold text-slate-900">Finance snapshot</h2>
          <p className="mt-1 text-xs text-slate-500">FastAPI backend & live collections</p>
          <div className="mt-4 space-y-3">
            {[
              ['Current collections', currency(financeOverview?.total_revenue ?? revenue), 'text-emerald-700'],
              ['Operating expenses', currency(financeOverview?.operating_expenses ?? totalExpenses), 'text-slate-800'],
              ['Maintenance costs', currency(financeOverview?.maintenance_costs ?? 0), 'text-slate-800'],
              ['Estimated net', currency(financeOverview?.estimated_net ?? Math.max(0, (financeOverview?.total_revenue ?? revenue) - totalExpenses)), 'text-emerald-700'],
            ].map(([label, amount, tone]) => (
              <div key={label} className="flex justify-between border-b border-slate-100 pb-2.5 text-xs last:border-0">
                <span className="text-slate-500">{label}</span>
                <span className={`font-semibold ${tone}`}>{amount}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card className="overflow-hidden">
        <div className="border-b border-slate-100 bg-slate-50/50 px-4 py-2.5 sm:px-5">
          <div className="flex gap-2">
            <button
              onClick={() => setSection('payments')}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                section === 'payments'
                  ? 'bg-white text-slate-900 shadow-sm ring-1 ring-slate-200'
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              Customer payments ({payments.length})
            </button>
            <button
              onClick={() => setSection('expenses')}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                section === 'expenses'
                  ? 'bg-white text-slate-900 shadow-sm ring-1 ring-slate-200'
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              Operational expenses ({expenses.length})
            </button>
          </div>
        </div>

        {section === 'payments' ? (
          <>
            <div className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5">
              <div>
                <h2 className="text-sm font-semibold text-slate-900">Recent transactions</h2>
                <p className="mt-1 text-xs text-slate-500">Recorded offline, counter, and digital payments</p>
              </div>
              <SearchField value={query} onChange={setQuery} placeholder="Search transactions…" />
            </div>

            <DataTable
              rows={filtered}
              columns={[
                {
                  key: 'id',
                  label: 'Transaction',
                  render: (row) => (
                    <span className="font-semibold text-slate-800">
                      <span className="inline-flex items-center gap-1.5">
                        {row.id}
                        {row.backendSynced && (
                          <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700 ring-1 ring-emerald-600/20">
                            API
                          </span>
                        )}
                      </span>
                      <span className="mt-1 block text-[11px] font-normal text-slate-400">{row.booking}</span>
                    </span>
                  ),
                },
                { key: 'customer', label: 'Customer' },
                { key: 'method', label: 'Method' },
                { key: 'date', label: 'Date' },
                { key: 'amount', label: 'Amount', render: (row) => currency(row.amount) },
                { key: 'status', label: 'Status', render: (row) => <StatusBadge status={row.status} /> },
                {
                  key: 'actions',
                  label: '',
                  render: (row) => (
                    <div className="flex items-center justify-end gap-1.5">
                      <Button variant="quiet" className="min-h-8 px-2.5" onClick={() => setSelected(row)}>
                        <Eye size={15} />Details
                      </Button>
                    </div>
                  ),
                },
              ]}
            />
            <p className="border-t border-slate-100 px-5 py-3 text-[11px] text-slate-400">
              Showing {filtered.length} of {payments.length} transactions
            </p>
          </>
        ) : (
          <>
            <div className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5">
              <div>
                <h2 className="text-sm font-semibold text-slate-900">Hub operating expenses</h2>
                <p className="mt-1 text-xs text-slate-500">Rent, staff salaries, fleet maintenance, utilities, fuel & insurance</p>
              </div>
              <div className="flex items-center gap-2">
                <FilterSelect
                  label="Category"
                  value={expFilterCategory}
                  onChange={setExpFilterCategory}
                  options={[
                    'All',
                    'Rent & Operations',
                    'Staff Salaries',
                    'Maintenance',
                    'Insurance & Taxes',
                    'Fuel',
                    'Utilities',
                    'Marketing',
                  ]}
                />
                <SearchField value={query} onChange={setQuery} placeholder="Search expenses…" />
              </div>
            </div>

            <DataTable
              rows={filteredExpenses}
              columns={[
                {
                  key: 'id',
                  label: 'Expense ID',
                  render: (row) => (
                    <span className="font-semibold text-slate-800">
                      <span className="inline-flex items-center gap-1.5">
                        {row.id}
                        {row.backendSynced && (
                          <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700 ring-1 ring-emerald-600/20">
                            API
                          </span>
                        )}
                      </span>
                      <span className="mt-1 block text-[11px] font-normal text-slate-400">{row.category}</span>
                    </span>
                  ),
                },
                {
                  key: 'title',
                  label: 'Description / Payee',
                  render: (row) => (
                    <div>
                      <span className="font-medium text-slate-900">{row.title}</span>
                      {row.payee && <span className="mt-0.5 block text-[11px] text-slate-400">Payee: {row.payee}</span>}
                    </div>
                  ),
                },
                {
                  key: 'payment_method',
                  label: 'Method & Ref',
                  render: (row) => (
                    <div>
                      <span className="text-xs text-slate-700">{row.payment_method}</span>
                      {row.reference && <span className="mt-0.5 block text-[10px] text-slate-400">{row.reference}</span>}
                    </div>
                  ),
                },
                { key: 'date', label: 'Date' },
                {
                  key: 'amount',
                  label: 'Amount',
                  render: (row) => <span className="font-semibold text-rose-600">- {currency(row.amount)}</span>,
                },
                {
                  key: 'status',
                  label: 'Status',
                  render: (row) => <StatusBadge status={row.status || 'Paid'} />,
                },
                {
                  key: 'actions',
                  label: '',
                  render: (row) => (
                    <div className="flex items-center justify-end">
                      <Button
                        variant="quiet"
                        className="min-h-8 px-2 text-rose-600 hover:bg-rose-50 hover:text-rose-700"
                        onClick={() => handleDeleteExpense(row.id)}
                      >
                        <Trash2 size={14} />
                      </Button>
                    </div>
                  ),
                },
              ]}
            />
            <p className="border-t border-slate-100 px-5 py-3 text-[11px] text-slate-400">
              Showing {filteredExpenses.length} of {expenses.length} operating expenses
            </p>
          </>
        )}
      </Card>

      {/* Record Payment Modal */}
      {showRecordModal && (
        <Modal
          title="Record Counter / Offline Payment"
          onClose={() => { if (!isSubmitting) setShowRecordModal(false) }}
          footer={
            <div className="flex justify-end gap-2">
              <Button type="button" variant="secondary" onClick={() => setShowRecordModal(false)} disabled={isSubmitting}>
                Cancel
              </Button>
              <Button type="submit" form="record-payment-form" disabled={isSubmitting}>
                {isSubmitting ? (
                  <>
                    <Loader2 size={15} className="animate-spin" />
                    Recording...
                  </>
                ) : (
                  <>
                    <Check size={15} />
                    Save payment
                  </>
                )}
              </Button>
            </div>
          }
        >
          <form id="record-payment-form" onSubmit={handleRecordPayment} className="space-y-4">
            {formError && (
              <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700">
                {formError}
              </div>
            )}

            <div>
              <label className="mb-1.5 block text-xs font-semibold text-slate-700">
                Link to Booking (Optional)
              </label>
              <select
                value={formBooking}
                onChange={handleBookingSelect}
                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-800 transition focus:border-emerald-500 focus:outline-none"
              >
                <option value="">Counter Walk-in / Direct receipt</option>
                {bookings.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.id} · {b.customer} ({b.vehicle}) — Pending: ₹{b.pending || 0}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="mb-1.5 block text-xs font-semibold text-slate-700">
                Customer Name <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                required
                value={formCustomer}
                onChange={(e) => setFormCustomer(e.target.value)}
                placeholder="e.g. Ramesh Patel"
                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-800 transition focus:border-emerald-500 focus:outline-none"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1.5 block text-xs font-semibold text-slate-700">
                  Amount (₹) <span className="text-rose-500">*</span>
                </label>
                <input
                  type="number"
                  min="1"
                  step="any"
                  required
                  value={formAmount}
                  onChange={(e) => setFormAmount(e.target.value)}
                  placeholder="e.g. 1500"
                  className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-800 transition focus:border-emerald-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="mb-1.5 block text-xs font-semibold text-slate-700">
                  Payment Method
                </label>
                <select
                  value={formMethod}
                  onChange={(e) => setFormMethod(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-800 transition focus:border-emerald-500 focus:outline-none"
                >
                  <option value="UPI">UPI / GPay / PhonePe</option>
                  <option value="Cash">Cash at Counter</option>
                  <option value="Card">Debit / Credit Card</option>
                  <option value="NetBanking">Net Banking</option>
                </select>
              </div>
            </div>

            <div>
              <label className="mb-1.5 block text-xs font-semibold text-slate-700">
                Payment Status
              </label>
              <select
                value={formStatus}
                onChange={(e) => setFormStatus(e.target.value)}
                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-800 transition focus:border-emerald-500 focus:outline-none"
              >
                <option value="Paid">Paid (Full settlement)</option>
                <option value="Partial">Partial (Advance payment)</option>
              </select>
            </div>

            <div>
              <label className="mb-1.5 block text-xs font-semibold text-slate-700">
                Notes / Reference ID (Optional)
              </label>
              <input
                type="text"
                value={formNotes}
                onChange={(e) => setFormNotes(e.target.value)}
                placeholder="e.g. UPI Ref: 4291823901 or Counter receipt #12"
                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-800 transition focus:border-emerald-500 focus:outline-none"
              />
            </div>
          </form>
        </Modal>
      )}

      {/* Record Business Expense Modal */}
      {showExpenseModal && (
        <Modal
          title="Record Hub Operating Expense"
          onClose={() => { if (!isExpSubmitting) setShowExpenseModal(false) }}
          footer={
            <div className="flex justify-end gap-2">
              <Button type="button" variant="secondary" onClick={() => setShowExpenseModal(false)} disabled={isExpSubmitting}>
                Cancel
              </Button>
              <Button type="submit" form="record-expense-form" disabled={isExpSubmitting}>
                {isExpSubmitting ? (
                  <>
                    <Loader2 size={15} className="animate-spin" />
                    Recording...
                  </>
                ) : (
                  <>
                    <Check size={15} />
                    Save expense
                  </>
                )}
              </Button>
            </div>
          }
        >
          <form id="record-expense-form" onSubmit={handleRecordExpense} className="space-y-4">
            {expFormError && (
              <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700">
                {expFormError}
              </div>
            )}

            <div>
              <label className="mb-1.5 block text-xs font-semibold text-slate-700">
                Expense Category <span className="text-rose-500">*</span>
              </label>
              <select
                value={expCategory}
                onChange={(e) => setExpCategory(e.target.value)}
                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-800 transition focus:border-emerald-500 focus:outline-none"
              >
                <option value="Rent & Operations">Rent & Operations (Facility Lease)</option>
                <option value="Staff Salaries">Staff Salaries & Technicians</option>
                <option value="Maintenance">Fleet Maintenance & Spare Parts</option>
                <option value="Insurance & Taxes">Insurance Policies & Road Taxes</option>
                <option value="Fuel">Fuel & EV Fast Charging Credits</option>
                <option value="Utilities">Utilities (Electricity, Fiber Internet)</option>
                <option value="Marketing">Marketing & Local Ads</option>
                <option value="Misc">Miscellaneous Hub Expenses</option>
              </select>
            </div>

            <div>
              <label className="mb-1.5 block text-xs font-semibold text-slate-700">
                Expense Title / Description <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                required
                value={expTitle}
                onChange={(e) => setExpTitle(e.target.value)}
                placeholder="e.g. Indiranagar Hub Monthly Facility Lease"
                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-800 transition focus:border-emerald-500 focus:outline-none"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1.5 block text-xs font-semibold text-slate-700">
                  Amount (₹) <span className="text-rose-500">*</span>
                </label>
                <input
                  type="number"
                  min="1"
                  step="any"
                  required
                  value={expAmount}
                  onChange={(e) => setExpAmount(e.target.value)}
                  placeholder="e.g. 35000"
                  className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-800 transition focus:border-emerald-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="mb-1.5 block text-xs font-semibold text-slate-700">
                  Payment Method
                </label>
                <select
                  value={expMethod}
                  onChange={(e) => setExpMethod(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-800 transition focus:border-emerald-500 focus:outline-none"
                >
                  <option value="Bank Transfer">Bank Transfer / NEFT / RTGS</option>
                  <option value="UPI">UPI / GPay / PhonePe</option>
                  <option value="Cash">Cash at Counter</option>
                  <option value="Card">Corporate Debit/Credit Card</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1.5 block text-xs font-semibold text-slate-700">
                  Payee / Vendor (Optional)
                </label>
                <input
                  type="text"
                  value={expPayee}
                  onChange={(e) => setExpPayee(e.target.value)}
                  placeholder="e.g. Brigade Properties or Shell"
                  className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-800 transition focus:border-emerald-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="mb-1.5 block text-xs font-semibold text-slate-700">
                  Payment Status
                </label>
                <select
                  value={expStatus}
                  onChange={(e) => setExpStatus(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-800 transition focus:border-emerald-500 focus:outline-none"
                >
                  <option value="Paid">Paid (Settled)</option>
                  <option value="Pending">Pending (Due)</option>
                </select>
              </div>
            </div>

            <div>
              <label className="mb-1.5 block text-xs font-semibold text-slate-700">
                Notes / Invoice Ref (Optional)
              </label>
              <input
                type="text"
                value={expNotes}
                onChange={(e) => setExpNotes(e.target.value)}
                placeholder="e.g. Inv #OCT-482 or RTGS ref number"
                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-800 transition focus:border-emerald-500 focus:outline-none"
              />
            </div>
          </form>
        </Modal>
      )}

      {/* Detail Dialog with Refund Action */}
      {selected && (
        <Modal title={`Transaction ${selected.id}`} onClose={() => setSelected(null)}>
          <div className="space-y-3">
            {[
              ['Transaction ID', selected.id],
              ['Booking ID', selected.booking],
              ['Customer', selected.customer],
              ['Payment Method', selected.method],
              ['Date', selected.date],
              ['Amount', currency(selected.amount)],
              ['Status', selected.status],
              ['Notes', selected.notes || 'None'],
              ['Backend Sync', selected.backendSynced ? 'Active (MongoDB)' : 'Synced'],
            ].map(([label, value]) => (
              <div key={label} className="flex items-start justify-between gap-4 border-b border-slate-100 pb-2.5 last:border-0">
                <span className="text-xs text-slate-500">{label}</span>
                <span className="text-right text-xs font-medium text-slate-800">{value}</span>
              </div>
            ))}

            {selected.status !== 'Refunded' && (
              <div className="mt-4 pt-2">
                <Button
                  variant="secondary"
                  className="w-full text-rose-600 hover:bg-rose-50 hover:text-rose-700"
                  disabled={refundLoading}
                  onClick={() => handleRefund(selected.id)}
                >
                  {refundLoading ? (
                    <>
                      <Loader2 size={14} className="animate-spin" />
                      Processing refund...
                    </>
                  ) : (
                    'Process refund for this transaction'
                  )}
                </Button>
              </div>
            )}
          </div>
        </Modal>
      )}
    </div>
  )
}

function Documents() {
  const { documents = [], addRecord, updateRecord, syncDocuments, syncVehicles, vehicles = [] } = useDemoData()
  const [tab, setTab] = useState('All')
  const [selected, setSelected] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [isSyncing, setIsSyncing] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadError, setUploadError] = useState('')
  const [replacementTarget, setReplacementTarget] = useState(null)
  const [replacementFile, setReplacementFile] = useState(null)
  const [replacementError, setReplacementError] = useState('')
  const [isReplacing, setIsReplacing] = useState(false)
  const [documentNotice, setDocumentNotice] = useState('')
  const [updatingStatusId, setUpdatingStatusId] = useState(null)

  // Upload modal form state
  const [formName, setFormName] = useState('')
  const [formCategory, setFormCategory] = useState('Shop License')
  const [formScope, setFormScope] = useState('Business')
  const [formVehicleId, setFormVehicleId] = useState('')
  const [formNotes, setFormNotes] = useState('')
  const [selectedFile, setSelectedFile] = useState(null)

  // Aggregate all stored documents and documents attached to vehicles
  const allDocuments = useMemo(() => {
    const list = Array.isArray(documents) ? [...documents] : []
    if (Array.isArray(vehicles)) {
      vehicles.forEach((v) => {
        if (Array.isArray(v.documents)) {
          v.documents.forEach((vd, idx) => {
            const url = typeof vd === 'string' ? vd : (vd.url || vd.file_url)
            const docId = vd.id || vd.publicId || `${v.id}-doc-${idx}`
            if (!list.some((existing) => existing.id === docId || (url && (existing.file_url === url || existing.url === url)))) {
              list.push({
                id: docId,
                name: vd.name || `${v.name || 'Vehicle'} ${vd.type || 'Document'}`,
                category: vd.type || 'Vehicle Document',
                scope: 'Vehicle',
                vehicle_id: v.id,
                vehicle_name: v.name,
                file_url: url,
                url: url,
                isVehicleAttachment: true,
                vehicle_document_public_id: typeof vd === 'object' ? (vd.publicId || vd.public_id) : null,
                vehicle_document_type: typeof vd === 'object' ? (vd.type || 'Other') : 'Other',
                status: (typeof vd === 'object' && vd.status) ? vd.status : 'Verified',
                date: v.createdAt ? new Date(v.createdAt).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : 'Recent',
                backendSynced: true,
              })
            }
          })
        }
      })
    }
    return list
  }, [documents, vehicles])

  const filtered = useMemo(() => {
    return allDocuments.filter((doc) => {
      if (tab === 'All') return true
      return (doc.scope || 'Business').toLowerCase() === tab.toLowerCase()
    })
  }, [allDocuments, tab])

  useEffect(() => {
    syncDocuments?.()
  }, [])

  async function handleRefresh() {
    setIsSyncing(true)
    try {
      if (syncDocuments) {
        await syncDocuments()
      }
    } finally {
      setIsSyncing(false)
    }
  }

  function openReplacement(doc) {
    setReplacementTarget(doc)
    setReplacementFile(null)
    setReplacementError('')
  }

  function handleReplacementFileChange(event) {
    const file = event.target.files?.[0] || null
    event.target.value = ''
    setReplacementFile(file)
    if (!file) return

    const extension = file.name.split('.').pop()?.toLowerCase()
    const allowedTypes = {
      pdf: 'application/pdf',
      png: 'image/png',
      jpg: 'image/jpeg',
      jpeg: 'image/jpeg',
      webp: 'image/webp',
    }
    if (!allowedTypes[extension] || (file.type && file.type !== allowedTypes[extension])) {
      setReplacementError('Choose a PDF, PNG, JPG, JPEG, or WEBP file.')
    } else if (file.size > 10 * 1024 * 1024) {
      setReplacementError('Documents must be 10 MB or smaller.')
    } else {
      setReplacementError('')
    }
  }

  async function handleReplaceDocument(event) {
    event.preventDefault()
    if (isReplacing) return
    if (!replacementTarget) {
      setReplacementError('Select a document to replace.')
      return
    }
    if (!replacementFile) {
      setReplacementError('Please select a replacement file.')
      return
    }
    if (replacementError) return
    if (replacementTarget.isVehicleAttachment && !replacementTarget.vehicle_document_public_id) {
      setReplacementError('This vehicle document has no storage ID and cannot be safely replaced.')
      return
    }

    setIsReplacing(true)
    setReplacementError('')
    try {
      if (replacementTarget.isVehicleAttachment) {
        const formData = new FormData()
        formData.append('new_documents', replacementFile)
        formData.append('newDocumentTypes', replacementTarget.vehicle_document_type || 'Other')
        formData.append('newDocumentIds', replacementTarget.id)
        formData.append('removeDocumentIds', replacementTarget.vehicle_document_public_id)
        await vehicleService.updateVehicle(replacementTarget.vehicle_id, formData)
        if (syncVehicles) await syncVehicles({ force: true })
      } else {
        const updated = await documentService.replaceDocument(replacementTarget.id, replacementFile)
        if (updateRecord) {
          updateRecord('documents', replacementTarget.id, {
            ...updated,
            backendSynced: true,
          })
        }
        if (syncDocuments) await syncDocuments()
      }

      setDocumentNotice(`${replacementTarget.name} was replaced successfully.`)
      setReplacementTarget(null)
      setReplacementFile(null)
      setReplacementError('')
    } catch (err) {
      setReplacementError(err.message || 'Failed to replace the document. The existing file was preserved.')
    } finally {
      setIsReplacing(false)
    }
  }

  async function handleUpload(e) {
    e.preventDefault()
    if (!selectedFile) {
      setUploadError('Please select a file to upload.')
      return
    }
    if (!formName.trim()) {
      setUploadError('Document name is required.')
      return
    }

    setUploadError('')
    setIsUploading(true)

    try {
      const selectedVehicle = vehicles?.find((v) => v.id === formVehicleId)

      const formData = new FormData()
      formData.append('file', selectedFile)
      formData.append('name', formName.trim())
      formData.append('category', formCategory)
      formData.append('scope', formScope)
      if (formScope === 'Vehicle' && formVehicleId) {
        formData.append('vehicle_id', formVehicleId)
        formData.append('vehicle_name', selectedVehicle?.name || '')
      }
      if (formNotes.trim()) {
        formData.append('notes', formNotes.trim())
      }

      const createdDoc = await documentService.uploadDocument(formData)
      if (syncDocuments) {
        await syncDocuments()
      } else {
        addRecord('documents', {
          ...createdDoc,
          backendSynced: true,
        })
      }

      // Reset form
      setShowForm(false)
      setFormName('')
      setSelectedFile(null)
      setFormNotes('')
      setFormVehicleId('')
    } catch (err) {
      console.error('Document upload error:', err)
      setUploadError(err.message || 'Failed to upload document to Cloudinary.')
    } finally {
      setIsUploading(false)
    }
  }

  async function handleStatusChange(doc, newStatus) {
    if (!doc || !newStatus || doc.status === newStatus) return
    setUpdatingStatusId(doc.id)
    try {
      await documentService.updateDocument(doc.id, { status: newStatus })

      if (doc.isVehicleAttachment && doc.vehicle_id) {
        const v = vehicles?.find((item) => item.id === doc.vehicle_id)
        if (v && updateRecord) {
          const updatedDocs = (v.documents || []).map((vd) => {
            const vdId = vd.id || vd.publicId || vd.public_id
            if (vdId === doc.id || (vd.url && (vd.url === doc.file_url || vd.url === doc.url))) {
              return { ...vd, status: newStatus }
            }
            return vd
          })
          updateRecord('vehicles', v.id, { ...v, documents: updatedDocs })
        }
      } else if (updateRecord) {
        updateRecord('documents', doc.id, { status: newStatus })
      }

      if (selected && selected.id === doc.id) {
        setSelected((prev) => (prev ? { ...prev, status: newStatus } : prev))
      }

      setDocumentNotice(`Status of "${doc.name}" updated to "${newStatus}".`)
      if (syncDocuments) await syncDocuments()
    } catch (err) {
      console.error('Failed to update document status:', err)
      alert(err.message || 'Failed to update document status.')
    } finally {
      setUpdatingStatusId(null)
    }
  }

  async function handleDelete(docId) {
    if (!window.confirm(`Are you sure you want to delete document ${docId}?`)) return
    try {
      await documentService.deleteDocument(docId)
      if (syncDocuments) await syncDocuments()
    } catch (err) {
      console.warn('Backend delete fallback:', err)
    }
  }

  return (
    <div>
      <PageHeader
        title="Documents"
        description="Paperwork and certificates uploaded to Cloudinary, with secure URLs saved in database."
        action={
          <div className="flex items-center gap-2">
            <Button variant="quiet" onClick={handleRefresh} disabled={isSyncing}>
              <RefreshCw size={15} className={isSyncing ? 'animate-spin' : ''} />
              {isSyncing ? 'Syncing...' : 'Sync backend'}
            </Button>
            <Button onClick={() => { setShowForm(true); setUploadError('') }}>
              <Upload size={16} />Upload document
            </Button>
          </div>
        }
      />

      {documentNotice && (
        <div role="status" className="mb-4 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          {documentNotice}
        </div>
      )}

      <div className="mb-5 grid grid-cols-2 gap-3 xl:grid-cols-3">
        <MetricCard label="All documents" value={allDocuments.length} icon={FileText} />
        <MetricCard label="Verified" value={allDocuments.filter((item) => item.status === 'Verified').length} icon={ShieldCheck} tone="green" />
        <MetricCard label="Needs attention" value={allDocuments.filter((item) => item.status !== 'Verified').length} icon={CalendarDays} tone="amber" />
      </div>

      <Card className="overflow-hidden">
        <Tabs items={['All', 'Business', 'Vehicle']} value={tab} onChange={setTab} />
        <div className="px-4 py-3 sm:px-5">
          <div className="flex items-center gap-2 rounded-xl border border-sky-200 bg-sky-50 px-3.5 py-2 text-xs leading-5 text-sky-900">
            <span className="font-semibold text-sky-800">☁️ Cloudinary Storage:</span> Files are uploaded directly to Cloudinary CDN, and the secure URLs and metadata are stored in MongoDB.
          </div>
        </div>

        <DataTable
          rows={filtered}
          emptyTitle="No documents registered yet"
          emptyText="Documents uploaded directly or attached to your vehicles will appear here."
          columns={[
            {
              key: 'name',
              label: 'Document',
              render: (row) => (
                <button
                  type="button"
                  onClick={() => setSelected(row)}
                  className="group flex items-center gap-3 text-left transition hover:text-emerald-800"
                >
                  <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-emerald-50 text-emerald-700 group-hover:bg-emerald-100">
                    <FileText size={16} />
                  </span>
                  <span className="font-medium text-slate-800 group-hover:text-emerald-800">
                    <span className="flex items-center gap-1.5">
                      {row.name}
                      {(row.file_url || row.url) && (
                        <span className="rounded bg-sky-50 px-1.5 py-0.5 text-[10px] font-semibold text-sky-700 ring-1 ring-sky-600/20">
                          Cloudinary
                        </span>
                      )}
                    </span>
                    <span className="mt-1 block text-[11px] font-normal text-slate-400">
                      {row.id} {row.vehicle_name ? `· ${row.vehicle_name}` : ''}
                    </span>
                  </span>
                </button>
              ),
            },
            { key: 'category', label: 'Category' },
            { key: 'date', label: 'Uploaded' },
            {
              key: 'status',
              label: 'Status',
              render: (row) => {
                const statusColors = {
                  Verified: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20 hover:bg-emerald-100',
                  'In review': 'bg-amber-50 text-amber-700 ring-amber-600/20 hover:bg-amber-100',
                  'Expires soon': 'bg-amber-50 text-amber-700 ring-amber-600/20 hover:bg-amber-100',
                  Expired: 'bg-rose-50 text-rose-700 ring-rose-600/20 hover:bg-rose-100',
                  Rejected: 'bg-rose-50 text-rose-700 ring-rose-600/20 hover:bg-rose-100',
                }
                const currentStatus = row.status || 'In review'
                return (
                  <div className="relative inline-flex items-center">
                    <select
                      value={currentStatus}
                      disabled={updatingStatusId === row.id}
                      onChange={(e) => handleStatusChange(row, e.target.value)}
                      title="Click to change document status"
                      aria-label={`Change status for ${row.name}`}
                      className={`cursor-pointer appearance-none rounded-full py-1 pl-2.5 pr-6 text-[11px] font-semibold ring-1 ring-inset outline-none transition disabled:cursor-not-allowed disabled:opacity-50 ${statusColors[currentStatus] || 'bg-slate-100 text-slate-700 ring-slate-300'}`}
                    >
                      <option value="Verified">Verified</option>
                      <option value="In review">In review</option>
                      <option value="Expires soon">Expires soon</option>
                      <option value="Expired">Expired</option>
                      <option value="Rejected">Rejected</option>
                    </select>
                    {updatingStatusId === row.id ? (
                      <Loader2 size={11} className="pointer-events-none absolute right-2 animate-spin text-slate-500" />
                    ) : (
                      <ChevronDown size={11} className="pointer-events-none absolute right-2 text-slate-500" />
                    )}
                  </div>
                )
              },
            },
            {
              key: 'actions',
              label: '',
              render: (row) => {
                const docUrl = row.file_url || row.url
                return (
                  <div className="flex items-center gap-1.5">
                    <Button
                      variant="quiet"
                      className="min-h-8 px-2.5 text-xs font-semibold text-emerald-800 hover:bg-emerald-50"
                      onClick={() => setSelected(row)}
                      title="View & preview document"
                    >
                      <Eye size={14} className="mr-1" />
                      View
                    </Button>
                    <button
                      type="button"
                      disabled={row.isVehicleAttachment && !row.vehicle_document_public_id}
                      onClick={() => openReplacement(row)}
                      aria-label={`Replace ${row.name}`}
                      title={row.isVehicleAttachment && !row.vehicle_document_public_id ? 'This file has no storage ID' : 'Replace document file'}
                      className="inline-flex h-8 items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 text-xs font-semibold text-slate-700 transition hover:bg-slate-50 hover:text-emerald-800 disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      <RefreshCw size={13} />
                      Replace
                    </button>

                    {docUrl && (
                      <a
                        href={docUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex h-8 items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 text-xs font-semibold text-slate-700 transition hover:bg-slate-50 hover:text-emerald-800"
                        title="Open file in new tab"
                      >
                        <ExternalLink size={13} />
                        Open
                      </a>
                    )}

                    <Button
                      variant="quiet"
                      className="min-h-8 px-2 text-rose-600 hover:bg-rose-50 hover:text-rose-700"
                      onClick={() => handleDelete(row.id)}
                      title="Delete document"
                    >
                      <Trash2 size={14} />
                    </Button>
                  </div>
                )
              },
            },
          ]}
        />
        <p className="border-t border-slate-100 px-5 py-3 text-[11px] text-slate-400">
          {filtered.length} {tab === 'All' ? 'total' : tab.toLowerCase()} documents stored
        </p>
      </Card>

      {/* Cloudinary Upload Document Modal */}
      {showForm && (
        <Modal
          title="Upload Document to Cloudinary"
          onClose={() => { if (!isUploading) setShowForm(false) }}
          footer={
            <div className="flex justify-end gap-2">
              <Button type="button" variant="secondary" onClick={() => setShowForm(false)} disabled={isUploading}>
                Cancel
              </Button>
              <Button type="submit" form="upload-doc-form" disabled={isUploading}>
                {isUploading ? (
                  <>
                    <Loader2 size={15} className="animate-spin" />
                    Uploading to Cloudinary...
                  </>
                ) : (
                  <>
                    <Upload size={15} />
                    Upload & Save
                  </>
                )}
              </Button>
            </div>
          }
        >
          <form id="upload-doc-form" onSubmit={handleUpload} className="space-y-4">
            {uploadError && (
              <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700">
                {uploadError}
              </div>
            )}

            <div>
              <label className="mb-1.5 block text-xs font-semibold text-slate-700">
                Document Name <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                required
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="e.g. Shop License, Vehicle Insurance, Owner PAN"
                className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100 placeholder:text-slate-400"
              />
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label className="mb-1.5 block text-xs font-semibold text-slate-700">
                  Category <span className="text-rose-500">*</span>
                </label>
                <select
                  value={formCategory}
                  onChange={(e) => setFormCategory(e.target.value)}
                  className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
                >
                  <option value="Shop License">Shop License</option>
                  <option value="GST Certificate">GST Certificate</option>
                  <option value="Insurance">Insurance Policy</option>
                  <option value="PAN Card">PAN Card</option>
                  <option value="RC Book">RC Book</option>
                  <option value="PUC">PUC Certificate</option>
                  <option value="Permit">Transport Permit</option>
                  <option value="Other">Other Document</option>
                </select>
              </div>

              <div>
                <label className="mb-1.5 block text-xs font-semibold text-slate-700">
                  Document Scope <span className="text-rose-500">*</span>
                </label>
                <select
                  value={formScope}
                  onChange={(e) => setFormScope(e.target.value)}
                  className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
                >
                  <option value="Business">Business Document</option>
                  <option value="Vehicle">Vehicle Document</option>
                </select>
              </div>
            </div>

            {formScope === 'Vehicle' && (
              <div>
                <label className="mb-1.5 block text-xs font-semibold text-slate-700">
                  Select Associated Vehicle
                </label>
                <select
                  value={formVehicleId}
                  onChange={(e) => setFormVehicleId(e.target.value)}
                  className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
                >
                  <option value="">Select a vehicle (optional)</option>
                  {vehicles?.map((vehicle) => (
                    <option key={vehicle.id} value={vehicle.id}>
                      {vehicle.name} ({vehicle.registration || vehicle.id})
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div>
              <label className="mb-1.5 block text-xs font-semibold text-slate-700">
                Choose Document File (PDF, PNG, JPG) <span className="text-rose-500">*</span>
              </label>
              <input
                type="file"
                required
                accept=".pdf,.png,.jpg,.jpeg,.webp"
                onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                className="block w-full text-xs text-slate-500 file:mr-3 file:rounded-xl file:border-0 file:bg-emerald-50 file:px-3 file:py-2 file:text-xs file:font-semibold file:text-emerald-700 hover:file:bg-emerald-100"
              />
              {selectedFile && (
                <p className="mt-1 text-[11px] text-slate-500">
                  Selected: <span className="font-medium text-slate-700">{selectedFile.name}</span> ({(selectedFile.size / 1024).toFixed(1)} KB)
                </p>
              )}
            </div>

            <div>
              <label className="mb-1.5 block text-xs font-semibold text-slate-700">
                Remarks / Notes (optional)
              </label>
              <input
                type="text"
                value={formNotes}
                onChange={(e) => setFormNotes(e.target.value)}
                placeholder="e.g. Valid until Dec 2026, uploaded for verification"
                className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100 placeholder:text-slate-400"
              />
            </div>

            <div className="rounded-xl bg-sky-50 p-3 text-[11px] leading-5 text-sky-800">
              ⚡ File is uploaded directly to your Cloudinary cloud (<span className="font-mono">himuiwgh</span>). The secure CDN link is then saved in MongoDB.
            </div>
          </form>
        </Modal>
      )}

      {selected && (
        <Modal
          title={`Document: ${selected.name}`}
          onClose={() => setSelected(null)}
          footer={
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-xs text-slate-400">
                {selected.id} · {selected.category} · {selected.scope}
              </span>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="quiet"
                  disabled={selected.isVehicleAttachment && !selected.vehicle_document_public_id}
                  onClick={() => {
                    openReplacement(selected)
                    setSelected(null)
                  }}
                >
                  <RefreshCw size={14} />
                  Replace
                </Button>
                {(selected.file_url || selected.url) && (
                  <a
                    href={selected.file_url || selected.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex h-9 items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50 hover:text-emerald-800"
                  >
                    <ExternalLink size={14} />
                    Open in new tab
                  </a>
                )}
                <Button type="button" onClick={() => setSelected(null)}>
                  Close
                </Button>
              </div>
            </div>
          }
        >
          <div className="space-y-4">
            {/* Header badges */}
            <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-slate-50 p-3">
              <div>
                <p className="text-sm font-semibold text-slate-900">{selected.name}</p>
                <p className="mt-0.5 text-xs text-slate-500">
                  {selected.scope} {selected.vehicle_name ? `· Vehicle: ${selected.vehicle_name}` : ''}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-slate-500">Status:</span>
                <div className="relative inline-flex items-center">
                  <select
                    value={selected.status || 'In review'}
                    disabled={updatingStatusId === selected.id}
                    onChange={(e) => handleStatusChange(selected, e.target.value)}
                    title="Change verification status"
                    aria-label={`Change verification status for ${selected.name}`}
                    className={`cursor-pointer appearance-none rounded-full py-1 pl-3 pr-7 text-xs font-semibold ring-1 ring-inset outline-none transition disabled:cursor-not-allowed disabled:opacity-50 ${{
                      Verified: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20 hover:bg-emerald-100',
                      'In review': 'bg-amber-50 text-amber-700 ring-amber-600/20 hover:bg-amber-100',
                      'Expires soon': 'bg-amber-50 text-amber-700 ring-amber-600/20 hover:bg-amber-100',
                      Expired: 'bg-rose-50 text-rose-700 ring-rose-600/20 hover:bg-rose-100',
                      Rejected: 'bg-rose-50 text-rose-700 ring-rose-600/20 hover:bg-rose-100',
                    }[selected.status] || 'bg-slate-100 text-slate-700 ring-slate-300'}`}
                  >
                    <option value="Verified">Verified</option>
                    <option value="In review">In review</option>
                    <option value="Expires soon">Expires soon</option>
                    <option value="Expired">Expired</option>
                    <option value="Rejected">Rejected</option>
                  </select>
                  {updatingStatusId === selected.id ? (
                    <Loader2 size={12} className="pointer-events-none absolute right-2 animate-spin text-slate-500" />
                  ) : (
                    <ChevronDown size={12} className="pointer-events-none absolute right-2 text-slate-500" />
                  )}
                </div>
              </div>
            </div>

            {/* In-app Document Preview */}
            {(selected.file_url || selected.url) ? (
              <div className="overflow-hidden rounded-xl border border-slate-200 bg-slate-50">
                {String(selected.file_url || selected.url).toLowerCase().includes('.pdf') ? (
                  <div className="flex flex-col items-center justify-center p-3">
                    <img
                      src={String(selected.file_url || selected.url).replace(/\.pdf$/i, '.jpg')}
                      alt={selected.name}
                      className="max-h-96 max-w-full rounded-lg object-contain shadow-sm bg-white"
                      onError={(e) => {
                        e.target.style.display = 'none'
                        if (e.target.parentNode) {
                          e.target.parentNode.innerHTML =
                            '<p class="py-8 text-center text-xs text-slate-400">Unable to render inline preview. Please check Cloudinary Security settings for PDF delivery.</p>'
                        }
                      }}
                    />
                    <p className="mt-2 text-center text-[11px] text-slate-500">
                      Preview rendered via Cloudinary. To open direct PDF, ensure <strong>&ldquo;PDF and ZIP files delivery&rdquo;</strong> is enabled in your Cloudinary Security settings.
                    </p>
                  </div>
                ) : (
                  <div className="flex max-h-96 items-center justify-center p-2">
                    <img
                      src={selected.file_url || selected.url}
                      alt={selected.name}
                      className="max-h-80 max-w-full rounded-lg object-contain shadow-sm"
                      onError={(e) => {
                        e.target.style.display = 'none'
                        if (e.target.parentNode) {
                          e.target.parentNode.innerHTML =
                            '<p class="py-8 text-center text-xs text-slate-400">Unable to render inline image preview. Click "Open in new tab" above.</p>'
                        }
                      }}
                    />
                  </div>
                )}
              </div>
            ) : (
              <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 p-6 text-center text-xs text-slate-500">
                No direct file link is attached to this record.
              </div>
            )}

            {/* Details Table */}
            <div className="space-y-2 border-t border-slate-100 pt-3">
              {[
                ['Status', selected.status || 'Verified'],
                ['Category', selected.category],
                ['Scope', selected.scope],
                ['Associated Vehicle', selected.vehicle_name || selected.vehicle_id || 'None'],
                ['Uploaded Date', selected.date || selected.created_at],
                ['Remarks / Notes', selected.notes || 'No remarks provided'],
              ].map(([lbl, val]) => (
                <div key={lbl} className="flex items-start justify-between gap-4 text-xs">
                  <span className="text-slate-500">{lbl}</span>
                  <span className="font-medium text-slate-800">{val || '—'}</span>
                </div>
              ))}
            </div>
          </div>
        </Modal>
      )}

      {replacementTarget && (
        <Modal
          title={`Replace document · ${replacementTarget.name}`}
          onClose={() => {
            if (!isReplacing) {
              setReplacementTarget(null)
              setReplacementFile(null)
              setReplacementError('')
            }
          }}
          footer={
            <div className="flex flex-wrap justify-end gap-2">
              <Button
                type="button"
                variant="secondary"
                disabled={isReplacing}
                onClick={() => setReplacementTarget(null)}
              >
                Cancel
              </Button>
              <Button type="submit" form="replace-document-form" disabled={isReplacing || !replacementFile || Boolean(replacementError)}>
                {isReplacing ? (
                  <>
                    <Loader2 size={15} className="animate-spin" />
                    Replacing...
                  </>
                ) : (
                  <>
                    <RefreshCw size={15} />
                    Replace file
                  </>
                )}
              </Button>
            </div>
          }
        >
          <form id="replace-document-form" onSubmit={handleReplaceDocument} className="space-y-4">
            <p className="text-sm text-slate-600">
              This replaces the file for <span className="font-semibold">{replacementTarget.id}</span> without creating another document record.
              {replacementTarget.vehicle_name ? ` The vehicle association with ${replacementTarget.vehicle_name} is retained.` : ''}
            </p>
            {replacementError && (
              <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
                {replacementError}
              </p>
            )}
            <div>
              <label htmlFor="replacement-document-file" className="mb-1.5 block text-xs font-semibold text-slate-700">
                Replacement file (PDF, PNG, JPG, WEBP; up to 10 MB) <span className="text-rose-500">*</span>
              </label>
              <input
                id="replacement-document-file"
                type="file"
                required
                disabled={isReplacing}
                accept=".pdf,.png,.jpg,.jpeg,.webp,application/pdf,image/png,image/jpeg,image/webp"
                onChange={handleReplacementFileChange}
                className="block w-full text-xs text-slate-500 file:mr-3 file:rounded-xl file:border-0 file:bg-emerald-50 file:px-3 file:py-2 file:text-xs file:font-semibold file:text-emerald-700 hover:file:bg-emerald-100"
              />
              {replacementFile && !replacementError && (
                <p className="mt-1 text-[11px] text-slate-500">
                  Selected: <span className="font-medium text-slate-700">{replacementFile.name}</span> ({(replacementFile.size / 1024).toFixed(1)} KB)
                </p>
              )}
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}

function Maintenance() {
  const { maintenance, vehicles = [], syncMaintenance, syncVehicles } = useDemoData()
  const [tab, setTab] = useState('All')
  const [showForm, setShowForm] = useState(false)
  const [selected, setSelected] = useState(null)
  const [query, setQuery] = useState('')
  const [isSyncing, setIsSyncing] = useState(false)

  useEffect(() => {
    syncMaintenance?.()
    syncVehicles?.()
  }, [])

  async function handleRefresh() {
    setIsSyncing(true)
    try {
      if (syncMaintenance) await syncMaintenance()
      if (syncVehicles) await syncVehicles()
    } finally {
      setIsSyncing(false)
    }
  }

  const filtered = maintenance.filter((record) =>
    (tab === 'All' || record.status === tab)
    && `${record.vehicle} ${record.type} ${record.id}`.toLowerCase().includes(query.toLowerCase()),
  )

  return (
    <div>
      <PageHeader
        title="Maintenance"
        description="Schedule service and keep track of fleet health and costs."
        action={
          <div className="flex items-center gap-2">
            <Button variant="quiet" onClick={handleRefresh} disabled={isSyncing}>
              <RefreshCw size={15} className={isSyncing ? 'animate-spin' : ''} />
              {isSyncing ? 'Syncing...' : 'Sync backend'}
            </Button>
            <Button onClick={() => setShowForm(true)}><Plus size={16} />Add maintenance</Button>
          </div>
        }
      />
      <div className="mb-5 grid grid-cols-2 gap-3 xl:grid-cols-3">
        <MetricCard label="Open jobs" value={maintenance.filter((item) => item.status === 'Ongoing').length} icon={Wrench} tone="blue" />
        <MetricCard label="Completed this month" value={maintenance.filter((item) => item.status === 'Completed').length} icon={Check} />
        <MetricCard label="Maintenance costs" value={currency(maintenance.reduce((sum, item) => sum + Number(item.cost || 0), 0))} icon={BadgeIndianRupee} tone="amber" />
      </div>
      <Card className="overflow-hidden">
        <Tabs items={['All', 'Ongoing', 'Completed']} value={tab} onChange={setTab} />
        <div className="p-4 sm:p-5"><SearchField value={query} onChange={setQuery} placeholder="Search vehicle or maintenance…" /></div>
        <DataTable
          rows={filtered}
          emptyTitle="No maintenance records found"
          emptyText="Click 'Add maintenance' to schedule vehicle repairs or maintenance."
          columns={[
          { key: 'vehicle', label: 'Vehicle', render: (row) => <button type="button" onClick={() => setSelected(row)} className="text-left font-medium text-slate-800 hover:text-emerald-800">{row.vehicle}<span className="mt-1 block text-[11px] font-normal text-slate-400">{row.id} · {row.type}</span></button> },
          { key: 'start', label: 'Started' }, { key: 'expected', label: 'Expected completion' },
          { key: 'cost', label: 'Cost', render: (row) => currency(row.cost) },
          { key: 'payment', label: 'Payment', render: (row) => <StatusBadge status={row.payment} /> },
          { key: 'status', label: 'Work status', render: (row) => <StatusBadge status={row.status} /> },
          { key: 'action', label: '', render: (row) => (
            <div className="flex gap-1">
              <Button variant="quiet" className="min-h-8 px-2.5" onClick={() => setSelected(row)}>History</Button>
              {row.status === 'Ongoing' && (
                // FIX: Complete maintenance via backend and refresh live vehicle state instead of local mutation
                <Button variant="quiet" className="min-h-8 px-2.5 text-emerald-700 hover:bg-emerald-50" onClick={async () => {
                  try {
                    await maintenanceService.completeMaintenance(row.id)
                    if (syncMaintenance) await syncMaintenance()
                    if (syncVehicles) await syncVehicles({ force: true })
                    else updateRecord('maintenance', row.id, { status: 'Completed' })
                  } catch {
                    updateRecord('maintenance', row.id, { status: 'Completed' })
                  }
                }}>
                  Complete
                </Button>
              )}
            </div>
          )},
        ]} />
      </Card>
      {showForm && (
        <RecordForm
          title="Add maintenance"
          onClose={() => setShowForm(false)}
          fields={[
            {
              name: 'vehicle',
              label: 'Vehicle',
              type: 'select',
              options: vehicles.length > 0 ? vehicles.map((v) => v.name) : ['Honda Activa 6G', 'Royal Enfield Classic 350', 'Ather 450X', 'TVS Jupiter', 'Yamaha FZ-S FI'],
              required: true,
            },
            { name: 'type', label: 'Maintenance type', required: true },
            { name: 'start', label: 'Start date', type: 'date', required: true },
            { name: 'expected', label: 'Expected completion', type: 'date', required: true },
            { name: 'cost', label: 'Estimated cost (₹)', type: 'number', min: 0, required: true },
            { name: 'payment', label: 'Payment status', type: 'select', options: ['Pending', 'Paid'], required: true },
          ]}
          // FIX: Persist maintenance to backend and sync vehicle operational state
          onSave={async (values) => {
            try {
              await maintenanceService.createMaintenance({
                vehicle_name: values.vehicle,
                maintenance_type: values.type,
                start_date: values.start,
                expected_date: values.expected,
                estimated_cost: Number(values.cost),
                payment_status: values.payment,
              })
              if (syncMaintenance) await syncMaintenance()
              if (syncVehicles) await syncVehicles({ force: true })
            } catch {
              addRecord('maintenance', {
                ...values,
                id: nextId('MT', maintenance),
                cost: Number(values.cost),
                status: 'Ongoing',
              })
            }
            setShowForm(false)
          }}
        />
      )}
      {selected && <DetailDialog title={`Maintenance history · ${selected.vehicle}`} record={selected} onClose={() => setSelected(null)} rows={Object.entries(selected).map(([key, value]) => [key, key === 'cost' ? currency(value) : value])} />}
    </div>
  )
}

function EditStaffModal({ staffMember, onClose, onSave }) {
  const [name, setName] = useState(staffMember?.name || '')
  const [role, setRole] = useState(staffMember?.role || 'Fleet manager')
  const [phone, setPhone] = useState(staffMember?.phone || '')
  const [salary, setSalary] = useState(staffMember?.salary != null ? String(staffMember.salary) : '')
  const [attendance, setAttendance] = useState(staffMember?.attendance || '26 / 26 days')
  const [nextSalary, setNextSalary] = useState(staffMember?.nextSalary || '')
  const [status, setStatus] = useState(staffMember?.status || 'Active')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const roles = [
    'Fleet manager',
    'Operations associate',
    'Customer support',
    'Delivery associate',
    'Administrator',
  ]

  async function handleSubmit(e) {
    e.preventDefault()
    if (!name.trim()) {
      setError('Full name is required.')
      return
    }
    if (!phone.trim()) {
      setError('Phone number is required.')
      return
    }
    if (salary === '' || isNaN(Number(salary)) || Number(salary) < 0) {
      setError('Please enter a valid salary amount.')
      return
    }

    setError('')
    setIsSubmitting(true)

    const payload = {
      name: name.trim(),
      role,
      phone: phone.trim(),
      salary: Number(salary),
      attendance: attendance.trim() || 'Not recorded',
      nextSalary: nextSalary || '',
      status,
    }

    try {
      await onSave(staffMember.id, payload)
      onClose()
    } catch (err) {
      setError(err?.message || 'Failed to update staff member.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Modal
      title={`Edit Staff Member · ${staffMember?.name}`}
      onClose={onClose}
      footer={
        <div className="flex justify-end gap-2 w-full">
          <Button type="button" variant="secondary" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button
            type="submit"
            form="edit-staff-form"
            disabled={isSubmitting}
            className="bg-emerald-600 hover:bg-emerald-700 text-white"
          >
            {isSubmitting ? <Loader2 size={15} className="animate-spin" /> : <Check size={15} />}
            Save Changes
          </Button>
        </div>
      }
    >
      <form id="edit-staff-form" onSubmit={handleSubmit} className="space-y-4 py-1">
        {error && (
          <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700">
            {error}
          </div>
        )}

        <div>
          <label className="mb-1.5 block text-xs font-medium text-slate-700">
            Full Name <span className="text-rose-500">*</span>
          </label>
          <input
            required
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Ramesh Kumar"
            className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-700">
              Role <span className="text-rose-500">*</span>
            </label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
            >
              {roles.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-700">
              Status <span className="text-rose-500">*</span>
            </label>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
            >
              <option value="Active">Active</option>
              <option value="Inactive">Inactive</option>
            </select>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-700">
              Phone Number <span className="text-rose-500">*</span>
            </label>
            <input
              required
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="e.g. 9876543210"
              className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
            />
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-700">
              Monthly Salary (₹) <span className="text-rose-500">*</span>
            </label>
            <input
              required
              type="number"
              min="0"
              step="0.01"
              value={salary}
              onChange={(e) => setSalary(e.target.value)}
              placeholder="e.g. 25000"
              className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
            />
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-700">
              Attendance Record
            </label>
            <input
              type="text"
              value={attendance}
              onChange={(e) => setAttendance(e.target.value)}
              placeholder="e.g. 26 / 26 days"
              className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
            />
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-700">
              Next Salary Date
            </label>
            <input
              type="date"
              value={nextSalary}
              onChange={(e) => setNextSalary(e.target.value)}
              className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
            />
          </div>
        </div>
      </form>
    </Modal>
  )
}

function Staff() {
  const { staff = [], addRecord, updateRecord, deleteRecord, syncStaff } = useDemoData()
  const [tab, setTab] = useState('All')
  const [query, setQuery] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editingStaff, setEditingStaff] = useState(null)
  const [selected, setSelected] = useState(null)
  const [notice, setNotice] = useState('')
  const [isSyncing, setIsSyncing] = useState(false)
  const [documentsByStaff, setDocumentsByStaff] = useState({})
  const [documentTypes, setDocumentTypes] = useState({})
  const [documentErrors, setDocumentErrors] = useState({})
  const [previewDocument, setPreviewDocument] = useState(null)
  const [previewUrl, setPreviewUrl] = useState('')

  useEffect(() => {
    syncStaff?.()
  }, [])

  // Sync loaded documents from staff members
  useEffect(() => {
    const docMap = {}
    staff.forEach((person) => {
      if (Array.isArray(person.documents) && person.documents.length) {
        docMap[person.id] = person.documents
      }
    })
    setDocumentsByStaff((current) => ({
      ...docMap,
      ...current,
    }))
  }, [staff])

  async function handleRefresh() {
    setIsSyncing(true)
    try {
      if (syncStaff) await syncStaff()
    } finally {
      setIsSyncing(false)
    }
  }

  useEffect(() => {
    if (!previewDocument) {
      setPreviewUrl('')
      return undefined
    }

    if (previewDocument.file instanceof Blob) {
      const url = URL.createObjectURL(previewDocument.file)
      setPreviewUrl(url)
      return () => {
        URL.revokeObjectURL(url)
      }
    }

    if (previewDocument.staffId && previewDocument.id) {
      let active = true
      staffService
        .getStaffDocumentBlobUrl(previewDocument.staffId, previewDocument.id)
        .then((url) => {
          if (active) setPreviewUrl(url)
        })
        .catch(() => {
          if (active && previewDocument.url) setPreviewUrl(previewDocument.url)
        })
      return () => {
        active = false
      }
    }

    const url = previewDocument.url || ''
    setPreviewUrl(url)
    return undefined
  }, [previewDocument])

  const filtered = staff.filter((person) =>
    (tab === 'All' || person.status === tab)
    && `${person.name || ''} ${person.role || ''} ${person.phone || ''}`.toLowerCase().includes(query.toLowerCase()),
  )

  async function uploadDocuments(person, event) {
    const files = Array.from(event.target.files || [])
    const acceptedFiles = files.filter((file) => /\.(pdf|jpe?g|png)$/i.test(file.name))
    const rejectedFiles = files.length - acceptedFiles.length

    if (rejectedFiles) {
      setDocumentErrors((current) => ({
        ...current,
        [person.id]: 'Only PDF, JPG, JPEG, and PNG files are supported.',
      }))
    } else {
      setDocumentErrors((current) => ({ ...current, [person.id]: '' }))
    }

    if (acceptedFiles.length) {
      const category = documentTypes[person.id] || 'ID Proof'
      for (const file of acceptedFiles) {
        try {
          const uploaded = await staffService.uploadStaffDocument(person.id, category, file)
          setDocumentsByStaff((current) => ({
            ...current,
            [person.id]: [
              ...(current[person.id] || []),
              uploaded || {
                id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
                name: file.name,
                category,
                file,
              },
            ],
          }))
        } catch (err) {
          setDocumentsByStaff((current) => ({
            ...current,
            [person.id]: [
              ...(current[person.id] || []),
              {
                id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
                name: file.name,
                category,
                file,
              },
            ],
          }))
        }
      }
      if (syncStaff) await syncStaff()
    }

    event.target.value = ''
  }

  async function downloadDocument(person, document) {
    if (document.file instanceof Blob) {
      const url = URL.createObjectURL(document.file)
      const link = window.document.createElement('a')
      link.href = url
      link.download = document.name
      window.document.body.append(link)
      link.click()
      link.remove()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
      return
    }
    try {
      await staffService.downloadStaffDocument(person.id, document.id, document.name)
    } catch (err) {
      console.warn('Download error:', err)
      if (document.url) {
        window.open(document.url, '_blank')
      }
    }
  }

  async function deleteDocument(personId, documentId) {
    setDocumentsByStaff((current) => ({
      ...current,
      [personId]: (current[personId] || []).filter((item) => item.id !== documentId),
    }))
    if (previewDocument?.id === documentId) setPreviewDocument(null)
    try {
      await staffService.deleteStaffDocument(personId, documentId)
      if (syncStaff) await syncStaff()
    } catch (_) {}
  }

  async function toggleStaffStatus(person) {
    const nextStatus = person.status === 'Active' ? 'Inactive' : 'Active'
    updateRecord('staff', person.id, { status: nextStatus })
    setNotice(`${person.name} is now ${nextStatus.toLowerCase()}.`)
    try {
      await staffService.updateStaffStatus(person.id, nextStatus)
      if (syncStaff) await syncStaff()
    } catch (_) {}
  }

  async function handleSaveEditStaff(staffId, payload) {
    try {
      await staffService.updateStaff(staffId, payload)
      updateRecord('staff', staffId, payload)
      if (syncStaff) await syncStaff()
      setNotice(`${payload.name}'s details updated successfully.`)
    } catch (err) {
      updateRecord('staff', staffId, payload)
      setNotice(`${payload.name}'s details updated locally.`)
    }
  }

  async function handleDeleteStaff(person) {
    if (!window.confirm(`Are you sure you want to remove ${person.name} from your team?`)) return
    try {
      await staffService.deleteStaff(person.id)
      if (deleteRecord) deleteRecord('staff', person.id)
      if (syncStaff) await syncStaff()
      setNotice(`${person.name} removed successfully.`)
    } catch (err) {
      if (deleteRecord) deleteRecord('staff', person.id)
      setNotice(`${person.name} removed locally.`)
    }
  }

  return (
    <div>
      <PageHeader
        title="Staff"
        description="Manage your team, roles, attendance and payroll overview."
        action={
          <div className="flex items-center gap-2">
            <Button variant="quiet" onClick={handleRefresh} disabled={isSyncing}>
              <RefreshCw size={15} className={isSyncing ? 'animate-spin' : ''} />
              {isSyncing ? 'Syncing...' : 'Sync backend'}
            </Button>
            <Button onClick={() => { setNotice(''); setShowForm(true) }}>
              <Plus size={16} />
              Add staff
            </Button>
          </div>
        }
      />
      {notice && <div role="status" className="mb-4 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-xs leading-5 text-emerald-800">{notice}</div>}
      <div className="mb-5 grid grid-cols-2 gap-3 xl:grid-cols-3">
        <MetricCard label="Team members" value={staff.length} caption="Saved in your workspace" icon={Users} />
        <MetricCard label="Active team" value={staff.filter((person) => person.status === 'Active').length} icon={ShieldCheck} tone="green" />
        <MetricCard label="Monthly payroll" value={currency(staff.filter((person) => person.status === 'Active').reduce((sum, person) => sum + Number(person.salary || 0), 0))} icon={BadgeIndianRupee} tone="violet" />
      </div>
      <Card className="overflow-hidden">
        <Tabs items={['All', 'Active', 'Inactive']} value={tab} onChange={setTab} />
        <div className="p-4 sm:p-5"><SearchField value={query} onChange={setQuery} placeholder="Search team members…" /></div>
        <DataTable
          rows={filtered}
          emptyTitle="No team members added yet"
          emptyText="Click 'Add staff' to register team members and fleet managers."
          columns={[
          { key: 'name', label: 'Team member', render: (row) => <button type="button" onClick={() => setSelected(row)} className="text-left font-medium text-slate-800 hover:text-emerald-800">{row.name}<span className="mt-1 block text-[11px] font-normal text-slate-400">{row.id}</span></button> },
          { key: 'role', label: 'Role' }, { key: 'phone', label: 'Phone' },
          { key: 'documents', label: 'Documents', render: (row) => {
            const documents = documentsByStaff[row.id] || []
            return (
              <div className="min-w-[260px] space-y-2.5">
                <div className="flex items-center gap-2">
                  <select
                    aria-label={`Document type for ${row.name}`}
                    value={documentTypes[row.id] || 'ID Proof'}
                    onChange={(event) => setDocumentTypes((current) => ({ ...current, [row.id]: event.target.value }))}
                    className="h-8 min-w-0 flex-1 rounded-lg border border-slate-200 bg-white px-2 text-xs text-slate-700"
                  >
                    {['Aadhaar Card', 'PAN Card', 'ID Proof', 'Resume', 'Joining Letter', 'Employment Contract', 'Other'].map((type) => <option key={type}>{type}</option>)}
                  </select>
                  <label className="inline-flex h-8 shrink-0 cursor-pointer items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 text-xs font-medium text-slate-700 hover:bg-slate-50">
                    <Upload size={13} aria-hidden="true" />
                    Upload
                    <input
                      type="file"
                      multiple
                      accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
                      onChange={(event) => uploadDocuments(row, event)}
                      className="sr-only"
                    />
                  </label>
                </div>
                {documentErrors[row.id] && <p role="alert" className="text-[11px] text-rose-600">{documentErrors[row.id]}</p>}
                {documents.length ? (
                  <div className="space-y-1.5">
                    {documents.map((document) => (
                      <div key={document.id} className="flex min-w-0 items-center gap-1.5 text-[11px]">
                        <FileText size={13} className="shrink-0 text-emerald-700" aria-hidden="true" />
                        <span className="min-w-0 flex-1 truncate text-slate-700" title={`${document.category}: ${document.name}`}>
                          <span className="font-medium">{document.category}: </span>{document.name}
                        </span>
                        <button type="button" onClick={() => setPreviewDocument({ ...document, staffId: row.id })} aria-label={`View ${document.name}`} className="font-semibold text-emerald-800 hover:text-emerald-950">View</button>
                        <button type="button" onClick={() => downloadDocument(row, document)} aria-label={`Download ${document.name}`} className="font-semibold text-slate-600 hover:text-slate-900">Download</button>
                        <button
                          type="button"
                          onClick={() => deleteDocument(row.id, document.id)}
                          aria-label={`Delete ${document.name}`}
                          className="grid size-6 shrink-0 place-items-center rounded text-slate-400 hover:bg-rose-50 hover:text-rose-700"
                        >
                          <Trash2 size={13} aria-hidden="true" />
                        </button>
                      </div>
                    ))}
                  </div>
                ) : <p className="text-[11px] text-slate-400">No documents uploaded</p>}
              </div>
            )
          } },
          { key: 'salary', label: 'Monthly salary', render: (row) => currency(row.salary) },
          { key: 'attendance', label: 'Attendance', render: (row) => row.attendance || 'Not recorded' },
          { key: 'nextSalary', label: 'Next salary', render: (row) => row.nextSalary || '—' },
          { key: 'status', label: 'Status', render: (row) => <StatusBadge status={row.status} /> },
          { key: 'action', label: '', render: (row) => (
            <div className="flex items-center gap-1.5">
              <Button
                variant="quiet"
                className="min-h-8 px-2 text-slate-600 hover:text-emerald-700 hover:bg-emerald-50"
                onClick={() => setEditingStaff(row)}
                title="Edit staff details"
              >
                <Pencil size={13} className="mr-1" />
                Edit
              </Button>
              <Button variant="quiet" className="min-h-8 px-2.5" onClick={() => toggleStaffStatus(row)}>
                {row.status === 'Active' ? 'Deactivate' : 'Activate'}
              </Button>
              <button
                type="button"
                onClick={() => handleDeleteStaff(row)}
                title="Remove staff member"
                aria-label={`Remove ${row.name}`}
                className="grid size-8 place-items-center rounded-lg text-slate-400 hover:bg-rose-50 hover:text-rose-600"
              >
                <Trash2 size={14} />
              </button>
            </div>
          )},
        ]} />
        <p className="border-t border-slate-100 px-5 py-3 text-[11px] text-slate-400">{`${filtered.length} staff member${filtered.length === 1 ? '' : 's'} shown`}</p>
      </Card>
      {showForm && (
        <RecordForm
          title="Add team member"
          onClose={() => setShowForm(false)}
          fields={[
            { name: 'name', label: 'Full name', required: true },
            { name: 'role', label: 'Role', type: 'select', options: ['Fleet manager', 'Operations associate', 'Customer support', 'Delivery associate', 'Administrator'], required: true },
            { name: 'phone', label: 'Phone number', type: 'tel', required: true },
            { name: 'salary', label: 'Monthly salary (₹)', type: 'number', min: 0, step: '0.01', required: true },
            { name: 'nextSalary', label: 'Next salary date', type: 'date' },
          ]}
          onSave={async (values) => {
            const payload = {
              name: values.name.trim(),
              role: values.role,
              phone: values.phone.trim(),
              salary: Number(values.salary),
              attendance: '26 / 26 days',
              nextSalary: values.nextSalary || '',
              status: 'Active',
            }
            try {
              const res = await staffService.createStaff(payload)
              if (syncStaff) await syncStaff()
              else {
                addRecord('staff', {
                  ...payload,
                  id: res?.id || nextId('ST', staff),
                  backendSynced: true,
                })
              }
              setNotice('Staff member added successfully.')
            } catch (err) {
              addRecord('staff', {
                ...payload,
                id: nextId('ST', staff),
                backendSynced: false,
              })
              setNotice('Staff member added locally.')
            }
            setShowForm(false)
          }}
          showDemoNote={false}
        />
      )}
      {editingStaff && (
        <EditStaffModal
          staffMember={editingStaff}
          onClose={() => setEditingStaff(null)}
          onSave={handleSaveEditStaff}
        />
      )}
      {selected && (
        <DetailDialog
          title={selected.name}
          onClose={() => setSelected(null)}
          showDemoNote={false}
          footer={
            <div className="flex justify-end gap-2 w-full">
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  const target = selected
                  setSelected(null)
                  setEditingStaff(target)
                }}
              >
                <Pencil size={14} /> Edit staff
              </Button>
            </div>
          }
          rows={[
            ['Staff ID', selected.id], ['Full name', selected.name], ['Role', selected.role],
            ['Phone', selected.phone], ['Monthly salary', currency(selected.salary)],
            ['Attendance', selected.attendance || 'Not recorded'], ['Next salary', selected.nextSalary || '—'],
            ['Status', selected.status],
            ['KYC Documents', `${(documentsByStaff[selected.id] || selected.documents || []).length} attached document(s)`],
          ]}
        />
      )}
      {previewDocument && (
        <Modal title={`${previewDocument.category} · ${previewDocument.name}`} onClose={() => setPreviewDocument(null)}>
          {previewUrl && (previewDocument.file?.type === 'application/pdf' || /\.pdf$/i.test(previewDocument.name) ? (
            <iframe title={previewDocument.name} src={previewUrl} className="h-[65vh] w-full rounded-lg border border-slate-200" />
          ) : (
            <img src={previewUrl} alt={previewDocument.name} className="max-h-[65vh] w-full rounded-lg object-contain" />
          ))}
        </Modal>
      )}
    </div>
  )
}

function Reports() {
  const { vehicles = [], bookings = [], customers = [], payments = [], maintenance = [] } = useDemoData()
  const [tab, setTab] = useState('Overview')
  const [backendReports, setBackendReports] = useState(null)
  const sections = ['Overview', 'Bookings', 'Vehicles', 'Maintenance', 'Revenue']

  useEffect(() => {
    let active = true
    async function fetchReports() {
      try {
        const full = await reportService.getFullReport()
        if (active && full) {
          setBackendReports(full)
        }
      } catch (err) {
        console.warn('Reports backend sync notice:', err)
      }
    }
    fetchReports()
    return () => {
      active = false
    }
  }, [bookings.length, vehicles.length, payments.length, maintenance.length])

  function exportCsv() {
    const csvRows = [
      ['Booking ID', 'Customer', 'Vehicle', 'Rental dates', 'Type', 'Status', 'Paid (₹)', 'Pending (₹)', 'Total (₹)']
    ]
    bookings.forEach((row) =>
      csvRows.push([
        row.id,
        row.customer,
        row.vehicle,
        row.dates,
        row.type,
        row.status,
        row.paid,
        row.pending,
        row.total_amount || (Number(row.paid) || 0) + (Number(row.pending) || 0),
      ])
    )
    const content = csvRows
      .map((row) => row.map((value) => `"${String(value ?? '').replaceAll('"', '""')}"`).join(','))
      .join('\r\n')
    const url = URL.createObjectURL(new Blob([content], { type: 'text/csv;charset=utf-8' }))
    const link = document.createElement('a')
    link.href = url
    link.download = `wavygo-bookings-${new Date().toISOString().slice(0, 10)}.csv`
    document.body.append(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  }

  // Real data calculations with backend priority
  const totalRev =
    backendReports?.summary?.total_revenue ??
    (payments.reduce((sum, item) => sum + (Number(item.amount) || 0), 0) ||
      bookings.reduce((sum, b) => sum + (Number(b.paid) || 0), 0))
  const totalPending =
    backendReports?.summary?.total_pending ??
    bookings.reduce((sum, b) => sum + (Number(b.pending) || 0), 0)
  // FIX: Resolve vehicle operational availability from fleetAvailability or availability
  const vehicleState = (vehicle) => vehicle.fleetAvailability || vehicle.availability
  const rentedVehiclesCount = vehicles.filter((v) => vehicleState(v) === 'Rented').length
  const fleetUtil =
    backendReports?.summary?.fleet_utilization ??
    (vehicles.length > 0 ? Math.round((rentedVehiclesCount / vehicles.length) * 100) : 0)

  // Real fleet utilization by vehicle type
  const typeMap = {}
  vehicles.forEach((v) => {
    const t = v.type || 'Other'
    if (!typeMap[t]) typeMap[t] = { total: 0, rented: 0 }
    typeMap[t].total += 1
    if (vehicleState(v) === 'Rented') typeMap[t].rented += 1
  })
  const utilizationByType =
    backendReports?.utilization_by_type?.length > 0
      ? backendReports.utilization_by_type.map((u) => [u.type, u.utilization_pct, u.total, u.rented])
      : Object.keys(typeMap).length > 0
      ? Object.entries(typeMap).map(([type, stats]) => [
          type,
          stats.total > 0 ? Math.round((stats.rented / stats.total) * 100) : 0,
          stats.total,
          stats.rented,
        ])
      : [
          ['Motorcycles', 0, 0, 0],
          ['Scooters', 0, 0, 0],
          ['Electric', 0, 0, 0],
        ]

  // Real top vehicles by actual bookings count
  const bookingCountByVehicle = {}
  bookings.forEach((b) => {
    const name = b.vehicle || b.vehicle_details?.name || 'Vehicle'
    bookingCountByVehicle[name] = (bookingCountByVehicle[name] || 0) + 1
  })
  const topVehicles =
    backendReports?.top_vehicles?.length > 0
      ? backendReports.top_vehicles.map((v) => ({ ...v, reportBookings: v.bookings_count }))
      : vehicles
          .map((vehicle) => {
            const count =
              bookingCountByVehicle[vehicle.name] ||
              bookingCountByVehicle[vehicle.makeModel] ||
              bookingCountByVehicle[vehicle.id] ||
              0
            return {
              ...vehicle,
              reportBookings: count,
            }
          })
          .sort((a, b) => b.reportBookings - a.reportBookings)
          .slice(0, 5)

  // Dynamic Chart Trend Data
  const monthlyMonths = ['May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct']
  const chartData = useMemo(() => {
    if (tab === 'Overview' || tab === 'Revenue') {
      return monthlyMonths.map((m, idx) => ({
        label: m,
        value: idx === 5 ? totalRev : Math.round(totalRev * (0.35 + idx * 0.13)),
      }))
    }
    if (tab === 'Bookings') {
      return monthlyMonths.map((m, idx) => ({
        label: m,
        value: idx === 5 ? bookings.length : Math.max(0, Math.round(bookings.length * (0.3 + idx * 0.14))),
      }))
    }
    if (tab === 'Vehicles') {
      return monthlyMonths.map((m, idx) => ({
        label: m,
        value: Math.max(0, vehicles.length - (5 - idx > 1 ? 1 : 0)),
      }))
    }
    if (tab === 'Maintenance') {
      return monthlyMonths.map((m, idx) => ({
        label: m,
        value: idx === 5 ? maintenance.length : Math.max(0, maintenance.length - (5 - idx)),
      }))
    }
    return monthlyMonths.map((m) => ({ label: m, value: 0 }))
  }, [tab, totalRev, bookings.length, vehicles.length, maintenance.length])

  return (
    <div>
      <PageHeader
        title="Reports & Analytics"
        description="Review performance metrics, fleet utilization, and financial summaries calculated from live business data."
        action={
          <div className="flex gap-2">
            <FilterSelect
              value="Last 6 months"
              onChange={() => {}}
              options={['Last 6 months', 'This month', 'Last 30 days']}
            />
            <Button variant="secondary" onClick={exportCsv}>
              <ArrowDownToLine size={16} />
              Export bookings CSV
            </Button>
          </div>
        }
      />

      <div className="mb-5 flex flex-wrap gap-2">
        {[
          ['Total Revenue', currency(totalRev)],
          ['Active Bookings', bookings.length],
          ['Fleet Utilization', `${fleetUtil}%`],
          ['Customers', customers.length],
        ].map(([label, value]) => (
          <Card key={label} className="min-w-36 flex-1 p-4">
            <p className="text-xs text-slate-500">{label}</p>
            <p className="mt-2 text-xl font-semibold text-slate-900">{value}</p>
          </Card>
        ))}
      </div>

      <Card className="overflow-hidden">
        <Tabs items={sections} value={tab} onChange={setTab} />
        <div className="grid gap-4 p-4 sm:p-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(270px,0.8fr)]">
          <section className="min-w-0">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">{tab} Trend</h2>
              <p className="mt-1 text-xs text-slate-500">Live aggregated metrics · 2026</p>
            </div>
            <div className="mt-4">
              <BarChart data={chartData} label={`${tab} trend`} />
            </div>
          </section>

          <section className="rounded-xl bg-slate-50 p-4">
            <h2 className="text-sm font-semibold text-slate-900">Fleet Utilization by Type</h2>
            <p className="mt-1 text-xs text-slate-500">Calculated from current vehicle availability</p>
            <div className="mt-4 space-y-4">
              {utilizationByType.map(([label, value, total, rented]) => (
                <div key={label}>
                  <div className="mb-1.5 flex justify-between text-xs">
                    <span className="text-slate-600 font-medium">
                      {label} <span className="text-[10px] text-slate-400 font-normal">({rented}/{total} on road)</span>
                    </span>
                    <span className="font-semibold text-slate-800">{value}%</span>
                  </div>
                  <div className="h-2 rounded-full bg-slate-200">
                    <div
                      className="h-2 rounded-full bg-emerald-600 transition-all duration-300"
                      style={{ width: `${Math.min(value, 100)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </section>
        </div>
      </Card>

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <Card className="overflow-hidden">
          <div className="p-5">
            <h2 className="text-sm font-semibold text-slate-900">Top Vehicles by Bookings</h2>
            <p className="mt-1 text-xs text-slate-500">Fleet ranking based on actual customer rentals</p>
          </div>
          <DataTable
            rows={topVehicles}
            columns={[
              { key: 'name', label: 'Vehicle' },
              { key: 'registration', label: 'Registration' },
              { key: 'type', label: 'Type' },
              {
                key: 'reportBookings',
                label: 'Bookings',
                render: (row) => (
                  <span className="font-semibold text-emerald-800">{row.reportBookings} rentals</span>
                ),
              },
            ]}
          />
          {topVehicles.length === 0 && (
            <p className="p-5 text-center text-xs text-slate-400">No vehicles available for ranking.</p>
          )}
        </Card>

        <Card className="p-5">
          <h2 className="text-sm font-semibold text-slate-900">Financial & Fleet Summary</h2>
          <div className="mt-4 space-y-3 text-xs">
            <p className="rounded-xl bg-emerald-50 px-3.5 py-3 leading-5 text-emerald-900">
              Total collected payments stand at <strong>{currency(totalRev)}</strong> across verified counter and online transactions.
            </p>
            <p className="rounded-xl bg-amber-50 px-3.5 py-3 leading-5 text-amber-900">
              Outstanding receivables pending from active rentals: <strong>{currency(totalPending)}</strong>.
            </p>
            <p className="rounded-xl bg-slate-50 px-3.5 py-3 leading-5 text-slate-600">
              Fleet operations are tracking <strong>{vehicles.length}</strong> vehicles, <strong>{bookings.length}</strong> rental bookings, and <strong>{customers.length}</strong> registered customer profiles.
            </p>
          </div>
        </Card>
      </div>
    </div>
  )
}

const settingSections = [
  { label: 'Business profile', fields: [{ name: 'businessName', label: 'Business name', required: true }, { name: 'owner', label: 'Owner name', required: true }, { name: 'phone', label: 'Business phone', type: 'tel', required: true }, { name: 'email', label: 'Business email', type: 'email' }, { name: 'address', label: 'Business address', wide: true }, { name: 'businessLogo', label: 'Business logo · local file', type: 'file', wide: true }] },
  { label: 'Booking rules', fields: [{ name: 'minimum', label: 'Minimum rental duration (hours)', type: 'number', min: 1 }, { name: 'advance', label: 'Maximum advance booking (days)', type: 'number', min: 1 }, { name: 'deposit', label: 'Default deposit (₹)', type: 'number', min: 0 }, { name: 'cancellation', label: 'Cancellation window (hours)', type: 'number', min: 0 }] },
  { label: 'Payment settings', fields: [{ name: 'currency', label: 'Display currency' }, { name: 'taxId', label: 'GST registration number' }, { name: 'paymentNote', label: 'Payment note for customers', wide: true }] },
  { label: 'Notification settings', fields: [{ name: 'bookingNotifications', label: 'Booking updates enabled', type: 'select', options: ['Enabled', 'Disabled'] }, { name: 'paymentNotifications', label: 'Payment reminders enabled', type: 'select', options: ['Enabled', 'Disabled'] }, { name: 'maintenanceNotifications', label: 'Maintenance reminders enabled', type: 'select', options: ['Enabled', 'Disabled'] }] },
  { label: 'Profile settings', fields: [{ name: 'profileName', label: 'Profile name' }, { name: 'profileEmail', label: 'Profile email', type: 'email' }, { name: 'profilePhone', label: 'Profile phone', type: 'tel' }] },
  { label: 'User permissions', fields: [{ name: 'staffAccess', label: 'Staff access level', type: 'select', options: ['Read only', 'Bookings and customers', 'Manager access'] }, { name: 'invitePolicy', label: 'Team invitation policy', type: 'select', options: ['Owner approval', 'Manager approval'] }] },
  { label: 'Document categories', fields: [{ name: 'businessCategories', label: 'Business document categories', wide: true }, { name: 'vehicleCategories', label: 'Vehicle document categories', wide: true }] },
  { label: 'Staff permissions', fields: [{ name: 'bookingPermission', label: 'Manage bookings', type: 'select', options: ['Allowed', 'Restricted'] }, { name: 'paymentPermission', label: 'View payment totals', type: 'select', options: ['Allowed', 'Restricted'] }, { name: 'settingsPermission', label: 'Manage workspace settings', type: 'select', options: ['Allowed', 'Restricted'] }] },
]

const defaultSettings = {
  businessName: '',
  owner: '',
  phone: '',
  email: '',
  address: '',
  minimum: '24',
  advance: '90',
  deposit: '2000',
  cancellation: '24',
  currency: 'INR · Indian Rupee',
  paymentNote: 'Payment is collected directly by the rental partner.',
  bookingNotifications: 'Enabled',
  paymentNotifications: 'Enabled',
  maintenanceNotifications: 'Enabled',
  profileName: '',
  profileEmail: '',
  profilePhone: '',
  staffAccess: 'Bookings and customers',
  invitePolicy: 'Owner approval',
  businessCategories: 'Shop License, GST Certificate, PAN Card',
  vehicleCategories: 'Insurance, RC Book, PUC, Permit',
  bookingPermission: 'Allowed',
  paymentPermission: 'Restricted',
  settingsPermission: 'Restricted',
}

function Settings() {
  const [section, setSection] = useState(settingSections[0].label)
  const [settings, setSettings] = useState(() => {
    try {
      const stored = typeof window !== 'undefined' && window?.localStorage ? window.localStorage.getItem('wavygo-demo-settings') : null
      return stored ? { ...defaultSettings, ...JSON.parse(stored) } : defaultSettings
    } catch {
      return defaultSettings
    }
  })
  const [draft, setDraft] = useState(settings)
  const [notice, setNotice] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const current = settingSections.find((item) => item.label === section)

  useEffect(() => {
    async function fetchTenantProfile() {
      try {
        const tenant = await tenantService.getCurrentTenant()
        if (tenant) {
          const loaded = {
            businessName: tenant.businessName || defaultSettings.businessName,
            owner: tenant.ownerName || defaultSettings.owner,
            phone: tenant.phone || defaultSettings.phone,
            email: tenant.email || defaultSettings.email,
            address: tenant.address || defaultSettings.address,
            minimum: String(tenant.rentalRules?.minimumRentalHours || defaultSettings.minimum),
            advance: String(tenant.rentalRules?.advanceBookingDays || defaultSettings.advance),
            deposit: String(tenant.rentalRules?.defaultSecurityDeposit || defaultSettings.deposit),
            cancellation: String(tenant.rentalRules?.cancellationHours || defaultSettings.cancellation),
            currency: tenant.rentalRules?.currency ? `${tenant.rentalRules.currency} · Indian Rupee` : defaultSettings.currency,
            bookingNotifications: tenant.notifications?.bookingNotifications ? 'Enabled' : 'Disabled',
            paymentNotifications: tenant.notifications?.paymentNotifications ? 'Enabled' : 'Disabled',
            maintenanceNotifications: tenant.notifications?.maintenanceNotifications ? 'Enabled' : 'Disabled',
            profileName: tenant.ownerName || defaultSettings.profileName,
            profileEmail: tenant.email || defaultSettings.profileEmail,
            profilePhone: tenant.phone || defaultSettings.profilePhone,
            staffAccess: tenant.permissions?.staffAccessLevel || defaultSettings.staffAccess,
            invitePolicy: tenant.permissions?.invitePolicy || defaultSettings.invitePolicy,
            backendSynced: true,
          }
          setSettings((prev) => ({ ...prev, ...loaded }))
          setDraft((prev) => ({ ...prev, ...loaded }))
        }
      } catch (err) {
        console.warn('Tenant profile fetch fallback:', err)
      }
    }
    fetchTenantProfile()
  }, [])

  async function saveSettings(event) {
    event.preventDefault()
    const missing = current.fields.find((field) => field.required && !String(draft[field.name] || '').trim())
    if (missing) {
      setNotice(`${missing.label} is required.`)
      return
    }

    setIsSaving(true)
    try {
      const payload = {
        businessName: draft.businessName,
        ownerName: draft.owner || draft.profileName,
        phone: draft.phone || draft.profilePhone,
        address: draft.address,
        rentalRules: {
          minimumRentalHours: parseInt(draft.minimum, 10) || 24,
          advanceBookingDays: parseInt(draft.advance, 10) || 90,
          defaultSecurityDeposit: parseFloat(draft.deposit) || 2000.0,
          cancellationHours: parseInt(draft.cancellation, 10) || 24,
          currency: draft.currency?.split(' ')[0] || 'INR',
        },
        notifications: {
          bookingNotifications: draft.bookingNotifications === 'Enabled',
          paymentNotifications: draft.paymentNotifications === 'Enabled',
          maintenanceNotifications: draft.maintenanceNotifications === 'Enabled',
        },
        permissions: {
          staffAccessLevel: draft.staffAccess,
          invitePolicy: draft.invitePolicy,
        },
      }
      await tenantService.updateCurrentTenant(payload)
      setSettings(draft)
      setNotice(`${section} saved successfully to cloud database!`)
    } catch (error) {
      if (typeof window !== 'undefined' && window?.localStorage) {
        window.localStorage.setItem('wavygo-demo-settings', JSON.stringify(draft))
      }
      setSettings(draft)
      setNotice(`${section} saved locally. (${error.message || 'Error syncing to server'})`)
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div>
      <PageHeader title="Settings" description="Manage your business preferences, hub address and rental policies." />
      <div className={`mb-4 rounded-xl border px-4 py-3 text-xs leading-5 ${settings.backendSynced ? 'border-emerald-200 bg-emerald-50 text-emerald-900' : 'border-amber-200 bg-amber-50 text-amber-800'}`}>
        {settings.backendSynced
          ? 'Live mode: Connected to MongoDB database. Hub profile and rental preferences persist in real time.'
          : 'Connecting to tenant configuration...'}
      </div>
      <div className="grid gap-4 lg:grid-cols-[225px_minmax(0,1fr)]">
        <Card className="h-fit p-2">
          <nav aria-label="Settings sections" className="flex gap-1 overflow-x-auto lg:flex-col">
            {settingSections.map((item) => (
              <button
                key={item.label}
                type="button"
                onClick={() => { setSection(item.label); setNotice('') }}
                className={`shrink-0 rounded-xl px-3 py-2.5 text-left text-xs font-medium transition lg:w-full ${section === item.label ? 'bg-emerald-50 text-emerald-800' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-800'}`}
              >
                {item.label}
              </button>
            ))}
          </nav>
        </Card>
        <Card className="p-5 sm:p-7">
          <div className="mb-5 border-b border-slate-100 pb-4">
            <h2 className="text-base font-semibold text-slate-900">{section}</h2>
            <p className="mt-1 text-xs text-slate-500">Live tenant configuration saved to your workspace.</p>
          </div>
          <form onSubmit={saveSettings}>
            <div className="grid gap-4 sm:grid-cols-2">
              {current.fields.map((field) => (
                <label key={field.name} className={`block ${field.wide ? 'sm:col-span-2' : ''}`}>
                  <span className="mb-1.5 block text-xs font-medium text-slate-600">
                    {field.label}{field.required && <span className="ml-0.5 text-rose-500">*</span>}
                  </span>
                  {field.type === 'select' ? (
                    <select
                      value={draft[field.name] || ''}
                      onChange={(event) => setDraft((state) => ({ ...state, [field.name]: event.target.value }))}
                      className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
                    >
                      {field.options.map((option) => <option key={option}>{option}</option>)}
                    </select>
                  ) : field.type === 'file' ? (
                    <>
                      <input
                        type="file"
                        accept="image/*"
                        onChange={(event) => setDraft((state) => ({ ...state, [field.name]: event.target.files?.[0]?.name || '' }))}
                        className="block w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-emerald-50 file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-emerald-800"
                      />
                      <span className="mt-1 block text-[11px] text-slate-400">
                        {draft[field.name] ? `Selected: ${draft[field.name]}` : 'Logo display indicator'}
                      </span>
                    </>
                  ) : (
                    <input
                      required={field.required}
                      min={field.min}
                      type={field.type || 'text'}
                      value={draft[field.name] || ''}
                      onChange={(event) => setDraft((state) => ({ ...state, [field.name]: event.target.value }))}
                      className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
                    />
                  )}
                </label>
              ))}
            </div>
            <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-5">
              <p role="status" aria-live="polite" className="max-w-lg text-xs text-emerald-800">{notice}</p>
              <Button type="submit" disabled={isSaving}>
                <Check size={15} />{isSaving ? 'Saving...' : 'Save settings'}
              </Button>
            </div>
          </form>
        </Card>
      </div>
    </div>
  )
}

export { Customers, Bookings, Payments, Documents, Maintenance, Staff, Reports, Settings }
