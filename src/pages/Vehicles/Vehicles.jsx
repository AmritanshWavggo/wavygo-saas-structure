import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDemoData } from '../../data/DemoDataContext.jsx'
import {
  ArrowDownUp,
  ArrowRight,
  CalendarDays,
  CarFront,
  ChevronDown,
  CircleHelp,
  Eye,
  Filter,
  Pencil,
  Plus,
  Search,
  SlidersHorizontal,
  Trash2,
  X,
} from 'lucide-react'

function VehicleArt({ vehicle, small = false }) {
  const [imageError, setImageError] = useState(false)
  // Only render known browser-loadable URL schemes; fall back to the vehicle icon on failure.
  const imageUrl = typeof vehicle.image === 'string' && /^(https?:|data:image\/|blob:)/i.test(vehicle.image)

  return (
    <span className={`grid shrink-0 place-items-center overflow-hidden rounded-2xl bg-gradient-to-br from-emerald-50 to-green-100 text-emerald-800 ${small ? 'size-12' : 'size-14'}`}>
      {imageUrl && !imageError
        ? <img src={vehicle.image} alt={`${vehicle.name || 'Vehicle'} photo`} className="h-full w-full object-cover" onError={() => setImageError(true)} />
        : <CarFront size={small ? 21 : 26} aria-hidden="true" />}
    </span>
  )
}

function isListedOnWavyGo(vehicle) {
  // Prefer an explicit API-shaped flag; legacy demo records use status as their listing signal.
  const listingValue = vehicle.show_on_wavygo ?? vehicle.showOnWavyGo
  return typeof listingValue === 'boolean' ? listingValue : vehicle.status === 'Online'
}

function Vehicles() {
  const navigate = useNavigate()
  const { vehicles, updateRecord } = useDemoData()
  const [activeTab, setActiveTab] = useState('All vehicles')
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('All types')
  const [availabilityFilter, setAvailabilityFilter] = useState('All availability')
  const [selectedVehicle, setSelectedVehicle] = useState(null)
  const [notice, setNotice] = useState('')
  const [page, setPage] = useState(1)
  const pageSize = 8

  // Apply the tab, type, availability, and text query together before slicing the current page.
  const filteredVehicles = useMemo(() => {
    const query = search.trim().toLowerCase()
    return vehicles.filter((vehicle) => {
      const isListed = isListedOnWavyGo(vehicle)
      const matchesTab = activeTab === 'All vehicles' || (activeTab === 'Online' ? isListed : !isListed)
      const matchesType = typeFilter === 'All types' || vehicle.type === typeFilter
      const matchesAvailability = availabilityFilter === 'All availability' || vehicle.availability === availabilityFilter
      const matchesSearch = !query || [vehicle.name, vehicle.registration, vehicle.id, vehicle.type, vehicle.availability].some((field) => String(field || '').toLowerCase().includes(query))
      return matchesTab && matchesType && matchesAvailability && matchesSearch
    })
  }, [vehicles, activeTab, search, typeFilter, availabilityFilter])

  const pageCount = Math.max(1, Math.ceil(filteredVehicles.length / pageSize))
  const visibleVehicles = filteredVehicles.slice((page - 1) * pageSize, page * pageSize)
  const counts = {
    all: vehicles.length,
    online: vehicles.filter(isListedOnWavyGo).length,
    offline: vehicles.filter((vehicle) => !isListedOnWavyGo(vehicle)).length,
  }

  function toggleStatus(id) {
    const vehicle = vehicles.find((item) => item.id === id)
    if (!vehicle) return
    const listed = isListedOnWavyGo(vehicle)
    // This is a session-only preview update, not a persisted WavyGo listing change.
    updateRecord('vehicles', id, { show_on_wavygo: !listed })
    setPage(1)
    setNotice('Preview only: no vehicle listing API is configured, so this change is not saved to WavyGo.')
  }

  function resetFilters() {
    setTypeFilter('All types')
    setAvailabilityFilter('All availability')
    setSearch('')
    setActiveTab('All vehicles')
    setPage(1)
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

      <div className="overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-[0_4px_22px_rgba(15,23,42,0.035)]">
        <div className="flex flex-col gap-4 border-b border-slate-100 px-4 pt-4 sm:px-6 sm:pt-5">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-base font-semibold text-slate-900">Your fleet <span className="ml-1 text-sm font-medium text-slate-400">{vehicles.length}</span></h2>
              <p className="mt-1 text-xs text-slate-500">Preview fleet · listing updates are not connected to an API</p>
            </div>
            <button type="button" onClick={resetFilters} className="inline-flex items-center gap-2 rounded-lg px-2 py-1.5 text-xs font-semibold text-slate-500 hover:bg-slate-50 hover:text-slate-800"><SlidersHorizontal size={14} /> Reset filters</button>
          </div>
          <div className="flex gap-5 overflow-x-auto">
            {tabs.map(({ label, count }) => (
              <button type="button" key={label} onClick={() => { setActiveTab(label); setPage(1) }} className={`relative flex shrink-0 items-center gap-2 pb-3 text-sm font-semibold transition ${activeTab === label ? 'text-emerald-800' : 'text-slate-500 hover:text-slate-800'}`}>
                {label}<span className={`rounded-full px-2 py-0.5 text-[11px] ${activeTab === label ? 'bg-emerald-50 text-emerald-800' : 'bg-slate-100 text-slate-500'}`}>{count}</span>
                {activeTab === label && <span className="absolute inset-x-0 bottom-0 h-0.5 rounded-full bg-emerald-700" />}
              </button>
            ))}
          </div>
        </div>

        <div className="grid gap-3 border-b border-slate-100 p-4 sm:grid-cols-[minmax(220px,1fr)_180px_180px] sm:px-6">
          <label className="relative block">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input value={search} onChange={(event) => { setSearch(event.target.value); setPage(1) }} placeholder="Search name, plate or location…" className="h-10 w-full rounded-xl border border-slate-200 bg-slate-50/50 pl-9 pr-3 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-emerald-400 focus:bg-white focus:ring-3 focus:ring-emerald-100" />
          </label>
          <label className="relative">
            <Filter size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <select value={typeFilter} onChange={(event) => { setTypeFilter(event.target.value); setPage(1) }} className="h-10 w-full appearance-none rounded-xl border border-slate-200 bg-white pl-9 pr-8 text-sm text-slate-700 outline-none focus:border-emerald-400 focus:ring-3 focus:ring-emerald-100">
              {['All types', 'Motorcycle', 'Scooter', 'Electric'].map((option) => <option key={option}>{option}</option>)}
            </select><ChevronDown size={14} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400" />
          </label>
          <label className="relative">
            <select value={availabilityFilter} onChange={(event) => { setAvailabilityFilter(event.target.value); setPage(1) }} className="h-10 w-full appearance-none rounded-xl border border-slate-200 bg-white px-3 pr-8 text-sm text-slate-700 outline-none focus:border-emerald-400 focus:ring-3 focus:ring-emerald-100">
              {['All availability', 'Available', 'Rented', 'Maintenance'].map((option) => <option key={option}>{option}</option>)}
            </select><ChevronDown size={14} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400" />
          </label>
        </div>

        {filteredVehicles.length ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[850px] border-collapse text-left">
              <thead><tr className="bg-slate-50/80 text-[11px] font-semibold uppercase tracking-[0.11em] text-slate-400">
                <th className="px-6 py-3.5">Vehicle <ArrowDownUp size={12} className="ml-1 inline" /></th><th className="px-4 py-3.5">Vehicle type</th><th className="px-4 py-3.5">Fleet availability</th><th className="px-4 py-3.5">Daily rate</th><th className="px-4 py-3.5">Show on WavyGo</th><th className="px-5 py-3.5 text-right">Actions</th>
              </tr></thead>
              <tbody className="divide-y divide-slate-100">
                {visibleVehicles.map((vehicle) => {
                  const isListed = isListedOnWavyGo(vehicle)
                  return (
                  <tr key={vehicle.id} className="group transition hover:bg-emerald-50/25">
                    <td className="px-6 py-4"><div className="flex items-center gap-3"><VehicleArt vehicle={vehicle} small /><div className="min-w-0"><p className="whitespace-nowrap text-sm font-semibold text-slate-900">{vehicle.name || 'Name unavailable'}</p><p className="mt-1 text-xs text-slate-500">{vehicle.registration || 'Registration unavailable'} <span className="mx-1 text-slate-300">·</span>{vehicle.id || 'ID unavailable'}</p></div></div></td>
                    <td className="px-4 py-4"><p className="text-sm font-medium text-slate-700">{vehicle.type}</p><p className="mt-1 text-xs text-slate-400">Two-wheeler</p></td>
                    <td className="px-4 py-4"><span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${vehicle.availability === 'Available' ? 'bg-emerald-50 text-emerald-800' : vehicle.availability === 'Rented' ? 'bg-sky-50 text-sky-800' : 'bg-amber-50 text-amber-800'}`}>{vehicle.availability || 'Not provided'}</span></td>
                    <td className="px-4 py-4"><p className="whitespace-nowrap text-sm font-semibold text-slate-800">{vehicle.price != null ? <>₹{Number(vehicle.price).toLocaleString('en-IN')}<span className="font-normal text-slate-400"> / day</span></> : 'Not provided'}</p></td>
                    <td className="px-4 py-4"><button type="button" role="switch" aria-checked={Boolean(isListed)} aria-label={`Show ${vehicle.name} on WavyGo`} onClick={() => toggleStatus(vehicle.id)} className={`relative inline-flex h-6 w-11 items-center rounded-full transition ${isListed ? 'bg-emerald-700' : 'bg-slate-300'}`}><span className={`inline-block size-4 transform rounded-full bg-white shadow transition ${isListed ? 'translate-x-6' : 'translate-x-1'}`} /><span className="sr-only">{isListed ? 'On' : 'Off'}</span></button><span className={`ml-2 text-xs font-semibold ${isListed ? 'text-emerald-800' : 'text-slate-500'}`}>{isListed ? 'On' : 'Off'}</span></td>
                    <td className="px-5 py-4"><div className="flex justify-end gap-1"><button type="button" onClick={() => setSelectedVehicle(vehicle)} className="inline-flex h-8 items-center gap-1 rounded-lg px-2 text-xs font-semibold text-slate-600 hover:bg-slate-100" aria-label={`View ${vehicle.name}`}><Eye size={14} /> View</button><button type="button" onClick={() => { setNotice('Vehicle editing is unavailable until a vehicle update API is provided.') }} className="inline-flex h-8 items-center gap-1 rounded-lg px-2 text-xs font-semibold text-slate-600 hover:bg-slate-100" aria-label={`Edit ${vehicle.name}`}><Pencil size={14} /> Edit</button><button type="button" onClick={() => { setNotice('Vehicle deletion is unavailable until a vehicle delete API is provided.') }} className="inline-flex h-8 items-center gap-1 rounded-lg px-2 text-xs font-semibold text-rose-600 hover:bg-rose-50" aria-label={`Delete ${vehicle.name}`}><Trash2 size={14} /> Delete</button></div>
                    </td>
                  </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="px-5 py-16 text-center sm:py-20">
            <span className="mx-auto grid size-14 place-items-center rounded-2xl bg-emerald-50 text-emerald-800"><Search size={22} /></span>
            <h3 className="mt-4 text-base font-semibold text-slate-900">No vehicles match those filters</h3>
            <p className="mx-auto mt-1.5 max-w-sm text-sm leading-6 text-slate-500">Try another search or reset your filters to see your full fleet.</p>
            <button type="button" onClick={resetFilters} className="mt-4 text-sm font-semibold text-emerald-800 hover:text-emerald-950">Clear filters</button>
          </div>
        )}
        <footer className="flex flex-col gap-3 border-t border-slate-100 px-4 py-3.5 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <p>Showing <span className="font-semibold text-slate-700">{visibleVehicles.length}</span> of <span className="font-semibold text-slate-700">{filteredVehicles.length}</span> matching vehicles · preview data</p>
          <div className="flex items-center gap-3"><button type="button" disabled={page <= 1} onClick={() => setPage((current) => current - 1)} className="rounded-lg border border-slate-200 px-2.5 py-1.5 font-semibold disabled:opacity-40">Previous</button><span>Page {page} of {pageCount}</span><button type="button" disabled={page >= pageCount} onClick={() => setPage((current) => current + 1)} className="rounded-lg border border-slate-200 px-2.5 py-1.5 font-semibold disabled:opacity-40">Next</button></div>
        </footer>
      </div>

      <div className={`flex items-center gap-3 rounded-xl border px-4 py-3 text-xs leading-5 ${notice ? 'border-amber-200 bg-amber-50 text-amber-900' : 'border-slate-200/70 bg-white/70 text-slate-500'}`}><CircleHelp size={16} className="shrink-0 text-emerald-700" /><p>{notice || 'Preview mode: this screen uses workspace sample data. Listing changes only update this browser session; no vehicle API is configured.'}</p></div>

      {selectedVehicle && <div className="fixed inset-0 z-40 flex items-center justify-center bg-slate-950/35 p-4 backdrop-blur-[2px]" onClick={() => setSelectedVehicle(null)}><article role="dialog" aria-modal="true" aria-labelledby="vehicle-detail-title" onClick={(event) => event.stopPropagation()} className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white p-5 shadow-2xl sm:p-6"><div className="flex items-start justify-between"><div className="flex items-center gap-3"><VehicleArt vehicle={selectedVehicle} /><div><h2 id="vehicle-detail-title" className="font-semibold text-slate-900">{selectedVehicle.name}</h2><p className="mt-1 text-xs text-slate-500">{selectedVehicle.type || 'Type unavailable'}</p></div></div><button type="button" onClick={() => setSelectedVehicle(null)} aria-label="Close details" className="grid size-8 place-items-center rounded-lg text-slate-400 hover:bg-slate-100"><X size={17} /></button></div><div className="mt-5 grid grid-cols-2 gap-3 text-sm">{[['Registration / RC', selectedVehicle.registration], ['Fleet ID', selectedVehicle.id], ['Make / model', selectedVehicle.name], ['Model year', selectedVehicle.year], ['Type', selectedVehicle.type], ['Fuel', selectedVehicle.fuel], ['Color', selectedVehicle.color], ['Engine capacity', selectedVehicle.engineCapacity ? `${selectedVehicle.engineCapacity} cc` : 'Not provided'], ['Seats', selectedVehicle.seats], ['Show on WavyGo', isListedOnWavyGo(selectedVehicle) ? 'On' : 'Off'], ['Fleet availability', selectedVehicle.availability || 'Not provided'], ['Daily rate', selectedVehicle.price ? `₹${Number(selectedVehicle.price).toLocaleString('en-IN')} / day` : 'Not provided'], ['Pickup location', selectedVehicle.location || selectedVehicle.pickupLocation], ['Minimum rental', selectedVehicle.minimumDays ? `${selectedVehicle.minimumDays} days` : 'Not provided']].map(([label, value]) => <div key={label} className="rounded-xl bg-slate-50 p-3"><p className="text-[11px] font-medium text-slate-400">{label}</p><p className="mt-1 font-semibold text-slate-800">{value || 'Not provided'}</p></div>)}</div><section className="mt-5"><h3 className="text-sm font-semibold text-slate-900">Documents</h3>{Array.isArray(selectedVehicle.documents) && selectedVehicle.documents.length ? <ul className="mt-2 space-y-2">{selectedVehicle.documents.map((doc, index) => { const url = typeof doc === 'string' ? doc : doc.url; return <li key={doc.id || doc.name || index} className="flex items-center justify-between rounded-xl border border-slate-100 p-3 text-sm"><span>{doc.name || doc.type || 'Vehicle document'}</span>{url ? <a href={url} target="_blank" rel="noreferrer" className="font-semibold text-emerald-800 hover:underline">Open</a> : <span className="text-xs text-slate-400">File unavailable</span>}</li> })}</ul> : <p className="mt-2 rounded-xl bg-slate-50 p-3 text-sm text-slate-500">No vehicle documents are available.</p>}</section><button type="button" onClick={() => setSelectedVehicle(null)} className="mt-5 h-10 w-full rounded-xl bg-emerald-800 text-sm font-semibold text-white hover:bg-emerald-900">Done</button></article></div>}
    </section>
  )
}

export default Vehicles
