import { useState } from 'react'
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
import {
  BarChart,
  Button,
  Card,
  FilterSelect,
  MetricCard,
  PageHeader,
  StatusBadge,
} from '../../components/ui/Workspace.jsx'

const revenueTrend = [
  { label: 'May', value: 18600 },
  { label: 'Jun', value: 22900 },
  { label: 'Jul', value: 21300 },
  { label: 'Aug', value: 28600 },
  { label: 'Sep', value: 31700 },
  { label: 'Oct', value: 35400 },
]

function Dashboard() {
  const { bookings, vehicles } = useDemoData()
  const [dateRange, setDateRange] = useState('Last 30 days')
  const rentedVehicles = vehicles.filter((vehicle) => vehicle.availability === 'Rented')
  const availableVehicles = vehicles.filter((vehicle) => vehicle.availability === 'Available')
  const activeBookings = bookings.filter((booking) => booking.status === 'Active')
  const monthlyRevenue = revenueTrend[revenueTrend.length - 1].value

  return (
    <div>
      <PageHeader
        eyebrow="MONDAY, OCTOBER 12, 2026"
        title="Good morning, WavyGo"
        description="Here's what's happening across your rental business today."
        action={
          <div className="flex flex-wrap gap-2">
            <FilterSelect value={dateRange} onChange={setDateRange} options={['Last 7 days', 'Last 30 days', 'This month', 'Last 90 days']} />
            <Link to="/app/bookings/new">
              <Button>
                <Plus size={16} aria-hidden="true" />
                New booking
              </Button>
            </Link>
          </div>
        }
      />

      <div className="mb-5 flex flex-wrap items-center gap-2 rounded-xl border border-amber-200/80 bg-amber-50/70 px-4 py-2.5 text-xs text-amber-800">
        <span className="rounded-full bg-amber-100 px-2 py-0.5 font-semibold uppercase tracking-wide text-[10px]">
          Demo workspace
        </span>
        Illustrative figures and sample records only — no live business data or API is connected.
      </div>

      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4 sm:gap-4">
        <MetricCard label="Total vehicles" value={vehicles.length} caption="Demo fleet" icon={Bike} tone="navy" />
        <MetricCard label="Available vehicles" value={availableVehicles.length} caption="Ready for a booking" icon={Check} tone="green" />
        <MetricCard label="Active bookings" value={activeBookings.length} caption="Sample active rentals" icon={CalendarDays} tone="blue" />
        <MetricCard label="Revenue" value={`₹${monthlyRevenue.toLocaleString('en-IN')}`} caption="Illustrative October revenue" icon={CircleDollarSign} tone="violet" />
      </div>

      <div className="mt-5 grid gap-4 xl:grid-cols-[minmax(0,1.65fr)_minmax(300px,0.9fr)]">
        <Card className="min-w-0 p-5 sm:p-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Revenue overview</h2>
              <p className="mt-1 text-xs text-slate-500">Booking revenue · {dateRange}</p>
            </div>
            <button type="button" aria-label="More revenue options" className="grid size-8 place-items-center rounded-lg text-slate-400 hover:bg-slate-100">
              <MoreHorizontal size={18} aria-hidden="true" />
            </button>
          </div>
          <div className="mt-4 flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-[30px] font-semibold tracking-tight text-slate-900">₹{monthlyRevenue.toLocaleString('en-IN')}</p>
              <p className="mt-1 inline-flex items-center gap-1 text-xs font-medium text-emerald-700">
                <ArrowUpRight size={14} aria-hidden="true" />
                12.8% <span className="font-normal text-slate-400">vs. previous month</span>
              </p>
            </div>
            <div className="rounded-xl bg-amber-50 px-3.5 py-2.5">
              <p className="text-[10px] font-medium uppercase tracking-wide text-amber-700">Pending payments</p>
              <p className="mt-1 text-lg font-semibold text-slate-900">₹18,450</p>
            </div>
          </div>
          <div className="mt-3">
            <BarChart data={revenueTrend} label="Illustrative monthly booking revenue trend" />
          </div>
        </Card>

        <Card className="p-5 sm:p-6">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Upcoming bookings</h2>
              <p className="mt-1 text-xs text-slate-500">Your next customer handovers</p>
            </div>
            <Link to="/app/bookings" className="inline-flex items-center gap-1 text-xs font-medium text-emerald-800 hover:text-emerald-950">
              See all <ChevronRight size={14} aria-hidden="true" />
            </Link>
          </div>
          <div className="mt-4 divide-y divide-slate-100">
            {bookings.slice(0, 4).map((booking, index) => (
              <div key={booking.id} className="flex items-center gap-3 py-3.5 first:pt-0 last:pb-0">
                <div className={`grid size-10 shrink-0 place-items-center rounded-xl text-lg ${index % 2 ? 'bg-emerald-50' : 'bg-slate-100'}`}>
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
            {bookings.length === 0 && <p className="py-8 text-center text-xs text-slate-500">No upcoming bookings in this demo.</p>}
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
            <Link to="/app/vehicles" className="inline-flex items-center gap-1 text-xs font-medium text-emerald-800">
              Fleet <ChevronRight size={14} aria-hidden="true" />
            </Link>
          </div>
          <div className="mt-4 grid gap-2.5 sm:grid-cols-2">
            {(rentedVehicles.length ? rentedVehicles : vehicles.slice(0, 2)).map((vehicle) => (
              <div key={vehicle.id} className="flex items-center gap-3 rounded-xl border border-slate-100 p-3">
                <span className="grid size-10 place-items-center rounded-xl bg-emerald-50 text-xl">{vehicle.image}</span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-semibold text-slate-800">{vehicle.name}</p>
                  <p className="mt-1 text-[11px] text-slate-400">{vehicle.registration}</p>
                </div>
                <StatusBadge status={vehicle.availability} />
              </div>
            ))}
          </div>
        </Card>

        <Card className="p-5 sm:p-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Quick overview</h2>
              <p className="mt-1 text-xs text-slate-500">Workspace activity at a glance</p>
            </div>
            <span className="grid size-9 place-items-center rounded-xl bg-emerald-50 text-emerald-700">
              <CircleDollarSign size={17} aria-hidden="true" />
            </span>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-3">
            <div className="rounded-xl bg-slate-50 p-3.5">
              <p className="text-[11px] text-slate-500">Bookings this month</p>
              <p className="mt-1.5 text-xl font-semibold text-slate-900">164</p>
              <p className="mt-1 text-[10px] text-emerald-700">↑ 8% vs. September</p>
            </div>
            <div className="rounded-xl bg-slate-50 p-3.5">
              <p className="text-[11px] text-slate-500">Fleet utilization</p>
              <p className="mt-1.5 text-xl font-semibold text-slate-900">74%</p>
              <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-200">
                <div className="h-full w-[74%] rounded-full bg-emerald-600" />
              </div>
            </div>
          </div>
          <div className="mt-3 flex items-center gap-2 rounded-xl border border-slate-100 px-3 py-2.5 text-xs text-slate-500">
            <MapPin size={14} aria-hidden="true" className="text-emerald-700" />
            Ahmedabad, Gujarat <span className="ml-auto text-[10px] text-slate-400">Demo location</span>
            <Clock3 size={13} aria-hidden="true" />
          </div>
        </Card>
      </div>
    </div>
  )
}

export default Dashboard
