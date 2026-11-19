import { useEffect, useMemo, useState } from 'react'
import {
  ArrowUpRight,
  Bike,
  CalendarDays,
  Check,
  ChevronRight,
  CircleDollarSign,
  Clock3,
  MapPin,
  MoreHorizontal,
  Plus,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { useDemoData } from '../../data/DemoDataContext.jsx'
import { dashboardService } from '../../services/dashboardService.js'
import { tenantService } from '../../services/tenantService.js'
import {
  BarChart,
  Button,
  Card,
  FilterSelect,
  MetricCard,
  PageHeader,
  StatusBadge,
} from '../../components/ui/Workspace.jsx'

function formatArrivalCountdown(arrival, now) {
  if (arrival.status === 'Arrived') return 'Marked as arrived'
  const difference = arrival.expectedAt - now
  const minutes = Math.ceil(Math.abs(difference) / 60_000)
  const hours = Math.floor(minutes / 60)
  const remainingMinutes = minutes % 60
  const duration = hours ? `${hours}h ${remainingMinutes}m` : `${remainingMinutes}m`
  return difference < 0 ? `Delayed by ${duration}` : `In ${duration}`
}

function Dashboard() {
  const {
    bookings = [],
    vehicles = [],
    payments = [],
    customers = [],
    staff = [],
    updateRecord,
    syncVehicles,
    syncOfflineBookings,
  } = useDemoData()
  const [dateRange, setDateRange] = useState('Last 30 days')
  const [backendStats, setBackendStats] = useState(null)
  const [vendorProfile, setVendorProfile] = useState(null)
  const [arrivalFilter, setArrivalFilter] = useState('All Upcoming')
  const [arrivals, setArrivals] = useState([])
  const [updatingArrivalId, setUpdatingArrivalId] = useState(null)
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    let active = true
    tenantService
      .getCurrentTenant()
      .then((profile) => {
        if (active && profile) setVendorProfile(profile)
      })
      .catch(() => {})
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 15_000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    if (backendStats?.upcoming_arrivals && Array.isArray(backendStats.upcoming_arrivals)) {
      setArrivals(backendStats.upcoming_arrivals)
    }
  }, [backendStats])

  const arrivalWindow = arrivalFilter === 'Next 1 Hour' ? 60 : arrivalFilter === 'Next 2 Hours' ? 120 : null
  const visibleArrivals = arrivals.filter((arrival) => {
    if (arrival.status === 'Arrived') return false
    if (arrivalWindow === null) return true
    const minutesUntilArrival = (arrival.expectedAt - now) / 60_000
    return minutesUntilArrival >= 0 && minutesUntilArrival <= arrivalWindow
  })

  async function handleMarkArrived(arrival) {
    if (!arrival?.bookingId) return
    setUpdatingArrivalId(arrival.bookingId)
    try {
      // 1. Immediately update local UI state
      setArrivals((current) =>
        current.map((item) =>
          item.bookingId === arrival.bookingId ? { ...item, status: 'Arrived' } : item,
        ),
      )

      // 2. Immediately update in DemoDataContext (Booking -> Completed, Vehicle -> Under Review)
      if (updateRecord) {
        updateRecord('bookings', arrival.bookingId, { status: 'Completed', arrival_status: 'Arrived' })
        const vId = arrival.vehicleId || arrival.vehicle?.id
        if (vId) {
          updateRecord('vehicles', vId, { availability: 'Under Review', fleetAvailability: 'Under Review' })
        }
      }

      // 3. Inform backend API
      await dashboardService.markArrival(arrival.bookingId)

      // 4. Re-sync live data from backend
      if (syncVehicles) await syncVehicles()
      if (syncOfflineBookings) await syncOfflineBookings()
      const stats = await dashboardService.getStats(dateRange)
      if (stats) setBackendStats(stats)
    } catch (err) {
      console.warn('Backend mark arrival notice:', err)
    } finally {
      setUpdatingArrivalId(null)
    }
  }

  useEffect(() => {
    let active = true
    async function loadStats() {
      try {
        const stats = await dashboardService.getStats(dateRange)
        if (active && stats) {
          setBackendStats(stats)
        }
      } catch (err) {
        console.warn('Dashboard backend sync notice:', err)
      }
    }
    loadStats()
    return () => {
      active = false
    }
  }, [dateRange, bookings.length, vehicles.length, payments.length])

  const rentedVehicles = vehicles.filter((v) => v.availability === 'Rented')
  const availableVehicles = vehicles.filter((v) => v.availability === 'Available')
  const activeBookings = bookings.filter((b) => b.status === 'Active')

  // Calculations with live backend prioritization
  const nowForRange = new Date()
  const rangeStart = (() => {
    if (dateRange === 'This month') return new Date(nowForRange.getFullYear(), nowForRange.getMonth(), 1)
    const days = dateRange === 'Last 7 days' ? 7 : dateRange === 'Last 90 days' ? 90 : 30
    const start = new Date(nowForRange)
    start.setHours(0, 0, 0, 0)
    start.setDate(start.getDate() - days + 1)
    return start
  })()
  const recordDateInRange = (record) => {
    const rawDate = record.created_at || record.date || record.payment_date
    if (!rawDate) return false
    const parsed = new Date(rawDate)
    return !Number.isNaN(parsed.getTime()) && parsed >= rangeStart && parsed <= nowForRange
  }
  const cancelledBookingIds = new Set(
    bookings
      .filter((booking) => String(booking.status || '').toLowerCase() === 'cancelled')
      .map((booking) => String(booking.id)),
  )
  const excludedPaymentStatuses = new Set(['cancelled', 'failed', 'pending', 'unpaid', 'refunded', 'refund'])
  const confirmedPayments = payments.filter((payment) => {
    const status = String(payment.status || 'Paid').toLowerCase()
    return !excludedPaymentStatuses.has(status)
      && !cancelledBookingIds.has(String(payment.booking || payment.booking_id || ''))
      && recordDateInRange(payment)
  })
  const totalPaidRevenue =
    backendStats?.total_revenue ??
    (confirmedPayments.length > 0
      ? confirmedPayments.reduce((sum, payment) => sum + (Number(payment.amount) || 0), 0)
      : bookings
          .filter((booking) => String(booking.status || '').toLowerCase() !== 'cancelled' && recordDateInRange(booking))
          .reduce((sum, booking) => sum + (Number(booking.paid) || 0), 0))

  const pendingPayments =
    backendStats?.pending_payments ??
    bookings
      .filter((booking) => String(booking.status || '').toLowerCase() !== 'cancelled' && recordDateInRange(booking))
      .reduce((sum, b) => sum + (Number(b.pending) || 0), 0)

  const fleetUtilization =
    backendStats?.fleet_utilization ??
    (vehicles.length > 0 ? Math.round((rentedVehicles.length / vehicles.length) * 100) : 0)

  const totalVehiclesCount = backendStats?.total_vehicles ?? vehicles.length
  const availableVehiclesCount = backendStats?.available_vehicles ?? availableVehicles.length
  const activeBookingsCount = backendStats?.active_bookings ?? activeBookings.length

  const todayDate = new Date().toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  }).toUpperCase()

  // Dynamic monthly trend data computed from backend or real payments
  const revenueTrend = useMemo(() => {
    if (Array.isArray(backendStats?.revenue_trend) && backendStats.revenue_trend.length > 0) {
      return backendStats.revenue_trend
    }
    const now = new Date()
    const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    const last6 = []
    for (let i = 5; i >= 0; i--) {
      const d = new Date(now.getFullYear(), now.getMonth() - i, 1)
      last6.push({
        year: d.getFullYear(),
        month: d.getMonth(),
        label: monthNames[d.getMonth()],
        value: 0,
      })
    }
    confirmedPayments.forEach((p) => {
      const amt = Number(p.amount) || 0
      if (!amt) return
      const pDate = p.date ? new Date(p.date) : null
      if (pDate && !isNaN(pDate.getTime())) {
        const match = last6.find((m) => m.year === pDate.getFullYear() && m.month === pDate.getMonth())
        if (match) match.value += amt
      }
    })
    const totalAgg = last6.reduce((s, m) => s + m.value, 0)
    if (totalAgg === 0 && totalPaidRevenue > 0) {
      last6[last6.length - 1].value = totalPaidRevenue
    }
    return last6.map(({ label, value }) => ({ label, value: Math.round(value) }))
  }, [backendStats?.revenue_trend, payments, totalPaidRevenue])

  const recentBookingsList = backendStats?.recent_bookings || bookings.slice(0, 4)
  const rentedDisplayList =
    backendStats?.rented_vehicles_list?.length > 0
      ? backendStats.rented_vehicles_list
      : rentedVehicles

  const storedBusiness = localStorage.getItem('wavygo-business-name') || ''
  const storedOwner = localStorage.getItem('wavygo-owner-name') || ''
  const userEmail = sessionStorage.getItem('wavygo-user-email') || ''
  const emailName = userEmail ? userEmail.split('@')[0] : ''
  const partnerGreeting =
    vendorProfile?.businessName ||
    vendorProfile?.ownerName ||
    storedBusiness ||
    storedOwner ||
    emailName ||
    'there'

  return (
    <div>
      <PageHeader
        eyebrow={todayDate}
        title={`Good day, ${partnerGreeting}`}
        description="Here is what is happening across your rental fleet and bookings today."
        action={
          <div className="flex flex-wrap gap-2">
            <FilterSelect
              value={dateRange}
              onChange={setDateRange}
              options={['Last 7 days', 'Last 30 days', 'This month', 'Last 90 days']}
            />
            <Link to="/app/bookings/new">
              <Button>
                <Plus size={16} aria-hidden="true" />
                New booking
              </Button>
            </Link>
          </div>
        }
      />

      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4 sm:gap-4">
        <MetricCard
          label="Total vehicles"
          value={totalVehiclesCount}
          caption="Total fleet size"
          icon={Bike}
          tone="navy"
        />
        <MetricCard
          label="Available vehicles"
          value={availableVehiclesCount}
          caption="Ready for customer booking"
          icon={Check}
          tone="green"
        />
        <MetricCard
          label="Active bookings"
          value={activeBookingsCount}
          caption="Vehicles on the road"
          icon={CalendarDays}
          tone="blue"
        />
        <MetricCard
          label="Total revenue"
          value={`₹${totalPaidRevenue.toLocaleString('en-IN')}`}
          caption="Total collections"
          icon={CircleDollarSign}
          tone="violet"
        />
      </div>

      <div className="mt-5 grid gap-4 xl:grid-cols-[minmax(0,1.65fr)_minmax(300px,0.9fr)]">
        <Card className="min-w-0 p-5 sm:p-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Revenue overview</h2>
              <p className="mt-1 text-xs text-slate-500">Booking revenue · {dateRange}</p>
            </div>
            <button
              type="button"
              aria-label="More revenue options"
              className="grid size-8 place-items-center rounded-lg text-slate-400 hover:bg-slate-100"
            >
              <MoreHorizontal size={18} aria-hidden="true" />
            </button>
          </div>
          <div className="mt-4 flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-[30px] font-semibold tracking-tight text-slate-900">
                ₹{totalPaidRevenue.toLocaleString('en-IN')}
              </p>
              <p className="mt-1 inline-flex items-center gap-1 text-xs font-medium text-emerald-700">
                <ArrowUpRight size={14} aria-hidden="true" />
                Live synced <span className="font-normal text-slate-400">with payments</span>
              </p>
            </div>
            <div className="rounded-xl bg-amber-50 px-3.5 py-2.5">
              <p className="text-[10px] font-medium uppercase tracking-wide text-amber-700">
                Pending payments
              </p>
              <p className="mt-1 text-lg font-semibold text-slate-900">
                ₹{pendingPayments.toLocaleString('en-IN')}
              </p>
            </div>
          </div>
          <div className="mt-3">
            <BarChart data={revenueTrend} label="Monthly booking revenue trend" />
          </div>
        </Card>

        <Card className="p-5 sm:p-6">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Recent bookings</h2>
              <p className="mt-1 text-xs text-slate-500">Latest customer handovers</p>
            </div>
            <Link
              to="/app/bookings"
              className="inline-flex items-center gap-1 text-xs font-medium text-emerald-800 hover:text-emerald-950"
            >
              See all <ChevronRight size={14} aria-hidden="true" />
            </Link>
          </div>
          <div className="mt-4 divide-y divide-slate-100">
            {recentBookingsList.map((booking, index) => (
              <div key={booking.id} className="flex items-center gap-3 py-3.5 first:pt-0 last:pb-0">
                <div
                  className={`grid size-10 shrink-0 place-items-center rounded-xl text-lg ${
                    index % 2 ? 'bg-emerald-50' : 'bg-slate-100'
                  }`}
                >
                  {index % 2 ? '🏍️' : '🛵'}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-semibold text-slate-800">{booking.customer}</p>
                  <p className="mt-1 truncate text-[11px] text-slate-400">{booking.vehicle}</p>
                </div>
                <div className="text-right">
                  <StatusBadge status={booking.status} />
                  <p className="mt-1 text-[10px] text-slate-400">{booking.dates}</p>
                </div>
              </div>
            ))}
            {recentBookingsList.length === 0 && (
              <div className="py-10 text-center">
                <p className="text-xs font-medium text-slate-600">No bookings recorded yet</p>
                <p className="mt-1 text-[11px] text-slate-400">
                  Create your first rental booking with the button above.
                </p>
              </div>
            )}
          </div>
        </Card>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <Card className="p-5 sm:p-6">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Currently rented</h2>
              <p className="mt-1 text-xs text-slate-500">Vehicles out on a booking</p>
            </div>
            <Link
              to="/app/vehicles"
              className="inline-flex items-center gap-1 text-xs font-medium text-emerald-800"
            >
              Fleet <ChevronRight size={14} aria-hidden="true" />
            </Link>
          </div>
          <div className="mt-4 grid gap-2.5 sm:grid-cols-2">
            {rentedDisplayList.map((vehicle) => (
              <div
                key={vehicle.id}
                className="flex items-center gap-3 rounded-xl border border-slate-100 p-3"
              >
                <span className="grid size-10 place-items-center rounded-xl bg-emerald-50 text-xl">
                  {vehicle.image || '🛵'}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-semibold text-slate-800">{vehicle.name}</p>
                  <p className="mt-1 text-[11px] text-slate-400">{vehicle.registration}</p>
                </div>
                <StatusBadge status={vehicle.availability} />
              </div>
            ))}
            {rentedDisplayList.length === 0 && (
              <p className="col-span-2 py-6 text-center text-xs text-slate-400">
                No vehicles registered in fleet yet.
              </p>
            )}
          </div>
        </Card>

        <Card className="p-5 sm:p-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Quick overview</h2>
              <p className="mt-1 text-xs text-slate-500">Fleet activity at a glance</p>
            </div>
            <span className="grid size-9 place-items-center rounded-xl bg-emerald-50 text-emerald-700">
              <CircleDollarSign size={17} aria-hidden="true" />
            </span>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-3">
            <div className="rounded-xl bg-slate-50 p-3.5">
              <p className="text-[11px] text-slate-500">Total Bookings</p>
              <p className="mt-1.5 text-xl font-semibold text-slate-900">{bookings.length}</p>
              <p className="mt-1 text-[10px] text-emerald-700">Live records</p>
            </div>
            <div className="rounded-xl bg-slate-50 p-3.5">
              <p className="text-[11px] text-slate-500">Fleet utilization</p>
              <p className="mt-1.5 text-xl font-semibold text-slate-900">{fleetUtilization}%</p>
              <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-200">
                <div
                  className="h-full rounded-full bg-emerald-600 transition-all"
                  style={{ width: `${Math.min(fleetUtilization, 100)}%` }}
                />
              </div>
            </div>
          </div>
          <div className="mt-3 flex items-center gap-2 rounded-xl border border-slate-100 px-3 py-2.5 text-xs text-slate-500">
            <MapPin size={14} aria-hidden="true" className="text-emerald-700" />
            Fleet Operations Hub <span className="ml-auto text-[10px] text-emerald-600 font-medium">Online</span>
            <Clock3 size={13} aria-hidden="true" />
          </div>
        </Card>
      </div>

      <Card className="mt-4 overflow-hidden p-5 sm:p-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-slate-900">Upcoming Bikes / Vehicles</h2>
            <p className="mt-1 text-xs text-slate-500">Illustrative arrival schedule · local demo records</p>
          </div>
          <FilterSelect
            label="Show"
            value={arrivalFilter}
            onChange={setArrivalFilter}
            options={['Next 1 Hour', 'Next 2 Hours', 'All Upcoming']}
          />
        </div>
        <div className="mt-4 space-y-3">
          {visibleArrivals.map((arrival) => {
            const status = arrival.status === 'Arrived'
              ? 'Arrived'
              : arrival.expectedAt < now ? 'Delayed' : 'Upcoming'
            return (
              <article key={arrival.bookingId} className="rounded-xl border border-slate-100 p-4">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="flex min-w-0 items-center gap-3">
                    <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-emerald-50 text-xl">
                      {arrival.vehicle?.image || '🏍️'}
                    </span>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-slate-900">{arrival.vehicle?.name || 'Sample vehicle'}</p>
                      <p className="mt-1 text-xs text-slate-500">
                        Vehicle ID {arrival.vehicle?.id || arrival.vehicleId} · {arrival.vehicle?.registration || 'Registration not available'}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 sm:justify-end">
                    <StatusBadge status={status} />
                    <span className="text-xs font-medium text-slate-600">{formatArrivalCountdown(arrival, now)}</span>
                    <Button
                      type="button"
                      variant={status === 'Arrived' ? 'secondary' : 'quiet'}
                      className="min-h-8 px-2.5 text-xs"
                      disabled={status === 'Arrived' || updatingArrivalId === arrival.bookingId}
                      onClick={() => handleMarkArrived(arrival)}
                    >
                      {status === 'Arrived'
                        ? 'Arrived'
                        : updatingArrivalId === arrival.bookingId
                          ? 'Updating...'
                          : 'Mark as Arrived'}
                    </Button>
                  </div>
                </div>
                <div className="mt-3 grid gap-x-5 gap-y-2 border-t border-slate-100 pt-3 text-xs sm:grid-cols-2 lg:grid-cols-4">
                  <p><span className="text-slate-400">Booking ID</span><span className="ml-1.5 font-medium text-slate-700">{arrival.bookingId}</span></p>
                  <p><span className="text-slate-400">Customer</span><span className="ml-1.5 font-medium text-slate-700">{arrival.customer?.name || 'Not available'}</span></p>
                  <p><span className="text-slate-400">Contact</span><span className="ml-1.5 font-medium text-slate-700">{arrival.customer?.phone || 'Not available'}</span></p>
                  <p><span className="text-slate-400">Expected arrival</span><span className="ml-1.5 font-medium text-slate-700">{new Date(arrival.expectedAt).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}</span></p>
                  <p><span className="text-slate-400">Pickup location</span><span className="ml-1.5 font-medium text-slate-700">{arrival.pickupLocation}</span></p>
                  <p><span className="text-slate-400">Return location</span><span className="ml-1.5 font-medium text-slate-700">{arrival.returnLocation}</span></p>
                  <p><span className="text-slate-400">Assigned staff</span><span className="ml-1.5 font-medium text-slate-700">{arrival.staff?.name || 'Not assigned'}</span></p>
                </div>
              </article>
            )
          })}
          {visibleArrivals.length === 0 && (
            <p className="rounded-xl border border-dashed border-slate-200 px-4 py-8 text-center text-xs text-slate-500">
              No vehicles are expected within this time window.
            </p>
          )}
          {arrivalFilter === 'All Upcoming' && arrivals.some((arrival) => arrival.status === 'Arrived') && (
            <div className="space-y-2 border-t border-slate-100 pt-3">
              <p className="text-xs font-semibold text-slate-700">Arrived this session</p>
              {arrivals.filter((arrival) => arrival.status === 'Arrived').map((arrival) => (
                <div key={arrival.bookingId} className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-emerald-50/60 px-3 py-2">
                  <p className="text-xs font-medium text-slate-700">
                    {arrival.vehicle?.name || 'Sample vehicle'} · {arrival.bookingId}
                  </p>
                  <StatusBadge status="Arrived" />
                </div>
              ))}
            </div>
          )}
        </div>
      </Card>
    </div>
  )
}

export default Dashboard
