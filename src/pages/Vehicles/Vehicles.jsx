
import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate } from 'react-router-dom'
import { useDemoData } from '../../data/DemoDataContext.jsx'
import { vehicleService } from '../../services/vehicleService.js'
import { maintenanceService } from '../../services/maintenanceService.js'
import {
  ArrowDownUp,
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

const AVAILABILITY_OPTIONS = ['Available', 'Rented', 'Under Review', 'Maintenance']

function VehicleArt({ vehicle, small = false }) {
  const [imageError, setImageError] = useState(false)

  const imageUrl =
    typeof vehicle.image === 'string' &&
    /^(https?:|data:image\/|blob:)/i.test(vehicle.image)

  return (
    <span
      className={`grid shrink-0 place-items-center overflow-hidden rounded-2xl bg-gradient-to-br from-emerald-50 to-green-100 text-emerald-800 ${
        small ? 'size-12' : 'size-14'
      }`}
    >
      {imageUrl && !imageError ? (
        <img
          src={vehicle.image}
          alt={`${vehicle.name || 'Vehicle'} photo`}
          className="h-full w-full object-cover"
          onError={() => setImageError(true)}
        />
      ) : (
        <CarFront size={small ? 21 : 26} aria-hidden="true" />
      )}
    </span>
  )
}

function isListedOnWavyGo(vehicle) {
  const listingValue = vehicle.show_on_wavygo ?? vehicle.showOnWavyGo

  return typeof listingValue === 'boolean'
    ? listingValue
    : vehicle.status === 'Online'
}

/**
 * Availability menu rendered through document.body.
 * This prevents parent table overflow and stacking contexts
 * from clipping the dropdown.
 */
function AvailabilityDropdown({ vehicle, onSelect }) {
  const [open, setOpen] = useState(false)
  const [position, setPosition] = useState(null)

  const triggerRef = useRef(null)
  const menuRef = useRef(null)

  useEffect(() => {
    if (!open) return

    function updatePosition() {
      const trigger = triggerRef.current
      if (!trigger) return

      const rect = trigger.getBoundingClientRect()
      const viewportWidth = window.innerWidth
      const viewportHeight = window.innerHeight

      const menuWidth = Math.min(190, viewportWidth - 24)
      const menuMaxHeight = Math.min(180, viewportHeight - 24)

      const spaceBelow = viewportHeight - rect.bottom
      const spaceAbove = rect.top

      const showBelow =
        spaceBelow >= Math.min(menuMaxHeight, 150) ||
        spaceBelow >= spaceAbove

      const left = Math.max(
        12,
        Math.min(rect.left, viewportWidth - menuWidth - 12)
      )

      const top = showBelow
        ? Math.min(rect.bottom + 8, viewportHeight - menuMaxHeight - 12)
        : Math.max(12, rect.top - menuMaxHeight - 8)

      setPosition({
        top,
        left,
        width: menuWidth,
        maxHeight: menuMaxHeight,
      })
    }

    function handleOutsideClick(event) {
      if (
        triggerRef.current?.contains(event.target) ||
        menuRef.current?.contains(event.target)
      ) {
        return
      }

      setOpen(false)
    }

    function handleKeyDown(event) {
      if (event.key === 'Escape') {
        setOpen(false)
        triggerRef.current?.focus()
      }
    }

    updatePosition()

    document.addEventListener('pointerdown', handleOutsideClick)
    document.addEventListener('keydown', handleKeyDown)
    window.addEventListener('resize', updatePosition)
    window.addEventListener('scroll', updatePosition, true)

    return () => {
      document.removeEventListener('pointerdown', handleOutsideClick)
      document.removeEventListener('keydown', handleKeyDown)
      window.removeEventListener('resize', updatePosition)
      window.removeEventListener('scroll', updatePosition, true)
    }
  }, [open])

  function handleSelect(value) {
    onSelect(vehicle.id, value)
    setOpen(false)
  }

  const menu = open && position
    ? createPortal(
        <div
          ref={menuRef}
          role="listbox"
          aria-label={`Availability for ${vehicle.name}`}
          className="fixed z-[9999] overflow-y-auto rounded-xl border border-slate-200 bg-white p-1.5 shadow-[0_12px_35px_rgba(15,23,42,0.18)]"
          style={{
            top: position.top,
            left: position.left,
            width: position.width,
            maxHeight: position.maxHeight,
          }}
        >
          <p className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
            Set availability
          </p>

          {AVAILABILITY_OPTIONS.map((option) => {
            const selected = vehicle.availability === option

            const optionStyles = {
              Available: 'text-emerald-700',
              Rented: 'text-sky-700',
              'Under Review': 'text-purple-700',
              Maintenance: 'text-amber-700',
            }

            const dotStyles = {
              Available: 'bg-emerald-500',
              Rented: 'bg-sky-500',
              'Under Review': 'bg-purple-500',
              Maintenance: 'bg-amber-500',
            }

            return (
              <button
                key={option}
                type="button"
                role="option"
                aria-selected={selected}
                onClick={() => handleSelect(option)}
                className={`flex min-h-10 w-full items-center justify-between gap-3 rounded-lg px-3 py-2 text-left text-sm transition hover:bg-slate-50 ${
                  selected
                    ? 'bg-emerald-50/70 font-semibold'
                    : 'font-medium text-slate-700'
                }`}
              >
                <span className="flex items-center gap-2.5">
                  <span
                    className={`size-2 rounded-full ${dotStyles[option]}`}
                  />
                  <span className={optionStyles[option]}>{option}</span>
                </span>

                {selected && (
                  <span className="text-xs font-semibold text-emerald-700">
                    Current
                  </span>
                )}
              </button>
            )
          })}
        </div>,
        document.body
      )
    : null

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={`Set availability for ${vehicle.name}`}
        onClick={() => setOpen((current) => !current)}
        className="inline-flex min-h-9 min-w-[142px] items-center justify-between gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 shadow-sm transition hover:border-emerald-300 hover:bg-emerald-50/50 focus:outline-none focus:ring-2 focus:ring-emerald-200"
      >
        <span className="flex items-center gap-2">
          <span
            className={`size-2 rounded-full ${
              vehicle.availability === 'Available'
                ? 'bg-emerald-500'
                : vehicle.availability === 'Rented'
                  ? 'bg-sky-500'
                  : 'bg-amber-500'
            }`}
          />
          {vehicle.availability || 'Not provided'}
        </span>

        <ChevronDown
          size={14}
          className={`shrink-0 text-slate-400 transition-transform ${
            open ? 'rotate-180' : ''
          }`}
        />
      </button>

      {menu}
    </>
  )
}

function Vehicles() {
  const navigate = useNavigate()
  const {
    vehicles = [],
    updateRecord,
    deleteRecord,
    syncVehicles = () => {},
    vehiclesLoading = false,
    vehiclesError = null,
  } = useDemoData()

  const [activeTab, setActiveTab] = useState('All vehicles')
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('All types')
  const [availabilityFilter, setAvailabilityFilter] =
    useState('All availability')
  const [selectedVehicle, setSelectedVehicle] = useState(null)
  const [editingVehicle, setEditingVehicle] = useState(null)
  const [editFormData, setEditFormData] = useState({})
  const [editError, setEditError] = useState('')
  const [isSavingEdit, setIsSavingEdit] = useState(false)
  const [vehicleToDelete, setVehicleToDelete] = useState(null)
  const [isDeleting, setIsDeleting] = useState(false)
  const [notice, setNotice] = useState('')
  const [page, setPage] = useState(1)

  const pageSize = 8

  function handleOpenEdit(vehicle) {
    setEditingVehicle(vehicle)
    const rateVal =
      vehicle.price != null
        ? Number(vehicle.price)
        : vehicle.dailyRate != null
          ? Number(vehicle.dailyRate)
          : 0
    const minDaysVal =
      vehicle.minimumDays != null ? Math.max(1, Number(vehicle.minimumDays)) : 1

    setEditFormData({
      makeModel: vehicle.name || vehicle.makeModel || '',
      registration: vehicle.registration || vehicle.registrationNumber || '',
      type: vehicle.type || 'Motorcycle',
      fuel: vehicle.fuel || 'Petrol',
      year: vehicle.year ? String(vehicle.year) : '2024',
      transmission: vehicle.transmission || 'Manual',
      color: vehicle.color || '',
      engineCapacity:
        vehicle.engineCapacity != null ? String(vehicle.engineCapacity) : '',
      seats: vehicle.seats != null ? String(vehicle.seats) : '2',
      dailyRate: rateVal > 0 ? String(rateVal) : '',
      minimumDays: String(minDaysVal),
      minRentalPackageAmount:
        rateVal > 0 ? String(Math.round(rateVal * minDaysVal)) : '',
      securityDeposit:
        vehicle.securityDeposit != null
          ? String(vehicle.securityDeposit)
          : '0',
      fleetAvailability:
        vehicle.availability || vehicle.fleetAvailability || 'Available',
      showOnWavygo: Boolean(isListedOnWavyGo(vehicle)),
      pickupAddress:
        vehicle.location ||
        vehicle.pickupAddress ||
        vehicle.pickupLocation?.address ||
        '',
      pickupNotes: vehicle.pickupNotes || '',
    })
    setEditError('')
  }

  function handleEditFieldChange(field, value) {
    setEditFormData((prev) => {
      const next = { ...prev, [field]: value }
      if (field === 'minimumDays') {
        const days = Math.max(1, parseInt(value, 10) || 1)
        const rate = parseFloat(prev.dailyRate) || 0
        if (rate > 0) {
          next.minRentalPackageAmount = String(Math.round(rate * days))
        }
      } else if (field === 'minRentalPackageAmount') {
        const pkgAmt = parseFloat(value) || 0
        const days = Math.max(1, parseInt(prev.minimumDays, 10) || 1)
        if (pkgAmt > 0) {
          next.dailyRate = String(Math.round(pkgAmt / days))
        }
      } else if (field === 'dailyRate') {
        const rate = parseFloat(value) || 0
        const days = Math.max(1, parseInt(prev.minimumDays, 10) || 1)
        if (rate > 0) {
          next.minRentalPackageAmount = String(Math.round(rate * days))
        }
      }
      return next
    })
    if (editError) setEditError('')
  }

  async function handleSaveEdit(e) {
    if (e) e.preventDefault()
    if (!editingVehicle) return

    if (!editFormData.makeModel?.trim()) {
      setEditError('Vehicle name / model is required.')
      return
    }
    if (!editFormData.registration?.trim()) {
      setEditError('Registration number is required.')
      return
    }
    const rateNum = Number(editFormData.dailyRate)
    if (!editFormData.dailyRate || Number.isNaN(rateNum) || rateNum <= 0) {
      setEditError('Daily rate must be greater than ₹0.')
      return
    }

    setIsSavingEdit(true)
    setEditError('')

    try {
      const updates = {
        makeModel: editFormData.makeModel.trim(),
        registration: editFormData.registration.trim().toUpperCase(),
        type: editFormData.type,
        fuel: editFormData.fuel,
        transmission: editFormData.transmission,
        fleetAvailability: editFormData.fleetAvailability,
        showOnWavygo: Boolean(editFormData.showOnWavygo),
      }

      if (editFormData.year) updates.year = parseInt(editFormData.year, 10)
      if (editFormData.color?.trim()) updates.color = editFormData.color.trim()
      if (editFormData.engineCapacity)
        updates.engineCapacity = parseInt(editFormData.engineCapacity, 10)
      if (editFormData.seats) updates.seats = parseInt(editFormData.seats, 10)
      if (editFormData.dailyRate)
        updates.dailyRate = parseFloat(editFormData.dailyRate)
      if (editFormData.minimumDays)
        updates.minimumDays = parseInt(editFormData.minimumDays, 10)
      if (editFormData.securityDeposit !== '')
        updates.securityDeposit = parseFloat(editFormData.securityDeposit || 0)
      if (editFormData.pickupAddress?.trim())
        updates.pickupAddress = editFormData.pickupAddress.trim()
      if (editFormData.pickupNotes?.trim())
        updates.pickupNotes = editFormData.pickupNotes.trim()

      await vehicleService.updateVehicle(editingVehicle.id, updates)

      updateRecord('vehicles', editingVehicle.id, {
        name: updates.makeModel,
        makeModel: updates.makeModel,
        registration: updates.registration,
        type: updates.type,
        fuel: updates.fuel,
        transmission: updates.transmission,
        year: updates.year,
        color: updates.color,
        engineCapacity: updates.engineCapacity,
        seats: updates.seats,
        dailyRate: updates.dailyRate,
        price: updates.dailyRate,
        minimumDays: updates.minimumDays,
        securityDeposit: updates.securityDeposit,
        availability: updates.fleetAvailability,
        fleetAvailability: updates.fleetAvailability,
        showOnWavygo: updates.showOnWavygo,
        status: updates.showOnWavygo ? 'Online' : 'Offline',
        location: updates.pickupAddress || editingVehicle.location,
        pickupAddress: updates.pickupAddress || editingVehicle.pickupAddress,
        pickupNotes: updates.pickupNotes,
      })

      if (typeof syncVehicles === 'function') {
        await syncVehicles({ force: true })
      }

      setNotice(`Vehicle "${updates.makeModel}" updated successfully.`)
      setEditingVehicle(null)
      if (selectedVehicle?.id === editingVehicle.id) {
        setSelectedVehicle((prev) => ({
          ...prev,
          ...updates,
          name: updates.makeModel,
          price: updates.dailyRate,
          availability: updates.fleetAvailability,
          location: updates.pickupAddress || prev.location,
        }))
      }
    } catch (err) {
      console.error('Error updating vehicle:', err)
      setEditError(err?.message || 'Failed to update vehicle.')
    } finally {
      setIsSavingEdit(false)
    }
  }

  async function handleDeleteVehicle() {
    if (!vehicleToDelete) return
    setIsDeleting(true)
    try {
      await vehicleService.deleteVehicle(vehicleToDelete.id)
      deleteRecord('vehicles', vehicleToDelete.id)
      if (typeof syncVehicles === 'function') {
        await syncVehicles({ force: true })
      }
      setNotice(`Vehicle "${vehicleToDelete.name}" deleted successfully.`)
      setVehicleToDelete(null)
      if (selectedVehicle?.id === vehicleToDelete.id) {
        setSelectedVehicle(null)
      }
    } catch (err) {
      console.error('Error deleting vehicle:', err)
      setNotice(err?.message || 'Failed to delete vehicle.')
    } finally {
      setIsDeleting(false)
    }
  }

  const filteredVehicles = useMemo(() => {
    const query = search.trim().toLowerCase()

    return vehicles.filter((vehicle) => {
      const isListed = isListedOnWavyGo(vehicle)

      const matchesTab =
        activeTab === 'All vehicles' ||
        (activeTab === 'Online' ? isListed : !isListed)

      const matchesType =
        typeFilter === 'All types' || vehicle.type === typeFilter

      const matchesAvailability =
        availabilityFilter === 'All availability' ||
        vehicle.availability === availabilityFilter

      const matchesSearch =
        !query ||
        [
          vehicle.name,
          vehicle.registration,
          vehicle.id,
          vehicle.type,
          vehicle.availability,
        ].some((field) =>
          String(field || '').toLowerCase().includes(query)
        )

      return (
        matchesTab &&
        matchesType &&
        matchesAvailability &&
        matchesSearch
      )
    })
  }, [vehicles, activeTab, search, typeFilter, availabilityFilter])

  const pageCount = Math.max(
    1,
    Math.ceil(filteredVehicles.length / pageSize)
  )

  const visibleVehicles = filteredVehicles.slice(
    (page - 1) * pageSize,
    page * pageSize
  )

  const counts = {
    all: vehicles.length,
    online: vehicles.filter(isListedOnWavyGo).length,
    offline: vehicles.filter((vehicle) => !isListedOnWavyGo(vehicle)).length,
  }

  async function toggleStatus(id) {
    const vehicle = vehicles.find((item) => item.id === id)
    if (!vehicle) return

    const listed = isListedOnWavyGo(vehicle)
    const nextStatus = !listed

    updateRecord('vehicles', id, {
      show_on_wavygo: nextStatus,
      showOnWavygo: nextStatus,
      status: nextStatus ? 'Online' : 'Offline',
    })

    try {
      await vehicleService.toggleShowOnWavygo(id, nextStatus)
      if (typeof syncVehicles === 'function') {
        syncVehicles({ force: true })
      }
      setNotice(
        `Vehicle "${vehicle.name}" listing on WavyGo set to ${nextStatus ? 'Online' : 'Offline'}.`
      )
    } catch (err) {
      console.warn('toggleShowOnWavygo error:', err)
      setNotice(
        `Listing updated locally to ${nextStatus ? 'Online' : 'Offline'}.`
      )
    }
  }

  async function handleAvailabilityChange(vehicleId, availability) {
    const result = updateRecord('vehicles', vehicleId, {
      availability,
      fleetAvailability: availability,
    })

    if (!result?.success) {
      setNotice(result?.error || 'Unable to update vehicle availability.')
      return
    }

    try {
      await vehicleService.updateVehicle(vehicleId, {
        fleetAvailability: availability,
      })
      if (typeof syncVehicles === 'function') {
        syncVehicles({ force: true })
      }
      setNotice(`Vehicle availability updated to ${availability}.`)
    } catch (err) {
      console.warn('updateVehicle availability error:', err)
      setNotice(`Vehicle availability updated locally to ${availability}.`)
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
            <span className="size-1.5 rounded-full bg-emerald-500" />
            Fleet management
          </div>

          <h1 className="text-3xl font-semibold tracking-tight text-slate-900">
            Vehicles
          </h1>

          <p className="mt-1.5 max-w-xl text-sm leading-6 text-slate-500">
            Manage your fleet, availability and daily pricing from one place.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() =>
              navigate('/app/bookings/new', { state: { offline: true } })
            }
            className="inline-flex h-11 items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 shadow-sm transition hover:border-emerald-200 hover:bg-emerald-50"
          >
            <CalendarDays size={16} className="text-emerald-700" />
            Offline booking
          </button>

          <button
            type="button"
            onClick={() => navigate('/app/vehicles/new')}
            className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-emerald-800 px-4 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-900"
          >
            <Plus size={17} />
            Add vehicle
          </button>
        </div>
      </div>

      <div className="overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-[0_4px_22px_rgba(15,23,42,0.035)]">
        <div className="flex flex-col gap-4 border-b border-slate-100 px-4 pt-4 sm:px-6 sm:pt-5">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-base font-semibold text-slate-900">
                Your fleet{' '}
                <span className="ml-1 text-sm font-medium text-slate-400">
                  {vehicles.length}
                </span>
              </h2>

              <p className="mt-1 text-xs text-slate-500">
                Manage your fleet availability, pricing and vehicle details
              </p>
            </div>

            <button
              type="button"
              onClick={resetFilters}
              className="inline-flex items-center gap-2 rounded-lg px-2 py-1.5 text-xs font-semibold text-slate-500 hover:bg-slate-50 hover:text-slate-800"
            >
              <SlidersHorizontal size={14} />
              Reset filters
            </button>
          </div>

          <div className="flex gap-5 overflow-x-auto">
            {tabs.map(({ label, count }) => (
              <button
                type="button"
                key={label}
                onClick={() => {
                  setActiveTab(label)
                  setPage(1)
                }}
                className={`relative flex shrink-0 items-center gap-2 pb-3 text-sm font-semibold transition ${
                  activeTab === label
                    ? 'text-emerald-800'
                    : 'text-slate-500 hover:text-slate-800'
                }`}
              >
                {label}

                <span
                  className={`rounded-full px-2 py-0.5 text-[11px] ${
                    activeTab === label
                      ? 'bg-emerald-50 text-emerald-800'
                      : 'bg-slate-100 text-slate-500'
                  }`}
                >
                  {count}
                </span>

                {activeTab === label && (
                  <span className="absolute inset-x-0 bottom-0 h-0.5 rounded-full bg-emerald-700" />
                )}
              </button>
            ))}
          </div>
        </div>

        <div className="grid gap-3 border-b border-slate-100 p-4 sm:grid-cols-[minmax(220px,1fr)_180px_180px] sm:px-6">
          <label className="relative block">
            <Search
              size={16}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
            />

            <input
              value={search}
              onChange={(event) => {
                setSearch(event.target.value)
                setPage(1)
              }}
              placeholder="Search name, plate or location…"
              className="h-10 w-full rounded-xl border border-slate-200 bg-slate-50/50 pl-9 pr-3 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-emerald-400 focus:bg-white focus:ring-3 focus:ring-emerald-100"
            />
          </label>

          <label className="relative">
            <Filter
              size={14}
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
            />

            <select
              value={typeFilter}
              onChange={(event) => {
                setTypeFilter(event.target.value)
                setPage(1)
              }}
              className="h-10 w-full appearance-none rounded-xl border border-slate-200 bg-white pl-9 pr-8 text-sm text-slate-700 outline-none focus:border-emerald-400 focus:ring-3 focus:ring-emerald-100"
            >
              {['All types', 'Motorcycle', 'Scooter', 'Electric'].map(
                (option) => (
                  <option key={option}>{option}</option>
                )
              )}
            </select>

            <ChevronDown
              size={14}
              className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400"
            />
          </label>

          <label className="relative">
            <select
              value={availabilityFilter}
              onChange={(event) => {
                setAvailabilityFilter(event.target.value)
                setPage(1)
              }}
              className="h-10 w-full appearance-none rounded-xl border border-slate-200 bg-white px-3 pr-8 text-sm text-slate-700 outline-none focus:border-emerald-400 focus:ring-3 focus:ring-emerald-100"
            >
              {['All availability', ...AVAILABILITY_OPTIONS].map(
                (option) => (
                  <option key={option}>{option}</option>
                )
              )}
            </select>

            <ChevronDown
              size={14}
              className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400"
            />
          </label>
        </div>

        {vehiclesError && vehicles.length > 0 && (
          <div role="alert" className="flex flex-wrap items-center justify-between gap-3 border-b border-amber-200 bg-amber-50 px-5 py-3 text-sm text-amber-900">
            <p>Could not refresh vehicles: {vehiclesError}. Showing the last loaded results.</p>
            <button type="button" onClick={() => syncVehicles({ force: true })} className="font-semibold underline">Retry</button>
          </div>
        )}

        {vehiclesLoading && vehicles.length === 0 ? (
          <div role="status" className="px-5 py-16 text-center text-sm text-slate-500">Loading vehicles…</div>
        ) : vehiclesError && vehicles.length === 0 ? (
          <div className="px-5 py-16 text-center sm:py-20">
            <h3 role="alert" className="text-base font-semibold text-rose-800">Could not load vehicles</h3>
            <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500">{vehiclesError}</p>
            <button type="button" onClick={() => syncVehicles({ force: true })} className="mt-4 text-sm font-semibold text-emerald-800 hover:text-emerald-950">Retry</button>
          </div>
        ) : filteredVehicles.length ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[850px] border-collapse text-left">
              <thead>
                <tr className="bg-slate-50/80 text-[11px] font-semibold uppercase tracking-[0.11em] text-slate-400">
                  <th className="px-6 py-3.5">
                    Vehicle <ArrowDownUp size={12} className="ml-1 inline" />
                  </th>
                  <th className="px-4 py-3.5">Vehicle type</th>
                  <th className="px-4 py-3.5">Fleet availability</th>
                  <th className="px-4 py-3.5">Daily rate</th>
                  <th className="px-4 py-3.5">Show on WavyGo</th>
                  <th className="px-5 py-3.5 text-right">Actions</th>
                </tr>
              </thead>

              <tbody className="divide-y divide-slate-100">
                {visibleVehicles.map((vehicle) => {
                  const isListed = isListedOnWavyGo(vehicle)

                  return (
                    <tr
                      key={vehicle.id}
                      className="group transition hover:bg-emerald-50/25"
                    >
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          <VehicleArt vehicle={vehicle} small />

                          <div className="min-w-0">
                            <p className="whitespace-nowrap text-sm font-semibold text-slate-900">
                              {vehicle.name || 'Name unavailable'}
                            </p>

                            <p className="mt-1 text-xs text-slate-500">
                              {vehicle.registration || 'Registration unavailable'}
                              <span className="mx-1 text-slate-300">·</span>
                              {vehicle.id || 'ID unavailable'}
                            </p>
                          </div>
                        </div>
                      </td>

                      <td className="px-4 py-4">
                        <p className="text-sm font-medium text-slate-700">
                          {vehicle.type}
                        </p>
                        <p className="mt-1 text-xs text-slate-400">
                          Two-wheeler
                        </p>
                      </td>

                      <td className="px-4 py-4">
                        <AvailabilityDropdown
                          vehicle={vehicle}
                          onSelect={handleAvailabilityChange}
                        />
                      </td>

                      <td className="px-4 py-4">
                        <p className="whitespace-nowrap text-sm font-semibold text-slate-800">
                          {vehicle.price != null ? (
                            <>
                              ₹{Number(vehicle.price).toLocaleString('en-IN')}
                              <span className="font-normal text-slate-400">
                                {' '}/ day
                              </span>
                            </>
                          ) : (
                            'Not provided'
                          )}
                        </p>
                      </td>

                      <td className="px-4 py-4">
                        <button
                          type="button"
                          role="switch"
                          aria-checked={Boolean(isListed)}
                          aria-label={`Show ${vehicle.name} on WavyGo`}
                          onClick={() => toggleStatus(vehicle.id)}
                          className={`relative inline-flex h-6 w-11 items-center rounded-full transition ${
                            isListed ? 'bg-emerald-700' : 'bg-slate-300'
                          }`}
                        >
                          <span
                            className={`inline-block size-4 transform rounded-full bg-white shadow transition ${
                              isListed ? 'translate-x-6' : 'translate-x-1'
                            }`}
                          />
                          <span className="sr-only">
                            {isListed ? 'On' : 'Off'}
                          </span>
                        </button>

                        <span
                          className={`ml-2 text-xs font-semibold ${
                            isListed ? 'text-emerald-800' : 'text-slate-500'
                          }`}
                        >
                          {isListed ? 'On' : 'Off'}
                        </span>
                      </td>

                      <td className="px-5 py-4">
                        <div className="flex justify-end gap-1">
                          <button
                            type="button"
                            onClick={() => setSelectedVehicle(vehicle)}
                            className="inline-flex h-8 items-center gap-1 rounded-lg px-2 text-xs font-semibold text-slate-600 hover:bg-slate-100"
                            aria-label={`View ${vehicle.name}`}
                          >
                            <Eye size={14} />
                            View
                          </button>

                          <button
                            type="button"
                            onClick={() => handleOpenEdit(vehicle)}
                            className="inline-flex h-8 items-center gap-1 rounded-lg px-2 text-xs font-semibold text-slate-600 hover:bg-slate-100"
                            aria-label={`Edit ${vehicle.name}`}
                          >
                            <Pencil size={14} />
                            Edit
                          </button>

                          <button
                            type="button"
                            onClick={() => setVehicleToDelete(vehicle)}
                            className="inline-flex h-8 items-center gap-1 rounded-lg px-2 text-xs font-semibold text-rose-600 hover:bg-rose-50"
                            aria-label={`Delete ${vehicle.name}`}
                          >
                            <Trash2 size={14} />
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : vehicles.length === 0 ? (
          <div className="px-5 py-16 text-center sm:py-20">
            <span className="mx-auto grid size-14 place-items-center rounded-2xl bg-emerald-50 text-emerald-800"><CarFront size={22} /></span>
            <h3 className="mt-4 text-base font-semibold text-slate-900">No vehicles in your fleet yet</h3>
            <p className="mx-auto mt-1.5 max-w-sm text-sm leading-6 text-slate-500">Add a vehicle to see it listed here.</p>
            <button type="button" onClick={() => navigate('/app/vehicles/new')} className="mt-4 text-sm font-semibold text-emerald-800 hover:text-emerald-950">Add vehicle</button>
          </div>
        ) : (
          <div className="px-5 py-16 text-center sm:py-20">
            <span className="mx-auto grid size-14 place-items-center rounded-2xl bg-emerald-50 text-emerald-800">
              <Search size={22} />
            </span>

            <h3 className="mt-4 text-base font-semibold text-slate-900">
              No vehicles match those filters
            </h3>

            <p className="mx-auto mt-1.5 max-w-sm text-sm leading-6 text-slate-500">
              Try another search or reset your filters to see your full fleet.
            </p>

            <button
              type="button"
              onClick={resetFilters}
              className="mt-4 text-sm font-semibold text-emerald-800 hover:text-emerald-950"
            >
              Clear filters
            </button>
          </div>
        )}

        <footer className="flex flex-col gap-3 border-t border-slate-100 px-4 py-3.5 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <p>
            Showing{' '}
            <span className="font-semibold text-slate-700">
              {visibleVehicles.length}
            </span>{' '}
            of{' '}
            <span className="font-semibold text-slate-700">
              {filteredVehicles.length}
            </span>{' '}
            matching vehicles · preview data
          </p>

          <div className="flex items-center gap-3">
            <button
              type="button"
              disabled={page <= 1}
              onClick={() => setPage((current) => current - 1)}
              className="rounded-lg border border-slate-200 px-2.5 py-1.5 font-semibold disabled:opacity-40"
            >
              Previous
            </button>

            <span>
              Page {page} of {pageCount}
            </span>

            <button
              type="button"
              disabled={page >= pageCount}
              onClick={() => setPage((current) => current + 1)}
              className="rounded-lg border border-slate-200 px-2.5 py-1.5 font-semibold disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </footer>
      </div>

      <div
        className={`flex items-center gap-3 rounded-xl border px-4 py-3 text-xs leading-5 ${
          notice
            ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
            : 'border-slate-200/70 bg-white/70 text-slate-500'
        }`}
      >
        <CircleHelp size={16} className="shrink-0 text-emerald-700" />
        <p>
          {notice ||
            'Fleet management: vehicles and availability are live synchronized with your WavyGo fleet.'}
        </p>
      </div>

      {selectedVehicle && (
        <div
          className="fixed inset-0 z-40 flex items-center justify-center bg-slate-950/35 p-4 backdrop-blur-[2px]"
          onClick={() => setSelectedVehicle(null)}
        >
          <article
            role="dialog"
            aria-modal="true"
            aria-labelledby="vehicle-detail-title"
            onClick={(event) => event.stopPropagation()}
            className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white p-5 shadow-2xl sm:p-6"
          >
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <VehicleArt vehicle={selectedVehicle} />

                <div>
                  <h2
                    id="vehicle-detail-title"
                    className="font-semibold text-slate-900"
                  >
                    {selectedVehicle.name}
                  </h2>

                  <p className="mt-1 text-xs text-slate-500">
                    {selectedVehicle.type || 'Type unavailable'}
                  </p>
                </div>
              </div>

              <button
                type="button"
                onClick={() => setSelectedVehicle(null)}
                aria-label="Close details"
                className="grid size-8 place-items-center rounded-lg text-slate-400 hover:bg-slate-100"
              >
                <X size={17} />
              </button>
            </div>

            <div className="mt-5 grid grid-cols-2 gap-3 text-sm">
              {[
                ['Registration / RC', selectedVehicle.registration],
                ['Fleet ID', selectedVehicle.id],
                ['Make / model', selectedVehicle.name],
                ['Model year', selectedVehicle.year],
                ['Type', selectedVehicle.type],
                ['Fuel', selectedVehicle.fuel],
                ['Color', selectedVehicle.color],
                [
                  'Engine capacity',
                  selectedVehicle.engineCapacity
                    ? `${selectedVehicle.engineCapacity} cc`
                    : 'Not provided',
                ],
                ['Seats', selectedVehicle.seats],
                [
                  'Show on WavyGo',
                  isListedOnWavyGo(selectedVehicle) ? 'On' : 'Off',
                ],
                [
                  'Fleet availability',
                  selectedVehicle.availability || 'Not provided',
                ],
                [
                  'Daily rate',
                  selectedVehicle.price
                    ? `₹${Number(selectedVehicle.price).toLocaleString('en-IN')} / day`
                    : 'Not provided',
                ],
                [
                  'Pickup location',
                  selectedVehicle.location || selectedVehicle.pickupLocation,
                ],
                [
                  'Minimum rental',
                  selectedVehicle.minimumDays
                    ? `${selectedVehicle.minimumDays} days`
                    : 'Not provided',
                ],
              ].map(([label, value]) => (
                <div key={label} className="rounded-xl bg-slate-50 p-3">
                  <p className="text-[11px] font-medium text-slate-400">
                    {label}
                  </p>
                  <p className="mt-1 font-semibold text-slate-800">
                    {value || 'Not provided'}
                  </p>
                </div>
              ))}
            </div>

            <section className="mt-5">
              <h3 className="text-sm font-semibold text-slate-900">
                Documents
              </h3>

              {Array.isArray(selectedVehicle.documents) &&
              selectedVehicle.documents.length ? (
                <ul className="mt-2 space-y-2">
                  {selectedVehicle.documents.map((doc, index) => {
                    const url = typeof doc === 'string' ? doc : doc.url

                    return (
                      <li
                        key={doc.id || doc.name || index}
                        className="flex items-center justify-between rounded-xl border border-slate-100 p-3 text-sm"
                      >
                        <span>
                          {doc.name || doc.type || 'Vehicle document'}
                        </span>

                        {url ? (
                          <a
                            href={url}
                            target="_blank"
                            rel="noreferrer"
                            className="font-semibold text-emerald-800 hover:underline"
                          >
                            Open
                          </a>
                        ) : (
                          <span className="text-xs text-slate-400">
                            File unavailable
                          </span>
                        )}
                      </li>
                    )
                  })}
                </ul>
              ) : (
                <p className="mt-2 rounded-xl bg-slate-50 p-3 text-sm text-slate-500">
                  No vehicle documents are available.
                </p>
              )}
            </section>

            <div className="mt-5 flex flex-wrap items-center justify-end gap-2.5">
              <button
                type="button"
                onClick={() => {
                  const target = selectedVehicle
                  setSelectedVehicle(null)
                  setVehicleToDelete(target)
                }}
                className="inline-flex h-10 items-center gap-1.5 rounded-xl border border-rose-200 px-3.5 text-xs font-semibold text-rose-600 hover:bg-rose-50"
              >
                <Trash2 size={14} />
                Delete
              </button>

              <button
                type="button"
                onClick={() => {
                  const target = selectedVehicle
                  setSelectedVehicle(null)
                  handleOpenEdit(target)
                }}
                className="inline-flex h-10 items-center gap-1.5 rounded-xl border border-slate-200 px-3.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
              >
                <Pencil size={14} />
                Edit Vehicle
              </button>

              <button
                type="button"
                onClick={() => setSelectedVehicle(null)}
                className="h-10 rounded-xl bg-emerald-800 px-5 text-sm font-semibold text-white hover:bg-emerald-900"
              >
                Close
              </button>
            </div>
          </article>
        </div>
      )}

      {editingVehicle && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 p-4 backdrop-blur-[2px]"
          onClick={() => !isSavingEdit && setEditingVehicle(null)}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="edit-vehicle-title"
            onClick={(e) => e.stopPropagation()}
            className="flex max-h-[92vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl"
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
              <div className="flex items-center gap-3">
                <div className="grid size-10 place-items-center rounded-xl bg-emerald-50 text-emerald-800">
                  <Pencil size={18} />
                </div>
                <div>
                  <h2
                    id="edit-vehicle-title"
                    className="text-base font-semibold text-slate-900"
                  >
                    Edit Vehicle
                  </h2>
                  <p className="text-xs text-slate-500">
                    {editingVehicle.name} •{' '}
                    {editingVehicle.registration || 'No Reg'}
                  </p>
                </div>
              </div>
              <button
                type="button"
                disabled={isSavingEdit}
                onClick={() => setEditingVehicle(null)}
                className="grid size-8 place-items-center rounded-lg text-slate-400 hover:bg-slate-100 disabled:opacity-40"
              >
                <X size={17} />
              </button>
            </div>

            {/* Error Message */}
            {editError && (
              <div className="mx-6 mt-4 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-xs font-medium text-rose-700">
                {editError}
              </div>
            )}

            {/* Body */}
            <form
              onSubmit={handleSaveEdit}
              className="flex-1 space-y-5 overflow-y-auto px-6 py-4"
            >
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                  Basic Details
                </h3>
                <div className="mt-2.5 grid grid-cols-1 gap-3.5 sm:grid-cols-2">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700">
                      Make & Model <span className="text-rose-500">*</span>
                    </label>
                    <input
                      type="text"
                      required
                      value={editFormData.makeModel || ''}
                      onChange={(e) =>
                        handleEditFieldChange('makeModel', e.target.value)
                      }
                      placeholder="e.g. Royal Enfield Classic 350"
                      className="mt-1 h-10 w-full rounded-xl border border-slate-200 px-3 text-sm text-slate-800 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700">
                      Registration Number <span className="text-rose-500">*</span>
                    </label>
                    <input
                      type="text"
                      required
                      value={editFormData.registration || ''}
                      onChange={(e) =>
                        handleEditFieldChange(
                          'registration',
                          e.target.value.toUpperCase()
                        )
                      }
                      placeholder="e.g. DL 01 AB 1234"
                      className="mt-1 h-10 w-full rounded-xl border border-slate-200 px-3 font-mono text-sm uppercase text-slate-800 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700">
                      Vehicle Type
                    </label>
                    <select
                      value={editFormData.type || 'Motorcycle'}
                      onChange={(e) =>
                        handleEditFieldChange('type', e.target.value)
                      }
                      className="mt-1 h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
                    >
                      <option value="Motorcycle">Motorcycle</option>
                      <option value="Scooter">Scooter</option>
                      <option value="Electric">Electric</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700">
                      Fuel Type
                    </label>
                    <select
                      value={editFormData.fuel || 'Petrol'}
                      onChange={(e) =>
                        handleEditFieldChange('fuel', e.target.value)
                      }
                      className="mt-1 h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
                    >
                      <option value="Petrol">Petrol</option>
                      <option value="Diesel">Diesel</option>
                      <option value="Electric">Electric</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700">
                      Transmission
                    </label>
                    <select
                      value={editFormData.transmission || 'Manual'}
                      onChange={(e) =>
                        handleEditFieldChange('transmission', e.target.value)
                      }
                      className="mt-1 h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
                    >
                      <option value="Manual">Manual</option>
                      <option value="Automatic">Automatic</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700">
                      Model Year
                    </label>
                    <input
                      type="number"
                      min="2000"
                      max="2030"
                      value={editFormData.year || ''}
                      onChange={(e) =>
                        handleEditFieldChange('year', e.target.value)
                      }
                      placeholder="2024"
                      className="mt-1 h-10 w-full rounded-xl border border-slate-200 px-3 text-sm text-slate-800 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700">
                      Color
                    </label>
                    <input
                      type="text"
                      value={editFormData.color || ''}
                      onChange={(e) =>
                        handleEditFieldChange('color', e.target.value)
                      }
                      placeholder="e.g. Matte Black"
                      className="mt-1 h-10 w-full rounded-xl border border-slate-200 px-3 text-sm text-slate-800 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700">
                      Engine Capacity (cc)
                    </label>
                    <input
                      type="number"
                      min="0"
                      max="10000"
                      value={editFormData.engineCapacity || ''}
                      onChange={(e) =>
                        handleEditFieldChange('engineCapacity', e.target.value)
                      }
                      placeholder="e.g. 350"
                      className="mt-1 h-10 w-full rounded-xl border border-slate-200 px-3 text-sm text-slate-800 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
                    />
                  </div>
                </div>
              </div>

              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                  Pricing & Rental Policy
                </h3>
                <div className="mt-2.5 grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700">
                      Min Rental Days <span className="text-rose-500">*</span>
                    </label>
                    <input
                      type="number"
                      min="1"
                      max="365"
                      value={editFormData.minimumDays || ''}
                      onChange={(e) =>
                        handleEditFieldChange('minimumDays', e.target.value)
                      }
                      placeholder="1"
                      className="mt-1 h-10 w-full rounded-xl border border-slate-200 px-3 text-sm text-slate-800 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700">
                      Min Package Amount (₹)
                    </label>
                    <input
                      type="number"
                      min="1"
                      step="any"
                      value={editFormData.minRentalPackageAmount || ''}
                      onChange={(e) =>
                        handleEditFieldChange('minRentalPackageAmount', e.target.value)
                      }
                      placeholder="1500"
                      className="mt-1 h-10 w-full rounded-xl border border-slate-200 px-3 text-sm text-slate-800 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700">
                      Daily Rate (₹) <span className="text-rose-500">*</span>
                    </label>
                    <input
                      type="number"
                      min="1"
                      step="any"
                      required
                      value={editFormData.dailyRate || ''}
                      onChange={(e) =>
                        handleEditFieldChange('dailyRate', e.target.value)
                      }
                      placeholder="500"
                      className="mt-1 h-10 w-full rounded-xl border border-slate-200 px-3 text-sm text-slate-800 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700">
                      Security Deposit (₹)
                    </label>
                    <input
                      type="number"
                      min="0"
                      step="any"
                      value={editFormData.securityDeposit || ''}
                      onChange={(e) =>
                        handleEditFieldChange('securityDeposit', e.target.value)
                      }
                      placeholder="0"
                      className="mt-1 h-10 w-full rounded-xl border border-slate-200 px-3 text-sm text-slate-800 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
                    />
                  </div>
                </div>

                <div className="mt-3 rounded-xl border border-emerald-100 bg-emerald-50/70 p-3 text-xs text-emerald-900">
                  <div className="flex items-center justify-between font-semibold">
                    <span>Active Rental Calculation:</span>
                    <span className="font-mono text-emerald-800">
                      ₹{Number(editFormData.dailyRate || 0).toLocaleString('en-IN')} / day × {Number(editFormData.minimumDays || 1)} days = ₹{(Number(editFormData.dailyRate || 0) * Number(editFormData.minimumDays || 1)).toLocaleString('en-IN')} min booking total
                    </span>
                  </div>
                </div>
              </div>

              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                  Status & Location
                </h3>
                <div className="mt-2.5 grid grid-cols-1 gap-3.5 sm:grid-cols-2">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700">
                      Fleet Availability
                    </label>
                    <select
                      value={editFormData.fleetAvailability || 'Available'}
                      onChange={(e) =>
                        handleEditFieldChange(
                          'fleetAvailability',
                          e.target.value
                        )
                      }
                      className="mt-1 h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
                    >
                      <option value="Available">Available</option>
                      <option value="Rented">Rented</option>
                      <option value="Under Review">Under Review</option>
                      <option value="Maintenance">Maintenance</option>
                    </select>
                  </div>

                  <div className="flex items-center pt-5">
                    <label className="relative inline-flex cursor-pointer items-center gap-3">
                      <input
                        type="checkbox"
                        checked={Boolean(editFormData.showOnWavygo)}
                        onChange={(e) =>
                          handleEditFieldChange(
                            'showOnWavygo',
                            e.target.checked
                          )
                        }
                        className="peer sr-only"
                      />
                      <div className="h-6 w-11 rounded-full bg-slate-300 transition-colors after:absolute after:start-[2px] after:top-[2px] after:h-5 after:w-5 after:rounded-full after:bg-white after:shadow after:transition-all after:content-[''] peer-checked:bg-emerald-700 peer-checked:after:translate-x-full peer-focus:outline-none"></div>
                      <span className="text-xs font-semibold text-slate-700">
                        Show on WavyGo marketplace
                      </span>
                    </label>
                  </div>

                  <div className="sm:col-span-2">
                    <label className="block text-xs font-semibold text-slate-700">
                      Pickup Address / Location
                    </label>
                    <input
                      type="text"
                      value={editFormData.pickupAddress || ''}
                      onChange={(e) =>
                        handleEditFieldChange('pickupAddress', e.target.value)
                      }
                      placeholder="e.g. Connaught Place Hub, New Delhi"
                      className="mt-1 h-10 w-full rounded-xl border border-slate-200 px-3 text-sm text-slate-800 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
                    />
                  </div>

                  <div className="sm:col-span-2">
                    <label className="block text-xs font-semibold text-slate-700">
                      Pickup Notes
                    </label>
                    <input
                      type="text"
                      value={editFormData.pickupNotes || ''}
                      onChange={(e) =>
                        handleEditFieldChange('pickupNotes', e.target.value)
                      }
                      placeholder="e.g. Near metro gate 4, ask for Vikram"
                      className="mt-1 h-10 w-full rounded-xl border border-slate-200 px-3 text-sm text-slate-800 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
                    />
                  </div>
                </div>
              </div>

              {/* Footer */}
              <div className="flex items-center justify-end gap-3 border-t border-slate-100 pt-4">
                <button
                  type="button"
                  disabled={isSavingEdit}
                  onClick={() => setEditingVehicle(null)}
                  className="rounded-xl border border-slate-200 px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-40"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSavingEdit}
                  className="inline-flex items-center gap-2 rounded-xl bg-emerald-800 px-5 py-2 text-xs font-semibold text-white hover:bg-emerald-900 disabled:opacity-60"
                >
                  {isSavingEdit && (
                    <Loader2 size={14} className="animate-spin" />
                  )}
                  {isSavingEdit ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {vehicleToDelete && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 p-4 backdrop-blur-[2px]"
          onClick={() => !isDeleting && setVehicleToDelete(null)}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-vehicle-title"
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl"
          >
            <div className="flex items-center gap-3 text-rose-600">
              <div className="grid size-11 place-items-center rounded-2xl bg-rose-50">
                <Trash2 size={22} />
              </div>
              <div>
                <h3
                  id="delete-vehicle-title"
                  className="font-semibold text-slate-900"
                >
                  Delete Vehicle
                </h3>
                <p className="text-xs text-slate-500">
                  This action is permanent and cannot be undone.
                </p>
              </div>
            </div>

            <p className="mt-4 text-sm leading-6 text-slate-600">
              Are you sure you want to delete{' '}
              <span className="font-semibold text-slate-800">
                {vehicleToDelete.name}
              </span>{' '}
              ({vehicleToDelete.registration || 'No Reg'})?
            </p>

            <div className="mt-6 flex items-center justify-end gap-3">
              <button
                type="button"
                disabled={isDeleting}
                onClick={() => setVehicleToDelete(null)}
                className="rounded-xl border border-slate-200 px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-40"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={isDeleting}
                onClick={handleDeleteVehicle}
                className="inline-flex items-center gap-2 rounded-xl bg-rose-600 px-5 py-2 text-xs font-semibold text-white hover:bg-rose-700 disabled:opacity-60"
              >
                {isDeleting && <Loader2 size={14} className="animate-spin" />}
                {isDeleting ? 'Deleting...' : 'Delete Vehicle'}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}

export default Vehicles