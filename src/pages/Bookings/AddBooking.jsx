import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useDemoData } from '../../data/DemoDataContext.jsx'
import {
  ArrowLeft,
  ArrowRight,
  BadgeCheck,
  Check,
  CheckCircle2,
  CircleHelp,
  CreditCard,
  FileText,
  MapPin,
  ShieldCheck,
  UserRound,
  UsersRound,
} from 'lucide-react'

const steps = ['Select vehicle', 'Customer details', 'Rental details', 'Payment', 'Confirm']

function formatDate(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function getRentalDays(start, end) {
  if (!start || !end) return 1
  const [sy, sm, sd] = start.split('-').map(Number)
  const [ey, em, ed] = end.split('-').map(Number)
  return Math.max(1, Math.round((Date.UTC(ey, em - 1, ed) - Date.UTC(sy, sm - 1, sd)) / 86_400_000))
}

function AddBooking() {
  const navigate = useNavigate()
  const location = useLocation()
  const offlineMode = Boolean(location.state?.offline)
  const { vehicles, customers, addRecord } = useDemoData()
  const today = formatDate(new Date())
  const tomorrow = formatDate(new Date(Date.now() + 86_400_000))
  const [step, setStep] = useState(0)
  const [selectedVehicleId, setSelectedVehicleId] = useState('')
  const [customerMode, setCustomerMode] = useState('existing')
  const [selectedCustomerId, setSelectedCustomerId] = useState('')
  const [customer, setCustomer] = useState({ name: '', phone: '', email: '' })
  const [rental, setRental] = useState({ startDate: today, endDate: tomorrow, pickupTime: '10:00', returnTime: '10:00', pickupLocation: '', addOns: false, discount: '0' })
  const [payment, setPayment] = useState({ method: 'Cash', deposit: false })
  const [errors, setErrors] = useState({})
  const [confirmation, setConfirmation] = useState(null)
  const selectedVehicle = vehicles.find((vehicle) => vehicle.id === selectedVehicleId)
  const selectedCustomerRecord = customers.find((item) => item.id === selectedCustomerId)
  const selectedCustomer = selectedCustomerRecord?.name || ''
  const activeCustomer = customerMode === 'existing' && selectedCustomerRecord ? selectedCustomerRecord : customer
  const rentalDays = getRentalDays(rental.startDate, rental.endDate)
  const dailyPrice = Number(selectedVehicle?.price || 0)
  const baseAmount = dailyPrice * rentalDays
  const addOnAmount = rental.addOns ? 500 * rentalDays : 0
  const serviceFee = Math.round(baseAmount * 0.05)
  const subtotal = baseAmount + addOnAmount + serviceFee
  const discountAmount = Math.min(subtotal, Math.max(0, Number(rental.discount) || 0))
  const depositAmount = payment.deposit ? 2000 : 0
  const totalAmount = subtotal - discountAmount + depositAmount

  function updateCustomer(field, value) {
    setCustomer((current) => ({ ...current, [field]: value }))
    setErrors((current) => ({ ...current, [field]: '' }))
  }

  function setSelectedCustomer(name) {
    setSelectedCustomerId(customers.find((item) => item.name === name)?.id || '')
  }

  function validate() {
    const nextErrors = {}
    if (step === 0 && !selectedVehicleId) nextErrors.vehicle = 'Select a vehicle to continue.'
    if (step === 1) {
      if (customerMode === 'existing' && !selectedCustomerId) nextErrors.selectedCustomer = 'Choose a customer or add a new one.'
      if (customerMode === 'new') {
        if (!customer.name.trim()) nextErrors.name = 'Enter the customer’s full name.'
        if (!/^[+()\d\s-]{8,}$/.test(customer.phone.trim())) nextErrors.phone = 'Enter a valid phone number.'
        if (customer.email.trim() && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(customer.email.trim())) nextErrors.email = 'Enter a valid email address.'
      }
    }
    if (step === 2) {
      if (!rental.startDate) nextErrors.startDate = 'Select a pickup date.'
      if (!rental.endDate) nextErrors.endDate = 'Select a return date.'
      if (rental.startDate && rental.endDate && rental.endDate <= rental.startDate) nextErrors.endDate = 'Return must be after pickup.'
      if (!rental.pickupLocation.trim()) nextErrors.pickupLocation = 'Add a pickup location.'
    }
    setErrors(nextErrors)
    return Object.keys(nextErrors).length === 0
  }

  function updateRental(field, value) {
    setRental((current) => ({ ...current, [field]: value }))
    setErrors((current) => ({ ...current, [field]: '' }))
  }

  function makeBooking() {
    const customerName = activeCustomer.name.trim()
    const dates = `${new Date(`${rental.startDate}T00:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} – ${new Date(`${rental.endDate}T00:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`
    const booking = {
      id: `BK-${String(Date.now()).slice(-6)}`,
      customer: customerName,
      vehicle: selectedVehicle.name,
      dates,
      type: 'Offline',
      status: 'Active',
      paid: 0,
      pending: totalAmount,
    }
    if (customerMode === 'new') {
      addRecord('customers', {
        id: `CU-${String(Date.now()).slice(-5)}`,
        name: customerName,
        phone: customer.phone.trim(),
        email: customer.email.trim(),
        bookings: 1,
        active: 1,
        paid: 0,
        pending: totalAmount,
        status: 'Verified',
      })
    }
    addRecord('bookings', booking)
    setConfirmation({
      ...booking,
      customerName,
      vehicleName: selectedVehicle.name,
      startDate: rental.startDate,
      endDate: rental.endDate,
      pickupLocation: rental.pickupLocation.trim(),
      paymentMethod: payment.method,
      totalAmount,
    })
  }

  const Field = ({ label, name, value, onChange, error, placeholder, type = 'text', required = false, ...props }) => (
    <label className="block">
      <span className="mb-1.5 block text-sm font-semibold text-slate-700">{label}{required && <span className="ml-1 text-rose-500">*</span>}</span>
      <input type={type} value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} {...props} className={`h-11 w-full rounded-xl border bg-white px-3.5 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-emerald-500 focus:ring-3 focus:ring-emerald-100 ${error ? 'border-rose-300' : 'border-slate-200'}`} />
      {error && <span className="mt-1 block text-xs text-rose-600">{error}</span>}
    </label>
  )

  if (confirmation) {
    return (
      <section className="mx-auto max-w-2xl pb-10 text-slate-800">
        <div className="overflow-hidden rounded-3xl border border-slate-200/80 bg-white shadow-[0_12px_45px_rgba(15,23,42,0.06)]">
          <div className="bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-emerald-100 via-emerald-50 to-white px-6 pb-7 pt-10 text-center sm:px-10">
            <span className="mx-auto grid size-16 place-items-center rounded-full bg-white text-emerald-700 shadow-sm"><CheckCircle2 size={34} /></span>
            <p className="mt-5 text-xs font-semibold uppercase tracking-[0.16em] text-emerald-700">Local demo confirmation</p>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">Booking confirmed</h1>
            <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500">Booking <span className="font-semibold text-slate-800">{confirmation.id}</span> has been added to the shared demo workspace. No API or payment service was used.</p>
          </div>
          <div className="mx-5 mb-5 space-y-4 rounded-2xl border border-slate-100 bg-slate-50/60 p-4 sm:mx-8 sm:p-5">
            <div className="flex items-center gap-3"><span className="grid size-11 place-items-center rounded-xl bg-emerald-100 text-2xl">{selectedVehicle?.image || '🏍️'}</span><div><p className="text-sm font-semibold text-slate-900">{confirmation.vehicleName}</p><p className="mt-1 text-xs text-slate-500">{selectedVehicle?.registration}</p></div><span className="ml-auto rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-semibold text-emerald-800">Active · Offline</span></div>
            <div className="grid grid-cols-2 gap-3 border-t border-slate-200 pt-4 text-sm"><div><p className="text-xs text-slate-400">Customer</p><p className="mt-1 font-semibold text-slate-800">{confirmation.customerName}</p></div><div><p className="text-xs text-slate-400">Rental dates</p><p className="mt-1 font-semibold text-slate-800">{confirmation.startDate} – {confirmation.endDate}</p></div><div><p className="text-xs text-slate-400">Pickup</p><p className="mt-1 font-semibold text-slate-800">{confirmation.pickupLocation}</p></div><div><p className="text-xs text-slate-400">Payment method</p><p className="mt-1 font-semibold text-slate-800">{confirmation.paymentMethod} · not charged</p></div><div className="col-span-2 flex items-center justify-between border-t border-slate-200 pt-3"><span className="font-semibold text-slate-700">Estimated total · pending</span><span className="text-lg font-semibold text-slate-900">₹{confirmation.totalAmount.toLocaleString('en-IN')}</span></div></div>
          </div>
          <div className="flex flex-col gap-2 border-t border-slate-100 p-5 sm:flex-row sm:justify-end sm:px-8"><button type="button" onClick={() => navigate('/app/bookings')} className="h-11 rounded-xl border border-slate-200 px-4 text-sm font-semibold text-slate-700 hover:bg-slate-50">Back to bookings</button><button type="button" onClick={() => navigate('/app/vehicles')} className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-emerald-800 px-5 text-sm font-semibold text-white hover:bg-emerald-900">View fleet <ArrowRight size={16} /></button></div>
        </div>
      </section>
    )
  }

  return (
    <section className="mx-auto max-w-5xl space-y-5 pb-8 text-slate-800">
      <button type="button" onClick={() => navigate('/app/bookings')} className="inline-flex items-center gap-2 text-sm font-medium text-slate-500 transition hover:text-emerald-800"><ArrowLeft size={16} /> Back to bookings</button>
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end"><div><p className="mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-emerald-700">Booking desk</p><h1 className="text-3xl font-semibold tracking-tight text-slate-900">{offlineMode ? 'Create an offline booking' : 'Add a booking'}</h1><p className="mt-1.5 text-sm text-slate-500">Build a booking step by step. Records are shared across this demo workspace.</p></div><span className="inline-flex w-fit items-center gap-1.5 rounded-full border border-amber-100 bg-amber-50 px-3 py-1.5 text-xs font-semibold text-amber-800"><ShieldCheck size={14} /> No payment collected</span></div>

      <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="rounded-2xl border border-slate-200/80 bg-white px-4 py-5 shadow-[0_4px_22px_rgba(15,23,42,0.035)] sm:px-7">
          <div className="mb-6 grid grid-cols-5 gap-1.5 sm:gap-3">
            {steps.map((label, index) => <div key={label} className="min-w-0"><div className="flex items-center gap-1.5 sm:gap-2">{index < step ? <span className="grid size-7 shrink-0 place-items-center rounded-full bg-emerald-700 text-white"><Check size={14} /></span> : <span className={`grid size-7 shrink-0 place-items-center rounded-full text-xs font-semibold ${index === step ? 'bg-emerald-700 text-white' : 'bg-slate-100 text-slate-500'}`}>{index + 1}</span>}<span className={`hidden truncate text-[11px] font-semibold md:block ${index === step ? 'text-slate-900' : 'text-slate-400'}`}>{label}</span></div><div className={`mt-2 h-1 rounded-full ${index <= step ? 'bg-emerald-600' : 'bg-slate-100'}`} /><span className={`mt-1.5 block truncate text-[9px] font-medium sm:text-[10px] md:hidden ${index === step ? 'text-slate-700' : 'text-slate-400'}`}>{label}</span></div>)}
          </div>

          {step === 0 && <div className="space-y-4"><div><h2 className="text-lg font-semibold text-slate-900">Select a vehicle</h2><p className="mt-1 text-sm text-slate-500">Choose which vehicle this booking is for.</p></div>{errors.vehicle && <p className="rounded-lg bg-rose-50 px-3 py-2 text-xs text-rose-700">{errors.vehicle}</p>}<div className="grid gap-3 sm:grid-cols-2">{vehicles.map((vehicle) => <button type="button" key={vehicle.id} onClick={() => { setSelectedVehicleId(vehicle.id); setErrors((current) => ({ ...current, vehicle: '' })) }} className={`relative rounded-2xl border p-4 text-left transition ${selectedVehicleId === vehicle.id ? 'border-emerald-500 bg-emerald-50/50 ring-3 ring-emerald-100' : 'border-slate-200 hover:border-emerald-200 hover:bg-emerald-50/20'}`}><span className="absolute right-3 top-3 grid size-5 place-items-center rounded-full border border-slate-200 bg-white">{selectedVehicleId === vehicle.id && <span className="size-2.5 rounded-full bg-emerald-700" />}</span><div className="flex items-center gap-3"><span className="grid size-12 place-items-center rounded-xl bg-gradient-to-br from-emerald-50 to-green-100 text-2xl">{vehicle.image || '???'}</span><div className="min-w-0"><p className="truncate pr-5 text-sm font-semibold text-slate-900">{vehicle.name}</p><p className="mt-1 truncate text-xs text-slate-500">{vehicle.registration}</p></div></div><div className="mt-4 flex items-end justify-between border-t border-slate-100 pt-3"><span className="text-xs text-slate-500">{vehicle.type} / {vehicle.availability || 'Available'}</span><span className="text-sm font-semibold text-slate-900">₹{Number(vehicle.price).toLocaleString('en-IN')}<span className="font-normal text-slate-400"> / day</span></span></div><span className={`absolute bottom-[3.25rem] right-4 rounded-full px-2 py-0.5 text-[10px] font-semibold ${vehicle.status === 'Online' ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-500'}`}>{vehicle.status}</span></button>)}</div></div>}

          {step === 1 && <div className="space-y-5"><div><h2 className="text-lg font-semibold text-slate-900">Customer details</h2><p className="mt-1 text-sm text-slate-500">Select an existing customer or add someone new for this demo.</p></div><div className="grid grid-cols-2 rounded-xl bg-slate-100 p-1"><button type="button" onClick={() => { setCustomerMode('existing'); setErrors({}) }} className={`inline-flex h-9 items-center justify-center gap-2 rounded-lg text-sm font-semibold ${customerMode === 'existing' ? 'bg-white text-emerald-800 shadow-sm' : 'text-slate-500'}`}><UsersRound size={15} /> Existing</button><button type="button" onClick={() => { setCustomerMode('new'); setErrors({}) }} className={`inline-flex h-9 items-center justify-center gap-2 rounded-lg text-sm font-semibold ${customerMode === 'new' ? 'bg-white text-emerald-800 shadow-sm' : 'text-slate-500'}`}><UserRound size={15} /> New customer</button></div>{customerMode === 'existing' ? <div><label className="mb-1.5 block text-sm font-semibold text-slate-700">Choose a customer<span className="ml-1 text-rose-500">*</span></label><div className="space-y-2">{customers.map((item) => <button type="button" key={item.name} onClick={() => { setSelectedCustomer(item.name); setErrors({}) }} className={`flex w-full items-center gap-3 rounded-xl border p-3.5 text-left transition ${selectedCustomer === item.name ? 'border-emerald-500 bg-emerald-50/50' : 'border-slate-200 hover:border-emerald-200'}`}><span className="grid size-10 place-items-center rounded-full bg-slate-100 text-sm font-semibold text-slate-600">{item.name.split(' ').map((part) => part[0]).join('')}</span><span className="min-w-0 flex-1"><span className="block text-sm font-semibold text-slate-800">{item.name}</span><span className="mt-0.5 block truncate text-xs text-slate-500">{item.phone} · {item.email}</span></span><span className={`grid size-5 place-items-center rounded-full border ${selectedCustomer === item.name ? 'border-emerald-700 bg-emerald-700 text-white' : 'border-slate-300'}`}>{selectedCustomer === item.name && <Check size={12} />}</span></button>)}</div>{errors.selectedCustomer && <p className="mt-1.5 text-xs text-rose-600">{errors.selectedCustomer}</p>}</div> : <div className="grid gap-4 sm:grid-cols-2"><Field label="Full name" name="name" value={customer.name} onChange={(value) => updateCustomer('name', value)} error={errors.name} placeholder="e.g. Meera Shah" required /><Field label="Phone number" name="phone" value={customer.phone} onChange={(value) => updateCustomer('phone', value)} error={errors.phone} placeholder="+91 98765 43210" required /><div className="sm:col-span-2"><Field label="Email address" name="email" value={customer.email} onChange={(value) => updateCustomer('email', value)} error={errors.email} placeholder="name@example.com" type="email" /></div></div>}</div>}

          {step === 2 && (
            <div className="space-y-5">
              <div><h2 className="text-lg font-semibold text-slate-900">Rental details</h2><p className="mt-1 text-sm text-slate-500">Set the pickup and return dates, times and location.</p></div>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Pickup date" name="startDate" type="date" value={rental.startDate} onChange={(value) => updateRental('startDate', value)} error={errors.startDate} min={today} required />
                <Field label="Return date" name="endDate" type="date" value={rental.endDate} onChange={(value) => updateRental('endDate', value)} error={errors.endDate} min={rental.startDate || today} required />
                <Field label="Pickup time" name="pickupTime" type="time" value={rental.pickupTime} onChange={(value) => updateRental('pickupTime', value)} />
                <Field label="Return time" name="returnTime" type="time" value={rental.returnTime} onChange={(value) => updateRental('returnTime', value)} />
                <div className="sm:col-span-2"><Field label="Pickup location" name="pickupLocation" value={rental.pickupLocation} onChange={(value) => updateRental('pickupLocation', value)} error={errors.pickupLocation} placeholder={selectedVehicle?.location || 'e.g. Indiranagar, Bengaluru'} required /></div>
                <div className="sm:col-span-2"><Field label="Discount (₹)" name="discount" type="number" value={rental.discount} onChange={(value) => updateRental('discount', value)} min="0" step="100" placeholder="0" /></div>
              </div>
              <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-slate-200 p-4 hover:border-emerald-200"><input type="checkbox" checked={rental.addOns} onChange={(event) => updateRental('addOns', event.target.checked)} className="mt-0.5 size-4 accent-emerald-700" /><span className="flex-1"><span className="block text-sm font-semibold text-slate-800">Add roadside assistance</span><span className="mt-1 block text-xs text-slate-500">A demo add-on of ₹500 per rental day.</span></span><span className="whitespace-nowrap text-xs font-semibold text-slate-600">₹500 / day</span></label>
            </div>
          )}

          {step === 3 && <div className="space-y-5"><div><h2 className="text-lg font-semibold text-slate-900">Payment</h2><p className="mt-1 text-sm text-slate-500">Record a payment preference and review the estimated amount.</p></div><div><p className="mb-2 text-sm font-semibold text-slate-700">Payment method</p><div className="grid gap-2 sm:grid-cols-3">{['Cash', 'Card', 'Bank transfer'].map((method) => <button type="button" key={method} onClick={() => setPayment((current) => ({ ...current, method }))} className={`inline-flex h-11 items-center justify-center gap-2 rounded-xl border text-sm font-semibold transition ${payment.method === method ? 'border-emerald-500 bg-emerald-50 text-emerald-800' : 'border-slate-200 text-slate-600 hover:border-emerald-200'}`}><CreditCard size={15} />{method}</button>)}</div></div><label className="flex cursor-pointer items-start gap-3 rounded-xl border border-slate-200 p-4 hover:border-emerald-200"><input type="checkbox" checked={payment.deposit} onChange={(event) => setPayment((current) => ({ ...current, deposit: event.target.checked }))} className="mt-0.5 size-4 accent-emerald-700" /><span className="flex-1"><span className="block text-sm font-semibold text-slate-800">Include refundable security deposit</span><span className="mt-1 block text-xs text-slate-500">Shown as an estimate only; nothing is charged.</span></span><span className="whitespace-nowrap text-sm font-semibold text-slate-700">₹2,000</span></label><div className="flex gap-3 rounded-xl border border-amber-100 bg-amber-50/70 p-4"><CircleHelp size={17} className="mt-0.5 shrink-0 text-amber-700" /><p className="text-xs leading-5 text-amber-900/80">Payment selection is for your local booking record only. No card details are requested and no payment is collected.</p></div></div>}

          {step === 4 && <div className="space-y-4"><div><h2 className="text-lg font-semibold text-slate-900">Confirm booking</h2><p className="mt-1 text-sm text-slate-500">Check the details before creating your local demo booking.</p></div><div className="rounded-2xl border border-slate-200 p-4"><div className="flex items-center gap-3"><span className="grid size-12 place-items-center rounded-xl bg-emerald-50 text-2xl">{selectedVehicle?.icon || '🚘'}</span><div><p className="text-sm font-semibold text-slate-900">{selectedVehicle?.name}</p><p className="mt-1 text-xs text-slate-500">{selectedVehicle?.plate} · {selectedVehicle?.type}</p></div></div><div className="mt-4 grid grid-cols-2 gap-3 border-t border-slate-100 pt-4 text-sm"><div><p className="text-xs text-slate-400">Customer</p><p className="mt-1 font-semibold text-slate-800">{activeCustomer.name || '—'}</p><p className="mt-0.5 text-xs text-slate-500">{activeCustomer.phone || '—'}</p></div><div><p className="text-xs text-slate-400">Rental period</p><p className="mt-1 font-semibold text-slate-800">{rentalDays} {rentalDays === 1 ? 'day' : 'days'}</p><p className="mt-0.5 text-xs text-slate-500">{rental.startDate} → {rental.endDate}</p></div><div className="col-span-2"><p className="text-xs text-slate-400">Pickup location</p><p className="mt-1 font-semibold text-slate-800">{rental.pickupLocation || '—'}</p></div></div></div><div className="rounded-2xl bg-slate-50 p-4"><p className="mb-3 text-sm font-semibold text-slate-800">Estimated total</p><div className="space-y-2 text-xs text-slate-500"><div className="flex justify-between"><span>Rental · {rentalDays} {rentalDays === 1 ? 'day' : 'days'}</span><span>₹{baseAmount.toLocaleString('en-IN')}</span></div>{rental.addOns && <div className="flex justify-between"><span>Roadside assistance</span><span>₹{addOnAmount.toLocaleString('en-IN')}</span></div>}<div className="flex justify-between"><span>Demo service fee (5%)</span><span>₹{serviceFee.toLocaleString('en-IN')}</span></div>{payment.deposit && <div className="flex justify-between"><span>Refundable deposit</span><span>₹{depositAmount.toLocaleString('en-IN')}</span></div>}<div className="flex justify-between border-t border-slate-200 pt-2 text-sm font-semibold text-slate-900"><span>Total estimate</span><span>₹{totalAmount.toLocaleString('en-IN')}</span></div></div></div><div className="flex gap-3 rounded-xl border border-emerald-100 bg-emerald-50/60 p-4"><BadgeCheck size={17} className="mt-0.5 shrink-0 text-emerald-700" /><p className="text-xs leading-5 text-emerald-900/75">Create this booking locally for preview. This will not send customer details or charge payment.</p></div></div>}

          <div className="mt-7 flex flex-col-reverse gap-2 border-t border-slate-100 pt-5 sm:flex-row sm:items-center sm:justify-between"><button type="button" disabled={step === 0} onClick={() => { setStep((current) => current - 1); setErrors({}) }} className="inline-flex h-11 items-center justify-center gap-2 rounded-xl border border-slate-200 px-4 text-sm font-semibold text-slate-600 transition hover:bg-slate-50 disabled:invisible"><ArrowLeft size={15} /> Back</button><div className="flex items-center justify-end gap-3"><span className="hidden text-xs text-slate-400 sm:block">Step {step + 1} of {steps.length}</span>{step < 4 ? <button type="button" onClick={() => { if (validate()) { setErrors({}); setStep((current) => current + 1) } }} className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-emerald-800 px-5 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-900">Continue <ArrowRight size={16} /></button> : <button type="button" onClick={makeBooking} className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-emerald-800 px-5 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-900"><Check size={16} /> Confirm demo booking</button>}</div></div>
        </div>

        <aside className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-[0_4px_22px_rgba(15,23,42,0.035)] lg:sticky lg:top-6"><div className="flex items-center gap-2"><FileText size={17} className="text-emerald-700" /><h2 className="text-sm font-semibold text-slate-900">Booking summary</h2></div><div className="mt-4 rounded-xl bg-slate-50 p-3.5">{selectedVehicle ? <div className="flex items-center gap-3"><span className="grid size-10 place-items-center rounded-xl bg-emerald-50 text-xl">{selectedVehicle.icon || '🚘'}</span><div className="min-w-0"><p className="truncate text-sm font-semibold text-slate-800">{selectedVehicle.name}</p><p className="mt-0.5 text-xs text-slate-500">₹{Number(selectedVehicle.price).toLocaleString('en-IN')} / day</p></div></div> : <p className="text-xs text-slate-400">Select a vehicle to see your estimate.</p>}</div><div className="mt-4 space-y-3 text-xs"><div className="flex justify-between text-slate-500"><span>Rental duration</span><span className="font-medium text-slate-700">{selectedVehicle ? `${rentalDays} ${rentalDays === 1 ? 'day' : 'days'}` : '—'}</span></div><div className="flex justify-between text-slate-500"><span>Customer</span><span className="max-w-[130px] truncate font-medium text-slate-700">{activeCustomer.name || 'Not selected'}</span></div>{selectedVehicle && <><div className="flex justify-between text-slate-500"><span>Rental estimate</span><span className="font-medium text-slate-700">₹{baseAmount.toLocaleString('en-IN')}</span></div><div className="flex justify-between border-t border-slate-100 pt-3 font-semibold text-slate-800"><span>Estimated total</span><span>₹{totalAmount.toLocaleString('en-IN')}</span></div></>}</div><div className="mt-5 flex gap-2.5 rounded-xl border border-emerald-100 bg-emerald-50/60 p-3"><ShieldCheck size={15} className="mt-0.5 shrink-0 text-emerald-700" /><p className="text-[11px] leading-4 text-emerald-900/75">Your details stay in this browser. This is a demo, not a live reservation.</p></div></aside>
      </div>
      <p className="flex items-center justify-center gap-2 text-center text-xs text-slate-400"><MapPin size={13} /> Demo customer and fleet data is for preview only.</p>
    </section>
  )
}

export default AddBooking
