import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDemoData } from '../../data/DemoDataContext.jsx'
import {
  ArrowDownUp,
  ArrowRight,
  CalendarDays,
  CarFront,
  Check,
  ChevronDown,
  CircleHelp,
  Ellipsis,
  Filter,
  Gauge,
  Plus,
  Search,
  SlidersHorizontal,
  X,
} from 'lucide-react'

function VehicleArt({ vehicle, small = false }) {
  return (
    <span className={`grid shrink-0 place-items-center overflow-hidden rounded-2xl bg-gradient-to-br from-emerald-50 to-green-100 ${small ? 'size-12 text-2xl' : 'size-14 text-[29px]'}`} aria-hidden="true">
      {vehicle.image?.startsWith?.('data:') || vehicle.image?.startsWith?.('blob:') || vehicle.image?.startsWith?.('http')
        ? <img src={vehicle.image} alt="" className="h-full w-full object-cover" />
        : vehicle.image || '🏍️'}
    </span>
  )
}

function Vehicles() {
  const navigate = useNavigate()
  const { vehicles, updateRecord } = useDemoData()
  const [activeTab, setActiveTab] = useState('All vehicles')
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('All types')
  const [statusFilter, setStatusFilter] = useState('All statuses')
  const [selectedVehicle, setSelectedVehicle] = useState(null)
  const [openMenu, setOpenMenu] = useState('')

  const filteredVehicles = useMemo(() => {
    const query = search.trim().toLowerCase()
    return vehicles.filter((vehicle) => {
      const matchesTab = activeTab === 'All vehicles' || vehicle.status === activeTab
      const matchesType = typeFilter === 'All types' || vehicle.type === typeFilter
      const matchesStatus = statusFilter === 'All statuses' || vehicle.status === statusFilter
      const matchesSearch = !query || [vehicle.name, vehicle.registration, vehicle.id, vehicle.type, vehicle.availability].some((field) => String(field || '').toLowerCase().includes(query))
      return matchesTab && matchesType && matchesStatus && matchesSearch
    })
  }, [vehicles, activeTab, search, typeFilter, statusFilter])

  const counts = {
    all: vehicles.length,
    online: vehicles.filter((vehicle) => vehicle.status === 'Online').length,
    offline: vehicles.filter((vehicle) => vehicle.status === 'Offline').length,
  }

  function toggleStatus(id) {
    const vehicle = vehicles.find((item) => item.id === id)
    if (vehicle) updateRecord('vehicles', id, { status: vehicle.status === 'Online' ? 'Offline' : 'Online' })
    setOpenMenu('')
  }

  const tabs = [
    { label: 'All vehicles', count: counts.all },
    { label: 'Online', count: counts.online },
    { label: 'Offline', count: counts.offline },
  ]

  return (
    <section className="space-y-6 pb-8 text-slate-800">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-emerald-700">
            <span className="size-1.5 rounded-full bg-emerald-500" /> Fleet management
          </div>
          <h1 className="text-3xl font-semibold tracking-tight text-slate-900">Vehicles</h1>
          <p className="mt-1.5 max-w-xl text-sm leading-6 text-slate-500">Manage your fleet, availability and daily pricing from one place.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={() => navigate('/app/bookings/new', { state: { offline: true } })} className="inline-flex h-11 items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 shadow-sm transition hover:border-emerald-200 hover:bg-emerald-50">
            <CalendarDays size={16} className="text-emerald-700" /> Offline booking
          </button>
          <button type="button" onClick={() => navigate('/app/vehicles/new')} className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-emerald-800 px-4 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-900">
            <Plus size={17} /> Add vehicle
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {[
          { label: 'Total vehicles', value: counts.all, foot: 'Across all vehicle types', icon: CarFront, tone: 'bg-emerald-50 text-emerald-800' },
          { label: 'Online now', value: counts.online, foot: 'Available for new bookings', icon: Check, tone: 'bg-green-50 text-green-800' },
          { label: 'Offline', value: counts.offline, foot: 'Not currently bookable', icon: Gauge, tone: 'bg-amber-50 text-amber-800' },
        ].map(({ label, value, foot, icon: Icon, tone }) => (
          <article key={label} className="flex items-center justify-between rounded-2xl border border-slate-200/80 bg-white p-4 shadow-[0_2px_10px_rgba(15,23,42,0.025)] sm:p-5">
            <div><p className="text-sm font-medium text-slate-500">{label}</p><p className="mt-1 text-2xl font-semibold tracking-tight text-slate-900">{value}</p><p className="mt-1 text-xs text-slate-400">{foot}</p></div>
            <span className={`grid size-11 place-items-center rounded-xl ${tone}`}><Icon size={19} /></span>
          </article>
        ))}
      </div>

      <div className="overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-[0_4px_22px_rgba(15,23,42,0.035)]">
        <div className="flex flex-col gap-4 border-b border-slate-100 px-4 pt-4 sm:px-6 sm:pt-5">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-base font-semibold text-slate-900">Your fleet <span className="ml-1 text-sm font-medium text-slate-400">{vehicles.length}</span></h2>
              <p className="mt-1 text-xs text-slate-500">Shared demo fleet · changes appear across workspace screens</p>
            </div>
            <button type="button" onClick={() => { setTypeFilter('All types'); setStatusFilter('All statuses'); setSearch(''); setActiveTab('All vehicles') }} className="inline-flex items-center gap-2 rounded-lg px-2 py-1.5 text-xs font-semibold text-slate-500 hover:bg-slate-50 hover:text-slate-800"><SlidersHorizontal size={14} /> Reset filters</button>
          </div>
          <div className="flex gap-5 overflow-x-auto">
            {tabs.map(({ label, count }) => (
              <button type="button" key={label} onClick={() => setActiveTab(label)} className={`relative flex shrink-0 items-center gap-2 pb-3 text-sm font-semibold transition ${activeTab === label ? 'text-emerald-800' : 'text-slate-500 hover:text-slate-800'}`}>
                {label}<span className={`rounded-full px-2 py-0.5 text-[11px] ${activeTab === label ? 'bg-emerald-50 text-emerald-800' : 'bg-slate-100 text-slate-500'}`}>{count}</span>
                {activeTab === label && <span className="absolute inset-x-0 bottom-0 h-0.5 rounded-full bg-emerald-700" />}
              </button>
            ))}
          </div>
        </div>

        <div className="grid gap-3 border-b border-slate-100 p-4 sm:grid-cols-[minmax(220px,1fr)_180px_180px] sm:px-6">
          <label className="relative block">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search name, plate or location…" className="h-10 w-full rounded-xl border border-slate-200 bg-slate-50/50 pl-9 pr-3 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-emerald-400 focus:bg-white focus:ring-3 focus:ring-emerald-100" />
          </label>
          <label className="relative">
            <Filter size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)} className="h-10 w-full appearance-none rounded-xl border border-slate-200 bg-white pl-9 pr-8 text-sm text-slate-700 outline-none focus:border-emerald-400 focus:ring-3 focus:ring-emerald-100">
              {['All types', 'Motorcycle', 'Scooter', 'Electric'].map((option) => <option key={option}>{option}</option>)}
            </select><ChevronDown size={14} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400" />
          </label>
          <label className="relative">
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} className="h-10 w-full appearance-none rounded-xl border border-slate-200 bg-white px-3 pr-8 text-sm text-slate-700 outline-none focus:border-emerald-400 focus:ring-3 focus:ring-emerald-100">
              {['All statuses', 'Online', 'Offline'].map((option) => <option key={option}>{option}</option>)}
            </select><ChevronDown size={14} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400" />
          </label>
        </div>

        {filteredVehicles.length ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[850px] border-collapse text-left">
              <thead><tr className="bg-slate-50/80 text-[11px] font-semibold uppercase tracking-[0.11em] text-slate-400">
                <th className="px-6 py-3.5">Vehicle <ArrowDownUp size={12} className="ml-1 inline" /></th><th className="px-4 py-3.5">Vehicle type</th><th className="px-4 py-3.5">Fleet availability</th><th className="px-4 py-3.5">Daily rate</th><th className="px-4 py-3.5">Listing status</th><th className="px-5 py-3.5 text-right"> </th>
              </tr></thead>
              <tbody className="divide-y divide-slate-100">
                {filteredVehicles.map((vehicle) => (
                  <tr key={vehicle.id} className="group transition hover:bg-emerald-50/25">
                    <td className="px-6 py-4"><div className="flex items-center gap-3"><VehicleArt vehicle={vehicle} small /><div className="min-w-0"><p className="whitespace-nowrap text-sm font-semibold text-slate-900">{vehicle.name}</p><p className="mt-1 text-xs text-slate-500">{vehicle.registration} <span className="mx-1 text-slate-300">·</span>{vehicle.id}</p></div></div></td>
                    <td className="px-4 py-4"><p className="text-sm font-medium text-slate-700">{vehicle.type}</p><p className="mt-1 text-xs text-slate-400">Two-wheeler</p></td>
                    <td className="px-4 py-4"><span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${vehicle.availability === 'Available' ? 'bg-emerald-50 text-emerald-800' : vehicle.availability === 'Rented' ? 'bg-sky-50 text-sky-800' : 'bg-amber-50 text-amber-800'}`}>{vehicle.availability || 'Available'}</span></td>
                    <td className="px-4 py-4"><p className="whitespace-nowrap text-sm font-semibold text-slate-800">₹{Number(vehicle.price || 0).toLocaleString('en-IN')}<span className="font-normal text-slate-400"> / day</span></p></td>
                    <td className="px-4 py-4"><button type="button" onClick={() => toggleStatus(vehicle.id)} aria-label={`Set ${vehicle.name} ${vehicle.status === 'Online' ? 'offline' : 'online'}`} className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold transition ${vehicle.status === 'Online' ? 'bg-emerald-50 text-emerald-800 hover:bg-emerald-100' : 'bg-slate-100 text-slate-500 hover:bg-slate-200'}`}><span className={`size-1.5 rounded-full ${vehicle.status === 'Online' ? 'bg-emerald-500' : 'bg-slate-400'}`} />{vehicle.status}</button></td>
                    <td className="relative px-5 py-4 text-right">
                      <button type="button" aria-label={`Actions for ${vehicle.name}`} onClick={() => setOpenMenu(openMenu === vehicle.id ? '' : vehicle.id)} className="grid size-8 place-items-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-700"><Ellipsis size={18} /></button>
                      {openMenu === vehicle.id && <div className="absolute right-8 top-12 z-10 w-44 rounded-xl border border-slate-200 bg-white p-1.5 text-left shadow-lg"><button type="button" onClick={() => { setSelectedVehicle(vehicle); setOpenMenu('') }} className="w-full rounded-lg px-3 py-2 text-left text-xs font-medium text-slate-700 hover:bg-slate-50">View vehicle details</button><button type="button" onClick={() => toggleStatus(vehicle.id)} className="w-full rounded-lg px-3 py-2 text-left text-xs font-medium text-slate-700 hover:bg-slate-50">Set {vehicle.status === 'Online' ? 'offline' : 'online'}</button></div>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="px-5 py-16 text-center sm:py-20">
            <span className="mx-auto grid size-14 place-items-center rounded-2xl bg-emerald-50 text-emerald-800"><Search size={22} /></span>
            <h3 className="mt-4 text-base font-semibold text-slate-900">No vehicles match those filters</h3>
            <p className="mx-auto mt-1.5 max-w-sm text-sm leading-6 text-slate-500">Try another search or reset your filters to see your full fleet.</p>
            <button type="button" onClick={() => { setTypeFilter('All types'); setStatusFilter('All statuses'); setSearch(''); setActiveTab('All vehicles') }} className="mt-4 text-sm font-semibold text-emerald-800 hover:text-emerald-950">Clear filters</button>
          </div>
        )}
        <footer className="flex flex-col gap-3 border-t border-slate-100 px-4 py-3.5 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <p>Showing <span className="font-semibold text-slate-700">{filteredVehicles.length}</span> of <span className="font-semibold text-slate-700">{vehicles.length}</span> vehicles <span className="ml-1 text-slate-400">· demo data</span></p>
          <button type="button" onClick={() => navigate('/app/vehicles/new')} className="inline-flex items-center gap-1 self-start font-semibold text-emerald-800 hover:text-emerald-950 sm:self-auto">Add another vehicle <ArrowRight size={14} /></button>
        </footer>
      </div>

      <div className="flex items-center gap-3 rounded-xl border border-slate-200/70 bg-white/70 px-4 py-3 text-xs leading-5 text-slate-500"><CircleHelp size={16} className="shrink-0 text-emerald-700" /><p><span className="font-semibold text-slate-700">Preview mode.</span> This screen uses the shared demo fleet. Status changes and vehicles you add are reflected in this workspace session.</p></div>

      {selectedVehicle && <div className="fixed inset-0 z-40 flex items-center justify-center bg-slate-950/35 p-4 backdrop-blur-[2px]" onClick={() => setSelectedVehicle(null)}><article role="dialog" aria-modal="true" aria-labelledby="vehicle-detail-title" onClick={(event) => event.stopPropagation()} className="w-full max-w-md rounded-2xl bg-white p-5 shadow-2xl sm:p-6"><div className="flex items-start justify-between"><div className="flex items-center gap-3"><VehicleArt vehicle={selectedVehicle} /><div><h2 id="vehicle-detail-title" className="font-semibold text-slate-900">{selectedVehicle.name}</h2><p className="mt-1 text-xs text-slate-500">{selectedVehicle.type}</p></div></div><button type="button" onClick={() => setSelectedVehicle(null)} aria-label="Close details" className="grid size-8 place-items-center rounded-lg text-slate-400 hover:bg-slate-100"><X size={17} /></button></div><div className="mt-5 grid grid-cols-2 gap-3 text-sm">{[['Registration', selectedVehicle.registration], ['Fleet ID', selectedVehicle.id], ['Type', selectedVehicle.type], ['Availability', selectedVehicle.availability || 'Available'], ['Listing status', selectedVehicle.status], ['Rate', `₹${Number(selectedVehicle.price || 0).toLocaleString('en-IN')} / day`]].map(([label, value]) => <div key={label} className="rounded-xl bg-slate-50 p-3"><p className="text-[11px] font-medium text-slate-400">{label}</p><p className="mt-1 font-semibold text-slate-800">{value}</p></div>)}</div><button type="button" onClick={() => setSelectedVehicle(null)} className="mt-5 h-10 w-full rounded-xl bg-emerald-800 text-sm font-semibold text-white hover:bg-emerald-900">Done</button></article></div>}
    </section>
  )
}

export default Vehicles
