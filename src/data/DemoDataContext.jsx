import { createContext, useContext, useState } from 'react'

const DemoDataContext = createContext(null)

const initialVehicles = [
  { id: 'VH-1042', name: 'Honda Activa 6G', registration: 'GJ 05 AB 4821', type: 'Scooter', fuel: 'Petrol', year: 2024, color: 'Matte blue', engineCapacity: 110, rcStatus: 'Verified', seats: 2, status: 'Online', availability: 'Available', price: 649, image: '🛵' },
  { id: 'VH-1038', name: 'Royal Enfield Classic 350', registration: 'GJ 05 CD 7194', type: 'Motorcycle', fuel: 'Petrol', year: 2023, color: 'Chrome red', engineCapacity: 349, rcStatus: 'Verified', seats: 2, status: 'Online', availability: 'Rented', price: 1899, image: '🏍️' },
  { id: 'VH-1034', name: 'Ather 450X', registration: 'GJ 05 EF 3602', type: 'Electric', fuel: 'Electric', year: 2025, color: 'Cosmic black', engineCapacity: null, rcStatus: 'Verified', seats: 2, status: 'Online', availability: 'Available', price: 1199, image: '🛵' },
  { id: 'VH-1029', name: 'TVS Jupiter', registration: 'GJ 05 GH 2351', type: 'Scooter', fuel: 'Petrol', year: 2022, color: 'Titanium grey', engineCapacity: 110, rcStatus: 'Pending review', seats: 2, status: 'Offline', availability: 'Available', price: 599, image: '🛵' },
  { id: 'VH-1022', name: 'Yamaha FZ-S FI', registration: 'GJ 05 JK 8610', type: 'Motorcycle', fuel: 'Petrol', year: 2024, color: 'Racing blue', engineCapacity: 149, rcStatus: 'Verified', seats: 2, status: 'Online', availability: 'Maintenance', price: 999, image: '🏍️' },
  { id: 'VH-1018', name: 'Bajaj Pulsar N160', registration: 'GJ 05 LM 4073', type: 'Motorcycle', fuel: 'Petrol', year: 2025, color: 'Brooklyn black', engineCapacity: 164, rcStatus: 'Verified', seats: 2, status: 'Online', availability: 'Available', price: 1099, image: '🏍️' },
]

const initialCustomers = [
  { id: 'CU-2048', name: 'Aarav Mehta', phone: '+91 98765 43210', email: 'aarav.mehta@email.com', bookings: 14, active: 1, paid: 28650, pending: 0, status: 'Verified' },
  { id: 'CU-2047', name: 'Isha Patel', phone: '+91 97654 32109', email: 'isha.patel@email.com', bookings: 9, active: 1, paid: 19450, pending: 1200, status: 'Verified' },
  { id: 'CU-2046', name: 'Rohan Shah', phone: '+91 96543 21098', email: 'rohan.shah@email.com', bookings: 6, active: 0, paid: 12800, pending: 0, status: 'Verified' },
  { id: 'CU-2045', name: 'Ananya Desai', phone: '+91 95432 10987', email: 'ananya.desai@email.com', bookings: 3, active: 0, paid: 6200, pending: 850, status: 'Review' },
  { id: 'CU-2044', name: 'Kabir Joshi', phone: '+91 94321 09876', email: 'kabir.j@email.com', bookings: 2, active: 0, paid: 3700, pending: 0, status: 'Verified' },
]

const initialBookings = [
  { id: 'BK-3984', customer: 'Aarav Mehta', vehicleId: 'VH-1038', vehicle: 'Royal Enfield Classic 350', dates: 'Oct 12 – Oct 14', startAt: '2026-10-12T10:00', endAt: '2026-10-14T10:00', type: 'Online', status: 'Active', paid: 3798, pending: 0 },
  { id: 'BK-3983', customer: 'Isha Patel', vehicleId: 'VH-1042', vehicle: 'Honda Activa 6G', dates: 'Oct 12 – Oct 13', startAt: '2026-10-12T10:00', endAt: '2026-10-13T10:00', type: 'Offline', status: 'Active', paid: 649, pending: 1200 },
  { id: 'BK-3982', customer: 'Rohan Shah', vehicleId: 'VH-1034', vehicle: 'Ather 450X', dates: 'Oct 11 – Oct 12', startAt: '2026-10-11T10:00', endAt: '2026-10-12T10:00', type: 'Online', status: 'Completed', paid: 2398, pending: 0 },
  { id: 'BK-3981', customer: 'Ananya Desai', vehicleId: 'VH-1018', vehicle: 'Bajaj Pulsar N160', dates: 'Oct 11 – Oct 14', startAt: '2026-10-11T10:00', endAt: '2026-10-14T10:00', type: 'Offline', status: 'Active', paid: 2198, pending: 850 },
  { id: 'BK-3980', customer: 'Kabir Joshi', vehicleId: 'VH-1029', vehicle: 'TVS Jupiter', dates: 'Oct 10 – Oct 11', startAt: '2026-10-10T10:00', endAt: '2026-10-11T10:00', type: 'Online', status: 'Completed', paid: 599, pending: 0 },
  { id: 'BK-3979', customer: 'Neha Shah', vehicleId: 'VH-1022', vehicle: 'Yamaha FZ-S FI', dates: 'Oct 09 – Oct 10', startAt: '2026-10-09T10:00', endAt: '2026-10-10T10:00', type: 'Online', status: 'Cancelled', paid: 0, pending: 0 },
]

const initialPayments = [
  { id: 'TX-7082', booking: 'BK-3984', customer: 'Aarav Mehta', method: 'UPI', date: 'Oct 12, 2026', amount: 3798, status: 'Paid' },
  { id: 'TX-7081', booking: 'BK-3983', customer: 'Isha Patel', method: 'Cash', date: 'Oct 12, 2026', amount: 649, status: 'Partial' },
  { id: 'TX-7080', booking: 'BK-3982', customer: 'Rohan Shah', method: 'Card', date: 'Oct 11, 2026', amount: 2398, status: 'Paid' },
  { id: 'TX-7079', booking: 'BK-3981', customer: 'Ananya Desai', method: 'UPI', date: 'Oct 11, 2026', amount: 2198, status: 'Partial' },
  { id: 'TX-7078', booking: 'BK-3980', customer: 'Kabir Joshi', method: 'UPI', date: 'Oct 10, 2026', amount: 599, status: 'Paid' },
]

const initialDocuments = [
  { id: 'DC-104', name: 'Business registration', category: 'Shop License', date: 'Sep 24, 2026', status: 'Verified', scope: 'Business' },
  { id: 'DC-103', name: 'GST registration certificate', category: 'GST Certificate', date: 'Sep 18, 2026', status: 'Verified', scope: 'Business' },
  { id: 'DC-102', name: 'Owner PAN card', category: 'PAN Card', date: 'Sep 18, 2026', status: 'In review', scope: 'Business' },
  { id: 'DC-101', name: 'Activa 6G insurance', category: 'Insurance', date: 'Aug 30, 2026', status: 'Expires soon', scope: 'Vehicle' },
  { id: 'DC-100', name: 'Classic 350 RC book', category: 'RC Book', date: 'Aug 22, 2026', status: 'Verified', scope: 'Vehicle' },
]

const initialMaintenance = [
  { id: 'MT-081', vehicle: 'Yamaha FZ-S FI', type: 'Scheduled servicing', start: 'Oct 12, 2026', expected: 'Oct 14, 2026', cost: 2400, payment: 'Paid', status: 'Ongoing' },
  { id: 'MT-080', vehicle: 'TVS Jupiter', type: 'Brake inspection', start: 'Oct 10, 2026', expected: 'Oct 11, 2026', cost: 950, payment: 'Paid', status: 'Completed' },
  { id: 'MT-079', vehicle: 'Ather 450X', type: 'Tyre replacement', start: 'Oct 07, 2026', expected: 'Oct 08, 2026', cost: 3800, payment: 'Pending', status: 'Completed' },
  { id: 'MT-078', vehicle: 'Honda Activa 6G', type: 'Oil change', start: 'Oct 02, 2026', expected: 'Oct 02, 2026', cost: 680, payment: 'Paid', status: 'Completed' },
]

const initialStaff = [
  { id: 'ST-024', name: 'Priya Nair', role: 'Fleet manager', phone: '+91 98201 23456', salary: 28000, attendance: '24 / 26 days', nextSalary: 'Oct 31, 2026', status: 'Active' },
  { id: 'ST-023', name: 'Dev Patel', role: 'Operations associate', phone: '+91 98202 34567', salary: 22000, attendance: '23 / 26 days', nextSalary: 'Oct 31, 2026', status: 'Active' },
  { id: 'ST-022', name: 'Sara Khan', role: 'Customer support', phone: '+91 98203 45678', salary: 24000, attendance: '26 / 26 days', nextSalary: 'Oct 31, 2026', status: 'Active' },
  { id: 'ST-021', name: 'Nikhil Rao', role: 'Delivery associate', phone: '+91 98204 56789', salary: 19500, attendance: '—', nextSalary: '—', status: 'Inactive' },
]

const seed = {
  vehicles: initialVehicles, customers: initialCustomers, bookings: initialBookings,
  payments: initialPayments, paymentAdjustments: [], cancellationHistory: [], refundAdjustments: [], customerEditHistory: [], auditLogs: [],
  documents: initialDocuments, maintenance: initialMaintenance, staff: initialStaff,
}

const CUSTOMER_EDIT_ROLES = ['founder', 'admin', 'manager']
const PAYMENT_CORRECTION_ROLES = ['admin']
const normalizeRole = (role = '') => String(role).trim().toLowerCase()
const hasPermission = (actor, roles) => roles.includes(normalizeRole(actor?.role))
function auditEntry({ action, actor, targetId, targetType, reason, changes }) {
  return { id: `AU-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`, action, actorName: actor?.name || 'Unknown demo user', actorRole: actor?.role || 'Unknown', targetId, targetType, reason, changes, createdAt: new Date().toISOString() }
}

function bookingInterval(booking) {
  if (booking.startAt && booking.endAt) return [new Date(booking.startAt).getTime(), new Date(booking.endAt).getTime()]
  const match = String(booking.dates || '').match(/([A-Za-z]{3})\s+(\d{1,2})\s*[–-]\s*([A-Za-z]{3})?\s*(\d{1,2})/)
  if (!match) return [NaN, NaN]
  const monthNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
  const month = monthNames.indexOf(match[1])
  const endMonth = match[3] ? monthNames.indexOf(match[3]) : month
  const year = 2026
  return [new Date(year, month, Number(match[2]), 10).getTime(), new Date(year, endMonth, Number(match[4]), 10).getTime()]
}

function intervalsOverlap(startA, endA, startB, endB) {
  return startA < endB && startB < endA
}

export function DemoDataProvider({ children }) {
  const [data, setData] = useState(seed)
  const [currentDemoRole, setCurrentDemoRoleState] = useState('Admin')
  const roleNames = { Admin: 'Demo Admin', Founder: 'Demo Founder', Manager: 'Demo Manager', Employee: 'Demo Employee', Intern: 'Demo Intern' }
  const currentDemoUser = { name: roleNames[currentDemoRole], role: currentDemoRole }
  function setCurrentDemoRole(role) { if (Object.prototype.hasOwnProperty.call(roleNames, role)) setCurrentDemoRoleState(role) }

  function addRecord(collection, record) { setData((current) => ({ ...current, [collection]: [record, ...(current[collection] || [])] })) }
  function updateRecord(collection, id, changes) {
    if (['customers', 'payments', 'paymentAdjustments'].includes(collection)) return { success: false, error: 'Use the dedicated update function for this record.' }
    setData((current) => ({ ...current, [collection]: (current[collection] || []).map((record) => record.id === id ? { ...record, ...changes } : record) }))
    return { success: true }
  }

  function updateCustomerDetails({ customerId, changes, reason, actor }) {
    const customer = data.customers.find((item) => item.id === customerId)
    if (!customer) return { success: false, error: 'Customer not found.' }
    if (!hasPermission(actor, CUSTOMER_EDIT_ROLES)) return { success: false, error: 'You do not have permission to edit customer details.' }
    if (!reason?.trim()) return { success: false, error: 'Please provide a reason for this change.' }
    const allowed = ['name', 'phone', 'email', 'status']
    const safeChanges = Object.fromEntries(Object.entries(changes || {}).filter(([key]) => allowed.includes(key)))
    const changed = Object.fromEntries(Object.entries(safeChanges).filter(([key, value]) => String(customer[key] ?? '') !== String(value ?? '')).map(([key, value]) => [key, { before: customer[key], after: value }]))
    if (!Object.keys(changed).length) return { success: false, error: 'No customer details were changed.' }
    const updatedCustomer = { ...customer, ...safeChanges }
    const entry = { ...auditEntry({ action: 'CUSTOMER_DETAILS_UPDATED', actor, targetId: customerId, targetType: 'customer', reason: reason.trim(), changes: changed }), customerId }
    setData((current) => ({ ...current, customers: current.customers.map((item) => item.id === customerId ? updatedCustomer : item), customerEditHistory: [...current.customerEditHistory, entry], auditLogs: [...current.auditLogs, entry] }))
    return { success: true, customer: updatedCustomer }
  }

  function addPaymentAdjustment({ paymentId, bookingId, correctedAmount, reason, actor }) {
    const payment = data.payments.find((item) => item.id === paymentId)
    const booking = data.bookings.find((item) => item.id === bookingId)
    if (!payment) return { success: false, error: 'Payment record not found.' }
    if (!booking) return { success: false, error: 'Linked booking not found.' }
    if (payment.booking !== bookingId) return { success: false, error: 'The payment does not belong to the selected booking.' }
    if (!hasPermission(actor, PAYMENT_CORRECTION_ROLES) || !actor?.name) return { success: false, error: 'Only the Admin demo role can correct payment records.' }
    if (!reason?.trim()) return { success: false, error: 'A correction reason is required.' }
    const amount = Number(correctedAmount)
    if (!Number.isFinite(amount) || amount < 0) return { success: false, error: 'Enter a valid non-negative payment amount.' }
    const prior = data.paymentAdjustments.filter((item) => item.paymentId === paymentId).reduce((sum, item) => sum + Number(item.difference || 0), 0)
    const previousAmount = Number(payment.amount) + prior
    const difference = amount - previousAmount
    if (!difference) return { success: false, error: 'The corrected amount is unchanged.' }
    if (Number(booking.paid || 0) + difference < 0) return { success: false, error: 'This correction would make the booking paid amount negative.' }
    if (Number(booking.pending || 0) - difference < 0) return { success: false, error: 'This correction exceeds the booking outstanding balance.' }
    const customer = data.customers.find((item) => item.name === payment.customer)
    if (!customer) return { success: false, error: 'The customer linked to this payment could not be found.' }
    const adjustment = { id: `AD-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`, paymentId, bookingId, customerId: customer.id, previousAmount, correctedAmount: amount, difference, reason: reason.trim(), correctedAt: new Date().toISOString(), correctedBy: actor.name, correctedByRole: actor.role }
    const log = auditEntry({ action: 'PAYMENT_AMOUNT_CORRECTED', actor, targetId: paymentId, targetType: 'payment', reason: reason.trim(), changes: { amount: { before: previousAmount, after: amount }, difference, bookingId } })
    setData((current) => ({ ...current, paymentAdjustments: [...current.paymentAdjustments, adjustment], bookings: current.bookings.map((item) => item.id === bookingId ? { ...item, paid: Number(item.paid || 0) + difference, pending: Number(item.pending || 0) - difference } : item), customers: current.customers.map((item) => item.id === customer.id ? { ...item, paid: Number(item.paid || 0) + difference, pending: Number(item.pending || 0) - difference } : item), auditLogs: [...current.auditLogs, log] }))
    return { success: true, adjustment }
  }

  function checkVehicleAvailability({ vehicleId, startAt, endAt, excludeBookingId = null }) {
    const start = new Date(startAt).getTime()
    const end = new Date(endAt).getTime()
    if (!vehicleId || !Number.isFinite(start) || !Number.isFinite(end) || end <= start) {
      return { available: false, error: 'Choose a valid vehicle, start date/time and end date/time.' }
    }
    const vehicle = data.vehicles.find((item) => item.id === vehicleId)
    if (!vehicle) return { available: false, error: 'Vehicle not found.' }
    if (vehicle.availability === 'Maintenance' || vehicle.status === 'Offline') {
      return { available: false, error: `${vehicle.name} is currently unavailable (${vehicle.availability === 'Maintenance' ? 'maintenance' : 'offline'}).` }
    }
    const conflict = data.bookings.find((booking) => {
      if (booking.id === excludeBookingId || !['Confirmed', 'Active'].includes(booking.status)) return false
      const linkedVehicleId = booking.vehicleId || data.vehicles.find((item) => item.name === booking.vehicle)?.id
      if (linkedVehicleId !== vehicleId) return false
      const [existingStart, existingEnd] = bookingInterval(booking)
      return Number.isFinite(existingStart) && Number.isFinite(existingEnd) && intervalsOverlap(start, end, existingStart, existingEnd)
    })
    return conflict
      ? { available: false, error: `This vehicle already has an overlapping booking (${conflict.id}, ${conflict.dates}).` }
      : { available: true, vehicle }
  }

  function createDemoBooking({ customerId, vehicleId, startAt, endAt, type = 'Offline', paid = 0, actor }) {
    const customer = data.customers.find((item) => item.id === customerId)
    if (!customer) return { success: false, error: 'Select a valid customer.' }
    const availability = checkVehicleAvailability({ vehicleId, startAt, endAt })
    if (!availability.available) return { success: false, error: availability.error }
    const start = new Date(startAt)
    const end = new Date(endAt)
    const totalHours = (end.getTime() - start.getTime()) / 3600000
    if (!Number.isFinite(totalHours) || totalHours <= 0) return { success: false, error: 'End date/time must be later than start date/time.' }
    const vehicle = availability.vehicle
    const total = Math.max(1, Math.ceil(totalHours / 24)) * Number(vehicle.price || 0)
    const amountPaid = Number(paid || 0)
    if (!Number.isFinite(amountPaid) || amountPaid < 0 || amountPaid > total) return { success: false, error: `Paid amount must be between ₹0 and ${total.toLocaleString('en-IN')}.` }
    const id = `BK-${Math.max(0, ...data.bookings.map((item) => Number(item.id?.match(/\d+$/)?.[0] || 0))) + 1}`
    const format = (value) => new Date(value).toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
    const booking = {
      id, customer: customer.name, customerId, vehicle: vehicle.name, vehicleId,
      startAt, endAt, dates: `${format(startAt)} – ${format(endAt)}`,
      type, status: 'Confirmed', paid: amountPaid, pending: total - amountPaid,
      totalAmount: total, createdAt: new Date().toISOString(),
    }
    const log = auditEntry({ action: 'BOOKING_CREATED', actor, targetId: id, targetType: 'booking', reason: 'Demo booking created', changes: { vehicleId, startAt, endAt } })
    const paymentId = amountPaid > 0 ? `TX-${Math.max(0, ...data.payments.map((item) => Number(item.id?.match(/\d+$/)?.[0] || 0))) + 1}` : null
    const paymentRecord = amountPaid > 0 ? { id: paymentId, booking: id, customer: customer.name, method: 'Cash', date: new Date().toLocaleDateString('en-US', { month: 'short', day: '2-digit', year: 'numeric' }), amount: amountPaid, status: amountPaid === total ? 'Paid' : 'Partial' } : null
    setData((current) => ({
      ...current,
      bookings: [booking, ...current.bookings],
      payments: paymentRecord ? [paymentRecord, ...current.payments] : current.payments,
      vehicles: current.vehicles.map((item) => item.id === vehicleId ? { ...item, availability: 'Rented' } : item),
      customers: current.customers.map((item) => item.id === customerId ? { ...item, bookings: Number(item.bookings || 0) + 1, active: Number(item.active || 0) + 1, paid: Number(item.paid || 0) + amountPaid, pending: Number(item.pending || 0) + (total - amountPaid) } : item),
      auditLogs: [...current.auditLogs, log],
    }))
    return { success: true, booking }
  }

  function cancelDemoBooking({ bookingId, reason, refundAmount, actor }) {
    const booking = data.bookings.find((item) => item.id === bookingId)
    if (!booking) return { success: false, error: 'Booking not found.' }
    if (!['Confirmed', 'Active'].includes(booking.status)) return { success: false, error: 'Only confirmed or active bookings can be cancelled.' }
    if (!String(reason || '').trim()) return { success: false, error: 'A cancellation reason is required.' }
    const refund = Number(refundAmount || 0)
    if (!Number.isFinite(refund) || refund < 0 || refund > Number(booking.paid || 0)) return { success: false, error: `Refund must be between ₹0 and ${Number(booking.paid || 0).toLocaleString('en-IN')}.` }
    const vehicleId = booking.vehicleId || data.vehicles.find((item) => item.name === booking.vehicle)?.id
    const cancellation = {
      id: `CN-${Date.now()}`, bookingId, reason: reason.trim(), cancelledAt: new Date().toISOString(),
      cancelledBy: actor?.name || 'Demo user', cancelledByRole: actor?.role || 'Unknown',
      refundAmount: refund, refundStatus: refund > 0 ? 'Refund pending (demo)' : 'No refund due',
    }
    const refundEntry = refund > 0 ? { id: `RF-${Date.now()}`, bookingId, customerId: booking.customerId || data.customers.find((item) => item.name === booking.customer)?.id, amount: refund, reason: `Cancellation: ${reason.trim()}`, status: 'Refund pending (demo)', createdAt: cancellation.cancelledAt, createdBy: cancellation.cancelledBy } : null
    const log = auditEntry({ action: 'BOOKING_CANCELLED', actor, targetId: bookingId, targetType: 'booking', reason: reason.trim(), changes: { status: { before: booking.status, after: 'Cancelled' }, refundAmount: refund } })
    const linkedVehicle = data.vehicles.find((item) => item.id === vehicleId)
    const hasOtherActiveBooking = data.bookings.some((item) => {
      if (item.id === bookingId || !['Confirmed', 'Active'].includes(item.status)) return false
      const otherVehicleId = item.vehicleId || data.vehicles.find((v) => v.name === item.vehicle)?.id
      if (otherVehicleId !== vehicleId) return false
      const [a, b] = bookingInterval(item)
      return b > Date.now() && a < b
    })
    const customerId = booking.customerId || data.customers.find((item) => item.name === booking.customer)?.id
    setData((current) => ({
      ...current,
      bookings: current.bookings.map((item) => item.id === bookingId ? { ...item, status: 'Cancelled', cancelledAt: cancellation.cancelledAt, cancellationReason: reason.trim(), refundedAmount: refund, pending: 0 } : item),
      cancellationHistory: [...(current.cancellationHistory || []), cancellation],
      refundAdjustments: refundEntry ? [...(current.refundAdjustments || []), refundEntry] : current.refundAdjustments || [],
      vehicles: current.vehicles.map((item) => item.id === vehicleId ? { ...item, availability: item.availability === 'Maintenance' ? 'Maintenance' : hasOtherActiveBooking ? 'Rented' : 'Available' } : item),
      customers: current.customers.map((item) => item.id === customerId ? { ...item, active: Math.max(0, Number(item.active || 0) - 1), paid: Math.max(0, Number(item.paid || 0) - refund), pending: Math.max(0, Number(item.pending || 0) - Number(booking.pending || 0)) } : item),
      payments: current.payments.map((item) => item.booking === bookingId && refund > 0 ? { ...item, refundStatus: 'Refund pending (demo)' } : item),
      auditLogs: [...current.auditLogs, log],
    }))
    return { success: true, cancellation }
  }

  function getEffectivePaymentAmount(paymentId) {
    const payment = data.payments.find((item) => item.id === paymentId)
    if (!payment) return null
    return Number(payment.amount) + data.paymentAdjustments.filter((item) => item.paymentId === paymentId).reduce((sum, item) => sum + Number(item.difference || 0), 0)
  }
  function getPaymentHistory(paymentId) {
    const payment = data.payments.find((item) => item.id === paymentId)
    if (!payment) return []
    return [{ id: `ORIGINAL-${payment.id}`, type: 'Original payment', amount: Number(payment.amount), date: payment.date, reason: 'Original payment record' }, ...data.paymentAdjustments.filter((item) => item.paymentId === paymentId).map((item) => ({ ...item, type: 'Correction', amount: item.correctedAmount, date: item.correctedAt }))]
  }

  return <DemoDataContext.Provider value={{ ...data, currentDemoUser, currentDemoRole, setCurrentDemoRole, addRecord, updateRecord, updateCustomerDetails, addPaymentAdjustment, getEffectivePaymentAmount, getPaymentHistory, checkVehicleAvailability, createDemoBooking, cancelDemoBooking }}>{children}</DemoDataContext.Provider>
}

export function useDemoData() {
  const context = useContext(DemoDataContext)
  if (!context) throw new Error('useDemoData must be used within DemoDataProvider.')
  return context
}
