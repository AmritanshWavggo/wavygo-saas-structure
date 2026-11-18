import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDemoData } from '../../data/DemoDataContext.jsx'
import { vehicleService } from '../../services/vehicleService.js'
import { maintenanceService } from '../../services/maintenanceService.js'
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
  Wrench,
  X,
  Check,
  Loader2,
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
  const { vehicles, updateRecord, addRecord, deleteRecord, syncVehicles, syncMaintenance } = useDemoData()
  const [activeTab, setActiveTab] = useState('All vehicles')
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('All types')
  const [availabilityFilter, setAvailabilityFilter] = useState('All availability')
  const [selectedVehicle, setSelectedVehicle] = useState(null)
  const [editingVehicle, setEditingVehicle] = useState(null)
  const [editFormData, setEditFormData] = useState({})
  const [editError, setEditError] = useState('')
  const [isSavingEdit, setIsSavingEdit] = useState(false)
  const [notice, setNotice] = useState('')
  const [page, setPage] = useState(1)
  const pageSize = 8

  // Maintenance modal states
  const [maintenanceVehicle, setMaintenanceVehicle] = useState(null)
  const [statusMenuVehicleId, setStatusMenuVehicleId] = useState(null)
  const [maintType, setMaintType] = useState('Scheduled Servicing')
  const [maintIssue, setMaintIssue] = useState('')
  const [maintCost, setMaintCost] = useState('1850')
  const [maintStartDate, setMaintStartDate] = useState(() =>
    new Date().toLocaleDateString('en-US', { month: 'short', day: '2-digit', year: 'numeric' })
  )
  const [maintExpectedDate, setMaintExpectedDate] = useState(() => {
    const d = new Date()
    d.setDate(d.getDate() + 2)
    return d.toLocaleDateString('en-US', { month: 'short', day: '2-digit', year: 'numeric' })
  })
  const [maintPayment, setMaintPayment] = useState('Pending')
  const [maintMechanic, setMaintMechanic] = useState('Indiranagar Service Hub')
  const [maintNotes, setMaintNotes] = useState('')
  const [isSavingMaintenance, setIsSavingMaintenance] = useState(false)
  const [maintenanceError, setMaintenanceError] = useState('')

  function handleOpenMaintenanceModal(vehicle) {
    setMaintenanceError('')
    setMaintenanceVehicle(vehicle)
    setMaintType('Scheduled Servicing')
    setMaintIssue(`Periodic inspection & maintenance for ${vehicle.name || 'vehicle'}`)
    setMaintCost('1850')
    const today = new Date().toLocaleDateString('en-US', { month: 'short', day: '2-digit', year: 'numeric' })
    const nextDays = new Date(Date.now() + 2 * 86400000).toLocaleDateString('en-US', { month: 'short', day: '2-digit', year: 'numeric' })
    setMaintStartDate(today)
    setMaintExpectedDate(nextDays)
    setMaintPayment('Pending')
    setMaintMechanic('Indiranagar Service Hub')
    setMaintNotes('')
  }

  async function handleQuickStatusChange(vehicle, newStatus) {
    setStatusMenuVehicleId(null)
    if (newStatus === 'Maintenance') {
      handleOpenMaintenanceModal(vehicle)
      return
    }
    try {
      await vehicleService.updateVehicle(vehicle.id, { fleetAvailability: newStatus })
      if (updateRecord) {
        updateRecord('vehicles', vehicle.id, { availability: newStatus, fleetAvailability: newStatus })
      }
      if (syncVehicles) {
        await syncVehicles()
      }
      setNotice(`Availability updated: ${vehicle.name} is now ${newStatus}.`)
    } catch (err) {
      setNotice(`Failed to update status: ${err.message || 'Error occurred'}`)
    }
  }

  async function handleSaveMaintenance(e) {
    e.preventDefault()
    if (!maintIssue.trim()) {
      setMaintenanceError('Issue or damage description is required.')
      return
    }
    const cost = parseFloat(maintCost)
    if (isNaN(cost) || cost < 0) {
      setMaintenanceError('Please enter a valid cost (0 or higher).')
      return
    }

    setMaintenanceError('')
    setIsSavingMaintenance(true)
    try {
      const payload = {
        vehicle_id: maintenanceVehicle.id,
        vehicle: maintenanceVehicle.name || maintenanceVehicle.makeModel,
        registration: maintenanceVehicle.registration || maintenanceVehicle.registrationNumber || '',
        type: maintType,
        damage_details: maintIssue.trim(),
        issue: maintIssue.trim(),
        start: maintStartDate.trim(),
        expected: maintExpectedDate.trim() || undefined,
        cost: cost,
        payment: maintPayment,
        status: 'Ongoing',
        mechanic_name: maintMechanic.trim() || undefined,
        notes: maintNotes.trim() || undefined,
      }

      const created = await maintenanceService.createMaintenance(payload)

      if (updateRecord) {
        updateRecord('vehicles', maintenanceVehicle.id, {
          availability: 'Maintenance',
          fleetAvailability: 'Maintenance',
        })
      }

      if (addRecord) {
        addRecord('maintenance', {
          ...created,
          vehicle: maintenanceVehicle.name,
          backendSynced: true,
        })
      }

      await Promise.allSettled([
        syncMaintenance ? syncMaintenance() : Promise.resolve(),
        syncVehicles ? syncVehicles() : Promise.resolve(),
      ])

      setNotice(`Vehicle ${maintenanceVehicle.name} sent to Maintenance! Record ${created.id} is now live in the Maintenance module.`)
      setMaintenanceVehicle(null)
    } catch (err) {
      setMaintenanceError(err.message || 'Failed to record maintenance.')
    } finally {
      setIsSavingMaintenance(false)
    }
  }

  function handleStartEdit(vehicle) {
    setEditError('')
    setEditingVehicle(vehicle)
    setEditFormData({
      makeModel: vehicle.makeModel || vehicle.name || '',
      registration: vehicle.registration || vehicle.registrationNumber || '',
      type: vehicle.type || 'Motorcycle',
      fuel: vehicle.fuel || 'Petrol',
      transmission: vehicle.transmission || 'Manual',
      year: String(vehicle.year || 2024),
      color: vehicle.color || '',
      engineCapacity: vehicle.engineCapacity ? String(vehicle.engineCapacity) : '',
      seats: String(vehicle.seats || 2),
      dailyRate: String(vehicle.price || vehicle.dailyRate || 1000),
      fleetAvailability: vehicle.availability || vehicle.fleetAvailability || 'Available',
      pickupAddress: vehicle.location || vehicle.pickupAddress || 'Indiranagar, Bengaluru',
      minimumDays: String(vehicle.minimumDays || 1),
      showOnWavygo: isListedOnWavyGo(vehicle),
    })
  }

  async function handleSaveVehicle(e) {
    e.preventDefault()
    if (!editFormData.makeModel.trim()) {
      setEditError('Make and model is required.')
      return
    }
    if (!editFormData.registration.trim()) {
      setEditError('Registration number is required.')
      return
    }
    const rate = parseFloat(editFormData.dailyRate)
    if (isNaN(rate) || rate <= 0) {
      setEditError('Please enter a valid positive daily rate.')
      return
    }

    setEditError('')
    setIsSavingEdit(true)
    try {
      const payload = {
        makeModel: editFormData.makeModel.trim(),
        registration: editFormData.registration.trim(),
        registrationNumber: editFormData.registration.trim(),
        type: editFormData.type,
        fuel: editFormData.fuel,
        transmission: editFormData.transmission,
        year: parseInt(editFormData.year, 10) || 2024,
        dailyRate: rate,
        fleetAvailability: editFormData.fleetAvailability,
        showOnWavygo: Boolean(editFormData.showOnWavygo),
        seats: parseInt(editFormData.seats, 10) || 2,
        pickupAddress: editFormData.pickupAddress.trim(),
        minimumDays: parseInt(editFormData.minimumDays, 10) || 1,
      }
      if (editFormData.color) payload.color = editFormData.color.trim()
      if (editFormData.engineCapacity) payload.engineCapacity = parseInt(editFormData.engineCapacity, 10)

      await vehicleService.updateVehicle(editingVehicle.id, payload)

      if (updateRecord) {
        updateRecord('vehicles', editingVehicle.id, {
          ...payload,
          name: payload.makeModel,
          price: rate,
          availability: payload.fleetAvailability,
          status: payload.showOnWavygo ? 'Online' : 'Offline',
          backendSynced: true,
        })
      }

      if (syncVehicles) {
        await syncVehicles()
      }

      setNotice(`Vehicle ${editFormData.makeModel} updated successfully in database!`)
      setEditingVehicle(null)
    } catch (err) {
      setEditError(err.message || 'Failed to update vehicle.')
    } finally {
      setIsSavingEdit(false)
    }
  }

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

  async function toggleStatus(id) {
    const vehicle = vehicles.find((item) => item.id === id)
    if (!vehicle) return
    const listed = isListedOnWavyGo(vehicle)
    const nextState = !listed
    try {
      await vehicleService.toggleShowOnWavygo(id, nextState)
      if (syncVehicles) await syncVehicles()
      else updateRecord('vehicles', id, { showOnWavygo: nextState, show_on_wavygo: nextState, status: nextState ? 'Online' : 'Offline' })
      setNotice(`Listing updated: ${vehicle.name} is now ${nextState ? 'Online on WavyGo' : 'taken Offline'}.`)
    } catch {
      updateRecord('vehicles', id, { showOnWavygo: nextState, show_on_wavygo: nextState, status: nextState ? 'Online' : 'Offline' })
      setNotice('Status updated locally.')
    }
    setPage(1)
  }

  async function handleDeleteVehicle(vehicle) {
    if (!window.confirm(`Are you sure you want to delete ${vehicle.name} (${vehicle.id})?`)) return
    try {
      await vehicleService.deleteVehicle(vehicle.id)
      if (deleteRecord) deleteRecord('vehicles', vehicle.id)
      if (syncVehicles) await syncVehicles()
      setNotice(`Vehicle ${vehicle.name} deleted successfully from database.`)
    } catch (err) {
      setNotice(`Failed to delete vehicle: ${err.message || 'Error occurred'}`)
    }
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
                    <td className="px-4 py-4">
                      <div className="relative inline-block">
                        <button
                          type="button"
                          onClick={() => setStatusMenuVehicleId(statusMenuVehicleId === vehicle.id ? null : vehicle.id)}
                          className={`group inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold transition hover:ring-2 hover:ring-offset-1 ${
                            vehicle.availability === 'Available'
                              ? 'bg-emerald-50 text-emerald-800 hover:ring-emerald-400'
                              : vehicle.availability === 'Rented'
                              ? 'bg-sky-50 text-sky-800 hover:ring-sky-400'
                              : 'bg-amber-50 text-amber-800 hover:ring-amber-400'
                          }`}
                          title="Click to update status or schedule maintenance"
                        >
                          <span
                            className={`size-1.5 rounded-full ${
                              vehicle.availability === 'Available'
                                ? 'bg-emerald-500'
                                : vehicle.availability === 'Rented'
                                ? 'bg-sky-500'
                                : 'bg-amber-500'
                            }`}
                          />
                          {vehicle.availability || 'Available'}
                          <ChevronDown size={11} className="opacity-60 group-hover:opacity-100" />
                        </button>

                        {/* Status popover menu */}
                        {statusMenuVehicleId === vehicle.id && (
                          <div
                            className="absolute left-0 top-full z-30 mt-1 w-44 rounded-xl border border-slate-200 bg-white p-1.5 shadow-lg"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <p className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                              Set Availability
                            </p>
                            <button
                              type="button"
                              onClick={() => handleQuickStatusChange(vehicle, 'Available')}
                              className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-xs font-medium text-slate-700 hover:bg-emerald-50 hover:text-emerald-800"
                            >
                              <span className="size-2 rounded-full bg-emerald-500" />
                              Available
                            </button>
                            <button
                              type="button"
                              onClick={() => handleQuickStatusChange(vehicle, 'Rented')}
                              className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-xs font-medium text-slate-700 hover:bg-sky-50 hover:text-sky-800"
                            >
                              <span className="size-2 rounded-full bg-sky-500" />
                              Rented
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                setStatusMenuVehicleId(null)
                                handleOpenMaintenanceModal(vehicle)
                              }}
                              className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-xs font-semibold text-amber-800 hover:bg-amber-50"
                            >
                              <Wrench size={13} className="text-amber-600" />
                              Maintenance...
                            </button>
                          </div>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-4"><p className="whitespace-nowrap text-sm font-semibold text-slate-800">{vehicle.price != null ? <>₹{Number(vehicle.price).toLocaleString('en-IN')}<span className="font-normal text-slate-400"> / day</span></> : 'Not provided'}</p></td>
                    <td className="px-4 py-4"><button type="button" role="switch" aria-checked={Boolean(isListed)} aria-label={`Show ${vehicle.name} on WavyGo`} onClick={() => toggleStatus(vehicle.id)} className={`relative inline-flex h-6 w-11 items-center rounded-full transition ${isListed ? 'bg-emerald-700' : 'bg-slate-300'}`}><span className={`inline-block size-4 transform rounded-full bg-white shadow transition ${isListed ? 'translate-x-6' : 'translate-x-1'}`} /><span className="sr-only">{isListed ? 'On' : 'Off'}</span></button><span className={`ml-2 text-xs font-semibold ${isListed ? 'text-emerald-800' : 'text-slate-500'}`}>{isListed ? 'On' : 'Off'}</span></td>
                    <td className="px-5 py-4"><div className="flex justify-end gap-1"><button type="button" onClick={() => setSelectedVehicle(vehicle)} className="inline-flex h-8 items-center gap-1 rounded-lg px-2 text-xs font-semibold text-slate-600 hover:bg-slate-100" aria-label={`View ${vehicle.name}`}><Eye size={14} /> View</button><button type="button" onClick={() => handleStartEdit(vehicle)} className="inline-flex h-8 items-center gap-1 rounded-lg px-2 text-xs font-semibold text-slate-600 hover:bg-slate-100" aria-label={`Edit ${vehicle.name}`}><Pencil size={14} /> Edit</button><button type="button" onClick={() => handleOpenMaintenanceModal(vehicle)} className="inline-flex h-8 items-center gap-1 rounded-lg px-2 text-xs font-semibold text-amber-700 hover:bg-amber-50" aria-label={`Maintenance for ${vehicle.name}`} title="Send to Maintenance"><Wrench size={14} /> Service</button><button type="button" onClick={() => handleDeleteVehicle(vehicle)} className="inline-flex h-8 items-center gap-1 rounded-lg px-2 text-xs font-semibold text-rose-600 hover:bg-rose-50" aria-label={`Delete ${vehicle.name}`}><Trash2 size={14} /> Delete</button></div>
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
          <p>Showing <span className="font-semibold text-slate-700">{visibleVehicles.length}</span> of <span className="font-semibold text-slate-700">{filteredVehicles.length}</span> matching vehicles {visibleVehicles.some(v => v.backendSynced) ? '· Database live' : '· preview data'}</p>
          <div className="flex items-center gap-3"><button type="button" disabled={page <= 1} onClick={() => setPage((current) => current - 1)} className="rounded-lg border border-slate-200 px-2.5 py-1.5 font-semibold disabled:opacity-40">Previous</button><span>Page {page} of {pageCount}</span><button type="button" disabled={page >= pageCount} onClick={() => setPage((current) => current + 1)} className="rounded-lg border border-slate-200 px-2.5 py-1.5 font-semibold disabled:opacity-40">Next</button></div>
        </footer>
      </div>

      <div className={`flex items-center gap-3 rounded-xl border px-4 py-3 text-xs leading-5 ${notice ? 'border-amber-200 bg-amber-50 text-amber-900' : 'border-slate-200/70 bg-white/70 text-slate-500'}`}><CircleHelp size={16} className="shrink-0 text-emerald-700" /><p>{notice || (vehicles.some(v => v.backendSynced) ? 'Live mode: Connected to MongoDB database. Listing and fleet availability changes persist in real time.' : 'Connecting to database...')}</p></div>

      {selectedVehicle && <div className="fixed inset-0 z-40 flex items-center justify-center bg-slate-950/35 p-4 backdrop-blur-[2px]" onClick={() => setSelectedVehicle(null)}><article role="dialog" aria-modal="true" aria-labelledby="vehicle-detail-title" onClick={(event) => event.stopPropagation()} className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white p-5 shadow-2xl sm:p-6"><div className="flex items-start justify-between"><div className="flex items-center gap-3"><VehicleArt vehicle={selectedVehicle} /><div><h2 id="vehicle-detail-title" className="font-semibold text-slate-900">{selectedVehicle.name}</h2><p className="mt-1 text-xs text-slate-500">{selectedVehicle.type || 'Type unavailable'}</p></div></div><button type="button" onClick={() => setSelectedVehicle(null)} aria-label="Close details" className="grid size-8 place-items-center rounded-lg text-slate-400 hover:bg-slate-100"><X size={17} /></button></div><div className="mt-5 grid grid-cols-2 gap-3 text-sm">{[['Registration / RC', selectedVehicle.registration], ['Fleet ID', selectedVehicle.id], ['Make / model', selectedVehicle.name], ['Model year', selectedVehicle.year], ['Type', selectedVehicle.type], ['Fuel', selectedVehicle.fuel], ['Color', selectedVehicle.color], ['Engine capacity', selectedVehicle.engineCapacity ? `${selectedVehicle.engineCapacity} cc` : 'Not provided'], ['Seats', selectedVehicle.seats], ['Show on WavyGo', isListedOnWavyGo(selectedVehicle) ? 'On' : 'Off'], ['Fleet availability', selectedVehicle.availability || 'Not provided'], ['Daily rate', selectedVehicle.price ? `₹${Number(selectedVehicle.price).toLocaleString('en-IN')} / day` : 'Not provided'], ['Pickup location', selectedVehicle.location || selectedVehicle.pickupLocation], ['Minimum rental', selectedVehicle.minimumDays ? `${selectedVehicle.minimumDays} days` : 'Not provided']].map(([label, value]) => <div key={label} className="rounded-xl bg-slate-50 p-3"><p className="text-[11px] font-medium text-slate-400">{label}</p><p className="mt-1 font-semibold text-slate-800">{value || 'Not provided'}</p></div>)}</div><section className="mt-5"><h3 className="text-sm font-semibold text-slate-900">Documents</h3>{Array.isArray(selectedVehicle.documents) && selectedVehicle.documents.length ? <ul className="mt-2 space-y-2">{selectedVehicle.documents.map((doc, index) => { const url = typeof doc === 'string' ? doc : doc.url; return <li key={doc.id || doc.name || index} className="flex items-center justify-between rounded-xl border border-slate-100 p-3 text-sm"><span>{doc.name || doc.type || 'Vehicle document'}</span>{url ? <a href={url} target="_blank" rel="noreferrer" className="font-semibold text-emerald-800 hover:underline">Open</a> : <span className="text-xs text-slate-400">File unavailable</span>}</li> })}</ul> : <p className="mt-2 rounded-xl bg-slate-50 p-3 text-sm text-slate-500">No vehicle documents are available.</p>}</section><button type="button" onClick={() => setSelectedVehicle(null)} className="mt-5 h-10 w-full rounded-xl bg-emerald-800 text-sm font-semibold text-white hover:bg-emerald-900">Done</button></article></div>}

      {/* Edit Vehicle Modal */}
      {editingVehicle && (
        <div
          className="fixed inset-0 z-40 flex items-center justify-center bg-slate-950/35 p-4 backdrop-blur-[2px]"
          onClick={() => { if (!isSavingEdit) setEditingVehicle(null) }}
        >
          <article
            role="dialog"
            aria-modal="true"
            aria-labelledby="edit-vehicle-title"
            onClick={(e) => e.stopPropagation()}
            className="max-h-[92vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white p-5 shadow-2xl sm:p-6"
          >
            <div className="flex items-center justify-between border-b border-slate-100 pb-4">
              <div className="flex items-center gap-3">
                <VehicleArt vehicle={editingVehicle} small />
                <div>
                  <h2 id="edit-vehicle-title" className="text-base font-semibold text-slate-900">
                    Edit {editingVehicle.name || 'Vehicle'}
                  </h2>
                  <p className="text-xs text-slate-500">
                    ID: {editingVehicle.id} · Update fleet specs, pricing, and availability
                  </p>
                </div>
              </div>
              <button
                type="button"
                disabled={isSavingEdit}
                onClick={() => setEditingVehicle(null)}
                aria-label="Close"
                className="grid size-8 place-items-center rounded-lg text-slate-400 hover:bg-slate-100"
              >
                <X size={17} />
              </button>
            </div>

            {editError && (
              <div className="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700">
                {editError}
              </div>
            )}

            <form onSubmit={handleSaveVehicle} className="mt-5 space-y-4">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">
                    Make & Model <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={editFormData.makeModel || ''}
                    onChange={(e) => setEditFormData({ ...editFormData, makeModel: e.target.value })}
                    className="h-10 w-full rounded-xl border border-slate-200 px-3 text-xs text-slate-800 outline-none focus:border-emerald-500"
                    placeholder="e.g. KTM 390 Duke"
                  />
                </div>

                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">
                    Registration / Number Plate <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={editFormData.registration || ''}
                    onChange={(e) => setEditFormData({ ...editFormData, registration: e.target.value })}
                    className="h-10 w-full rounded-xl border border-slate-200 px-3 text-xs text-slate-800 outline-none focus:border-emerald-500"
                    placeholder="e.g. KA 01 EK 8812"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">Type</label>
                  <select
                    value={editFormData.type || 'Motorcycle'}
                    onChange={(e) => setEditFormData({ ...editFormData, type: e.target.value })}
                    className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-xs text-slate-800 outline-none focus:border-emerald-500"
                  >
                    <option value="Motorcycle">Motorcycle</option>
                    <option value="Scooter">Scooter</option>
                    <option value="Electric">Electric</option>
                  </select>
                </div>

                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">Fuel</label>
                  <select
                    value={editFormData.fuel || 'Petrol'}
                    onChange={(e) => setEditFormData({ ...editFormData, fuel: e.target.value })}
                    className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-xs text-slate-800 outline-none focus:border-emerald-500"
                  >
                    <option value="Petrol">Petrol</option>
                    <option value="Electric">Electric</option>
                    <option value="Diesel">Diesel</option>
                  </select>
                </div>

                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">Transmission</label>
                  <select
                    value={editFormData.transmission || 'Manual'}
                    onChange={(e) => setEditFormData({ ...editFormData, transmission: e.target.value })}
                    className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-xs text-slate-800 outline-none focus:border-emerald-500"
                  >
                    <option value="Manual">Manual</option>
                    <option value="Automatic">Automatic</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">Daily Rate (₹) *</label>
                  <input
                    type="number"
                    min="1"
                    required
                    value={editFormData.dailyRate || ''}
                    onChange={(e) => setEditFormData({ ...editFormData, dailyRate: e.target.value })}
                    className="h-10 w-full rounded-xl border border-slate-200 px-3 text-xs text-slate-800 outline-none focus:border-emerald-500"
                    placeholder="e.g. 1500"
                  />
                </div>

                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">Fleet Availability</label>
                  <select
                    value={editFormData.fleetAvailability || 'Available'}
                    onChange={(e) => {
                      const val = e.target.value
                      setEditFormData({ ...editFormData, fleetAvailability: val })
                      if (val === 'Maintenance') {
                        setEditingVehicle(null)
                        handleOpenMaintenanceModal(editingVehicle)
                      }
                    }}
                    className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-xs text-slate-800 outline-none focus:border-emerald-500"
                  >
                    <option value="Available">Available</option>
                    <option value="Rented">Rented</option>
                    <option value="Maintenance">Maintenance (Opens repair details)</option>
                    <option value="Under Review">Under Review</option>
                  </select>
                </div>

                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">Model Year</label>
                  <input
                    type="number"
                    min="2000"
                    max="2030"
                    value={editFormData.year || '2024'}
                    onChange={(e) => setEditFormData({ ...editFormData, year: e.target.value })}
                    className="h-10 w-full rounded-xl border border-slate-200 px-3 text-xs text-slate-800 outline-none focus:border-emerald-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">Color</label>
                  <input
                    type="text"
                    value={editFormData.color || ''}
                    onChange={(e) => setEditFormData({ ...editFormData, color: e.target.value })}
                    className="h-10 w-full rounded-xl border border-slate-200 px-3 text-xs text-slate-800 outline-none focus:border-emerald-500"
                    placeholder="e.g. Orange"
                  />
                </div>

                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">Engine (cc)</label>
                  <input
                    type="number"
                    value={editFormData.engineCapacity || ''}
                    onChange={(e) => setEditFormData({ ...editFormData, engineCapacity: e.target.value })}
                    className="h-10 w-full rounded-xl border border-slate-200 px-3 text-xs text-slate-800 outline-none focus:border-emerald-500"
                    placeholder="e.g. 399"
                  />
                </div>

                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">Seats</label>
                  <input
                    type="number"
                    min="1"
                    max="10"
                    value={editFormData.seats || '2'}
                    onChange={(e) => setEditFormData({ ...editFormData, seats: e.target.value })}
                    className="h-10 w-full rounded-xl border border-slate-200 px-3 text-xs text-slate-800 outline-none focus:border-emerald-500"
                  />
                </div>
              </div>

              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">Pickup Address</label>
                <input
                  type="text"
                  value={editFormData.pickupAddress || ''}
                  onChange={(e) => setEditFormData({ ...editFormData, pickupAddress: e.target.value })}
                  className="h-10 w-full rounded-xl border border-slate-200 px-3 text-xs text-slate-800 outline-none focus:border-emerald-500"
                  placeholder="e.g. Indiranagar, Bengaluru"
                />
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="editShowOnWavygo"
                  checked={Boolean(editFormData.showOnWavygo)}
                  onChange={(e) => setEditFormData({ ...editFormData, showOnWavygo: e.target.checked })}
                  className="size-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                />
                <label htmlFor="editShowOnWavygo" className="text-xs font-medium text-slate-700">
                  Show on WavyGo (Online customer rentals)
                </label>
              </div>

              <div className="mt-6 flex justify-end gap-2 border-t border-slate-100 pt-4">
                <button
                  type="button"
                  disabled={isSavingEdit}
                  onClick={() => setEditingVehicle(null)}
                  className="rounded-xl border border-slate-200 px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSavingEdit}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-800 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-emerald-900 disabled:opacity-50"
                >
                  {isSavingEdit ? (
                    <>
                      <Loader2 size={14} className="animate-spin" />
                      Saving...
                    </>
                  ) : (
                    <>
                      <Check size={14} />
                      Save changes
                    </>
                  )}
                </button>
              </div>
            </form>
          </article>
        </div>
      )}

      {/* Add Maintenance Record Modal */}
      {maintenanceVehicle && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4 backdrop-blur-[2px]"
          onClick={() => { if (!isSavingMaintenance) setMaintenanceVehicle(null) }}
        >
          <article
            role="dialog"
            aria-modal="true"
            aria-labelledby="maintenance-modal-title"
            onClick={(e) => e.stopPropagation()}
            className="max-h-[92vh] w-full max-w-xl overflow-y-auto rounded-2xl bg-white p-5 shadow-2xl sm:p-6"
          >
            <div className="flex items-center justify-between border-b border-slate-100 pb-4">
              <div className="flex items-center gap-3">
                <span className="grid size-10 place-items-center rounded-xl bg-amber-50 text-amber-700">
                  <Wrench size={20} />
                </span>
                <div>
                  <h2 id="maintenance-modal-title" className="text-base font-semibold text-slate-900">
                    Schedule Maintenance · {maintenanceVehicle.name}
                  </h2>
                  <p className="text-xs text-slate-500">
                    {maintenanceVehicle.id} · {maintenanceVehicle.registration || 'No plate'} · Automatically logs into Maintenance module
                  </p>
                </div>
              </div>
              <button
                type="button"
                disabled={isSavingMaintenance}
                onClick={() => setMaintenanceVehicle(null)}
                aria-label="Close"
                className="grid size-8 place-items-center rounded-lg text-slate-400 hover:bg-slate-100"
              >
                <X size={17} />
              </button>
            </div>

            {maintenanceError && (
              <div className="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700">
                {maintenanceError}
              </div>
            )}

            <form onSubmit={handleSaveMaintenance} className="mt-5 space-y-4">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">
                    Maintenance Type <span className="text-rose-500">*</span>
                  </label>
                  <select
                    value={maintType}
                    onChange={(e) => setMaintType(e.target.value)}
                    className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-xs text-slate-800 outline-none focus:border-emerald-500"
                  >
                    <option value="Damage Repair">Damage Repair (Accident / Post-rental)</option>
                    <option value="Scheduled Servicing">Scheduled Servicing (Periodic maintenance)</option>
                    <option value="Brake & Tyre Inspection">Brake & Tyre Replacement</option>
                    <option value="Oil & Fluid Replacement">Oil & Fluid Top-up / Replacement</option>
                    <option value="Electrical & Diagnostics">Electrical & Battery Diagnostics</option>
                    <option value="General Inspection">General Inspection / Routine Check</option>
                  </select>
                </div>

                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">
                    Estimated Cost (₹) <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="any"
                    required
                    value={maintCost}
                    onChange={(e) => setMaintCost(e.target.value)}
                    placeholder="e.g. 1850"
                    className="h-10 w-full rounded-xl border border-slate-200 px-3 text-xs text-slate-800 outline-none focus:border-emerald-500"
                  />
                </div>
              </div>

              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">
                  Issue / Damage Description <span className="text-rose-500">*</span>
                </label>
                <textarea
                  required
                  rows={2}
                  value={maintIssue}
                  onChange={(e) => setMaintIssue(e.target.value)}
                  placeholder="Describe the issue, defect, or maintenance scope (e.g. Front brake disc shuddering, oil change due, chain tension loose)"
                  className="w-full rounded-xl border border-slate-200 p-3 text-xs text-slate-800 outline-none focus:border-emerald-500"
                />
              </div>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">
                    Start Date <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={maintStartDate}
                    onChange={(e) => setMaintStartDate(e.target.value)}
                    placeholder="e.g. Oct 31, 2026 or 2026-10-31"
                    className="h-10 w-full rounded-xl border border-slate-200 px-3 text-xs text-slate-800 outline-none focus:border-emerald-500"
                  />
                </div>

                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">
                    Expected Completion Date
                  </label>
                  <input
                    type="text"
                    value={maintExpectedDate}
                    onChange={(e) => setMaintExpectedDate(e.target.value)}
                    placeholder="e.g. Nov 02, 2026 or 2026-11-02"
                    className="h-10 w-full rounded-xl border border-slate-200 px-3 text-xs text-slate-800 outline-none focus:border-emerald-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">
                    Workshop / Garage Name
                  </label>
                  <input
                    type="text"
                    value={maintMechanic}
                    onChange={(e) => setMaintMechanic(e.target.value)}
                    placeholder="e.g. Speedway Hub or In-house Workshop"
                    className="h-10 w-full rounded-xl border border-slate-200 px-3 text-xs text-slate-800 outline-none focus:border-emerald-500"
                  />
                </div>

                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">
                    Payment Status
                  </label>
                  <select
                    value={maintPayment}
                    onChange={(e) => setMaintPayment(e.target.value)}
                    className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-xs text-slate-800 outline-none focus:border-emerald-500"
                  >
                    <option value="Pending">Pending (Pay upon completion)</option>
                    <option value="Paid">Paid (Advance settlement)</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">
                  Additional Notes (Optional)
                </label>
                <input
                  type="text"
                  value={maintNotes}
                  onChange={(e) => setMaintNotes(e.target.value)}
                  placeholder="e.g. Customer reported vibration during return"
                  className="h-10 w-full rounded-xl border border-slate-200 px-3 text-xs text-slate-800 outline-none focus:border-emerald-500"
                />
              </div>

              <div className="mt-6 flex items-center justify-between border-t border-slate-100 pt-4">
                <p className="text-[11px] text-slate-400">
                  Vehicle availability will be set to <span className="font-semibold text-amber-700">Maintenance</span>.
                </p>
                <div className="flex gap-2">
                  <button
                    type="button"
                    disabled={isSavingMaintenance}
                    onClick={() => setMaintenanceVehicle(null)}
                    className="rounded-xl border border-slate-200 px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isSavingMaintenance}
                    className="inline-flex items-center gap-1.5 rounded-xl bg-amber-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-amber-700 disabled:opacity-50"
                  >
                    {isSavingMaintenance ? (
                      <>
                        <Loader2 size={14} className="animate-spin" />
                        Saving...
                      </>
                    ) : (
                      <>
                        <Check size={14} />
                        Send to Maintenance
                      </>
                    )}
                  </button>
                </div>
              </div>
            </form>
          </article>
        </div>
      )}
    </section>
  )
}

export default Vehicles
