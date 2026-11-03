import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useCreateVehicle } from '../../hooks/useVehicles.js'
import { validateRcFormat } from '../../utils/rc.js'
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  BadgeCheck,
  CalendarDays,
  Check,
  CircleHelp,
  FileCheck2,
  ImagePlus,
  IndianRupee,
  Lock,
  Upload,
  X,
} from 'lucide-react'

const steps = ['Basic details', 'Pricing & availability', 'Documents & photos', 'Review']

const MAX_PHOTO_BYTES = 10 * 1024 * 1024 // 10 MB
const ALLOWED_PHOTO_TYPES = ['image/jpeg', 'image/png', 'image/webp']

export const initialData = {
  makeModel: '',
  trim: '',
  registration: '',
  year: '2024',
  type: '',
  fuel: '',
  color: '',
  engineCapacity: '',
  rcStatus: 'Pending review',
  seats: '1',
  transmission: '',
  rate: '',
  location: '',
  minimumDays: '1',
  pickupNotes: '',
}

export function validateAddVehicleForm(step, data, photo) {
  const nextErrors = {}
  const currentYear = new Date().getFullYear()
  const maxYear = currentYear + 1

  if (step === 0) {
    if (!data.makeModel?.trim()) nextErrors.makeModel = 'Enter the vehicle make and model.'
    if (!data.registration?.trim()) {
      nextErrors.registration = 'Enter the registration number.'
    } else if (!validateRcFormat(data.registration)) {
      nextErrors.registration = 'Enter a valid registration number (e.g. GJ05AB4821).'
    }
    const yearNum = Number(data.year)
    if (!data.year || isNaN(yearNum) || yearNum < 2000 || yearNum > maxYear) {
      nextErrors.year = `Enter a valid model year between 2000 and ${maxYear}.`
    }
    if (!data.type) nextErrors.type = 'Choose a vehicle type.'
    if (!data.fuel) nextErrors.fuel = 'Choose a fuel type.'
    if (!data.transmission) nextErrors.transmission = 'Choose a transmission.'
  }

  if (step === 1) {
    const rateNum = Number(data.rate)
    if (!data.rate || isNaN(rateNum) || rateNum < 1) {
      nextErrors.rate = 'Enter a daily rate greater than ₹0.'
    }
    if (!data.location?.trim()) nextErrors.location = 'Add a pickup location.'
    const minDaysNum = Number(data.minimumDays)
    if (!data.minimumDays || isNaN(minDaysNum) || minDaysNum < 1) {
      nextErrors.minimumDays = 'Minimum rental must be at least one day.'
    }
  }

  if (step === 2) {
    if (photo?.file) {
      if (!ALLOWED_PHOTO_TYPES.includes(photo.file.type)) {
        nextErrors.photo = 'Vehicle photo must be a JPEG, PNG, or WebP image.'
      } else if (photo.file.size > MAX_PHOTO_BYTES) {
        nextErrors.photo = 'Vehicle photo exceeds the 10 MB limit.'
      }
    }
  }

  return nextErrors
}

export function buildVehicleFormData(data, photo) {
  const formData = new FormData()

  formData.append('makeModel', data.makeModel.trim())
  formData.append('registration', data.registration.trim())
  formData.append('registrationNumber', data.registration.trim().replace(/\s+/g, '').toUpperCase())
  formData.append('year', String(parseInt(data.year, 10)))
  formData.append('type', data.type)
  formData.append('fuel', data.fuel)
  formData.append('transmission', data.transmission)
  if (data.color?.trim()) formData.append('color', data.color.trim())
  if (data.engineCapacity && data.fuel !== 'Electric') {
    formData.append('engineCapacity', String(parseInt(data.engineCapacity, 10)))
  }
  formData.append('seats', String(parseInt(data.seats || '1', 10)))
  formData.append('rcStatus', data.rcStatus || 'Pending review')
  if (data.trim?.trim()) formData.append('trim', data.trim.trim())

  formData.append('dailyRate', String(parseFloat(data.rate)))
  formData.append('minimumDays', String(parseInt(data.minimumDays || '1', 10)))
  formData.append('securityDeposit', '0')
  formData.append('pickupAddress', data.location.trim())
  if (data.pickupNotes?.trim()) formData.append('pickupNotes', data.pickupNotes.trim())
  formData.append('showOnWavygo', 'false')
  formData.append('fleetAvailability', 'Available')

  if (photo?.file) {
    formData.append('photos', photo.file)
  }

  // Phase 1 note: documents & documentTypes are omitted per security guidelines
  return formData
}

function AddVehicle() {
  const navigate = useNavigate()
  const createMutation = useCreateVehicle()

  const [step, setStep] = useState(0)
  const [data, setData] = useState(initialData)
  const [errors, setErrors] = useState({})
  const [photo, setPhoto] = useState(null)
  const [submitError, setSubmitError] = useState('')

  function update(field, value) {
    setData((current) => ({ ...current, [field]: value }))
    setErrors((current) => ({ ...current, [field]: '' }))
  }

  function validateCurrentStep() {
    const nextErrors = validateAddVehicleForm(step, data, photo)
    setErrors(nextErrors)
    return Object.keys(nextErrors).length === 0
  }

  function handlePhotoChange(event) {
    const file = event.target.files?.[0]
    if (!file) return

    if (photo?.preview) URL.revokeObjectURL(photo.preview)

    if (!ALLOWED_PHOTO_TYPES.includes(file.type)) {
      setErrors((prev) => ({ ...prev, photo: 'Vehicle photo must be a JPEG, PNG, or WebP image.' }))
      event.target.value = ''
      return
    }
    if (file.size > MAX_PHOTO_BYTES) {
      setErrors((prev) => ({ ...prev, photo: 'Vehicle photo exceeds the 10 MB limit.' }))
      event.target.value = ''
      return
    }

    setErrors((prev) => ({ ...prev, photo: '' }))
    setPhoto({
      name: file.name,
      preview: URL.createObjectURL(file),
      file,
    })
    event.target.value = ''
  }

  async function handleSubmit() {
    setSubmitError('')
    // Validate all steps
    const step0Errors = validateAddVehicleForm(0, data, photo)
    const step1Errors = validateAddVehicleForm(1, data, photo)
    const step2Errors = validateAddVehicleForm(2, data, photo)
    const allErrors = { ...step0Errors, ...step1Errors, ...step2Errors }

    if (Object.keys(allErrors).length > 0) {
      setErrors(allErrors)
      if (Object.keys(step0Errors).length > 0) setStep(0)
      else if (Object.keys(step1Errors).length > 0) setStep(1)
      else if (Object.keys(step2Errors).length > 0) setStep(2)
      return
    }

    const formData = buildVehicleFormData(data, photo)

    try {
      await createMutation.mutateAsync(formData)
      navigate('/app/vehicles')
    } catch (err) {
      // Map field-level 422 errors
      if (err?.status === 422 && Array.isArray(err.details) && err.details.length > 0) {
        const fieldMap = {
          makeModel: 'makeModel',
          registration: 'registration',
          registrationNumber: 'registration',
          dailyRate: 'rate',
          pickupAddress: 'location',
          minimumDays: 'minimumDays',
          year: 'year',
          type: 'type',
          fuel: 'fuel',
          transmission: 'transmission',
          engineCapacity: 'engineCapacity',
          color: 'color',
          seats: 'seats',
        }

        const backendErrors = {}
        const unmappedMessages = []

        err.details.forEach(({ field, message }) => {
          const formField = fieldMap[field]
          if (formField) {
            backendErrors[formField] = message
          } else {
            unmappedMessages.push(message)
          }
        })

        setErrors(backendErrors)
        setSubmitError(
          unmappedMessages.length > 0
            ? unmappedMessages.join(' ')
            : 'Please correct the highlighted errors before submitting.',
        )

        // If errors belong to earlier steps, navigate there
        if (['makeModel', 'registration', 'year', 'type', 'fuel', 'transmission', 'engineCapacity', 'color', 'seats'].some((k) => backendErrors[k])) {
          setStep(0)
        } else if (['rate', 'location', 'minimumDays'].some((k) => backendErrors[k])) {
          setStep(1)
        }
      } else {
        setSubmitError(err?.message || 'Failed to create vehicle. Please try again.')
      }
    }
  }

  const Input = ({ label, name, placeholder, type = 'text', required = false, help, ...props }) => (
    <label className="block">
      <span className="mb-1.5 block text-sm font-semibold text-slate-700">
        {label}
        {required && <span className="ml-1 text-rose-500">*</span>}
      </span>
      <input
        type={type}
        value={data[name]}
        onChange={(event) => update(name, event.target.value)}
        placeholder={placeholder}
        {...props}
        className={`h-11 w-full rounded-xl border bg-white px-3.5 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-emerald-500 focus:ring-3 focus:ring-emerald-100 ${
          errors[name] ? 'border-rose-300' : 'border-slate-200'
        }`}
      />
      {errors[name] ? (
        <span className="mt-1 block text-xs text-rose-600">{errors[name]}</span>
      ) : help ? (
        <span className="mt-1 block text-xs text-slate-400">{help}</span>
      ) : null}
    </label>
  )

  const Select = ({ label, name, options, required = false }) => (
    <label className="block">
      <span className="mb-1.5 block text-sm font-semibold text-slate-700">
        {label}
        {required && <span className="ml-1 text-rose-500">*</span>}
      </span>
      <select
        value={data[name]}
        onChange={(event) => update(name, event.target.value)}
        className={`h-11 w-full rounded-xl border bg-white px-3.5 text-sm text-slate-700 outline-none transition focus:border-emerald-500 focus:ring-3 focus:ring-emerald-100 ${
          errors[name] ? 'border-rose-300' : 'border-slate-200'
        }`}
      >
        <option value="">Select {label.toLowerCase()}</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
      {errors[name] && <span className="mt-1 block text-xs text-rose-600">{errors[name]}</span>}
    </label>
  )

  return (
    <section className="mx-auto max-w-4xl space-y-5 pb-8 text-slate-800">
      <button
        type="button"
        onClick={() => navigate('/app/vehicles')}
        className="inline-flex items-center gap-2 text-sm font-medium text-slate-500 transition hover:text-emerald-800"
      >
        <ArrowLeft size={16} /> Back to vehicles
      </button>
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-emerald-700">Fleet setup</p>
          <h1 className="text-3xl font-semibold tracking-tight text-slate-900">Add a vehicle</h1>
          <p className="mt-1.5 text-sm text-slate-500">A few details and you’ll be ready to list it in your fleet.</p>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200/80 bg-white px-4 py-5 shadow-[0_4px_22px_rgba(15,23,42,0.035)] sm:px-7">
        <div className="mb-6 grid grid-cols-4 gap-2 sm:gap-4">
          {steps.map((label, index) => (
            <div key={label} className="min-w-0">
              <div className="flex items-center gap-2">
                {index < step ? (
                  <span className="grid size-7 shrink-0 place-items-center rounded-full bg-emerald-700 text-white">
                    <Check size={14} />
                  </span>
                ) : (
                  <span
                    className={`grid size-7 shrink-0 place-items-center rounded-full text-xs font-semibold ${
                      index === step ? 'bg-emerald-700 text-white' : 'bg-slate-100 text-slate-500'
                    }`}
                  >
                    {index + 1}
                  </span>
                )}
                <span className={`hidden truncate text-xs font-semibold sm:block ${index === step ? 'text-slate-900' : 'text-slate-400'}`}>
                  {label}
                </span>
              </div>
              <div className={`mt-2 h-1 rounded-full ${index <= step ? 'bg-emerald-600' : 'bg-slate-100'}`} />
              <span className={`mt-1.5 block truncate text-[10px] font-medium sm:hidden ${index === step ? 'text-slate-700' : 'text-slate-400'}`}>
                {label}
              </span>
            </div>
          ))}
        </div>

        {step === 0 && (
          <div className="animate-in space-y-5">
            <div className="mb-1">
              <h2 className="text-lg font-semibold text-slate-900">Basic details</h2>
              <p className="mt-1 text-sm text-slate-500">Tell us about the vehicle you’re adding to your fleet.</p>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <Input label="Make & model" name="makeModel" placeholder="e.g. Royal Enfield Classic 350" required />
              <Input label="Variant / trim" name="trim" placeholder="e.g. Classic Chrome" />
              <Input label="Registration number" name="registration" placeholder="e.g. GJ 05 AB 4821" required help="Format: GJ05AB4821 or GJ 05 AB 4821" />
              <Input label="Model year" name="year" type="number" min="2000" max={new Date().getFullYear() + 1} required />
              <Select label="Vehicle type" name="type" options={['Motorcycle', 'Scooter', 'Electric']} required />
              <Select label="Fuel type" name="fuel" options={['Petrol', 'Diesel', 'Electric']} required />
              <Input label="Color" name="color" placeholder="e.g. Forest green" />
              <Input label="Engine capacity (cc)" name="engineCapacity" type="number" min="0" placeholder="e.g. 350" />
              <Select label="Transmission" name="transmission" options={['Automatic', 'Manual']} required />
              <Select label="RC status" name="rcStatus" options={['Pending review', 'Verified']} required />
              <Select label="Seating capacity" name="seats" options={['1', '2']} />
            </div>
          </div>
        )}

        {step === 1 && (
          <div className="space-y-5">
            <div className="mb-1">
              <h2 className="text-lg font-semibold text-slate-900">Pricing & availability</h2>
              <p className="mt-1 text-sm text-slate-500">Set the daily rate and where guests can collect this vehicle.</p>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <Input label="Daily rental rate" name="rate" type="number" min="1" placeholder="e.g. 2,500" required help="Daily rate in Indian rupees (₹)." />
              <Input label="Minimum rental period" name="minimumDays" type="number" min="1" required help="How many days a booking must be for." />
              <Input label="Pickup location" name="location" placeholder="e.g. Indiranagar, Bengaluru" required />
              <label className="block sm:col-span-2">
                <span className="mb-1.5 block text-sm font-semibold text-slate-700">Pickup instructions <span className="font-normal text-slate-400">(optional)</span></span>
                <textarea
                  value={data.pickupNotes}
                  onChange={(event) => update('pickupNotes', event.target.value)}
                  rows="3"
                  placeholder="Share a helpful note for your renter…"
                  className="w-full resize-y rounded-xl border border-slate-200 bg-white px-3.5 py-3 text-sm text-slate-800 outline-none placeholder:text-slate-400 focus:border-emerald-500 focus:ring-3 focus:ring-emerald-100"
                />
              </label>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-5">
            <div className="mb-1">
              <h2 className="text-lg font-semibold text-slate-900">Documents & photos</h2>
              <p className="mt-1 text-sm text-slate-500">Upload vehicle photos. Compliance documents are temporarily disabled while private delivery storage is provisioned.</p>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <p className="mb-1.5 text-sm font-semibold text-slate-700">Vehicle photo</p>
                {photo?.preview ? (
                  <div className="relative h-48 overflow-hidden rounded-2xl border border-slate-200 bg-slate-50">
                    <img src={photo.preview} alt="Vehicle preview" className="h-full w-full object-cover" />
                    <button
                      type="button"
                      aria-label="Remove vehicle photo"
                      onClick={() => {
                        URL.revokeObjectURL(photo.preview)
                        setPhoto(null)
                      }}
                      className="absolute right-2 top-2 grid size-8 place-items-center rounded-full bg-white/90 text-slate-700 shadow hover:bg-white"
                    >
                      <X size={15} />
                    </button>
                    <p className="absolute inset-x-0 bottom-0 truncate bg-slate-950/50 px-3 py-2 text-xs text-white">{photo.name}</p>
                  </div>
                ) : (
                  <label className="flex h-48 cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-slate-50/70 text-center transition hover:border-emerald-400 hover:bg-emerald-50/40">
                    <ImagePlus size={24} className="text-emerald-700" />
                    <span className="mt-2 text-sm font-semibold text-slate-700">Choose a vehicle image</span>
                    <span className="mt-1 text-xs text-slate-400">JPEG, PNG, or WebP up to 10 MB</span>
                    <input type="file" accept="image/jpeg,image/png,image/webp" onChange={handlePhotoChange} className="sr-only" />
                  </label>
                )}
                {errors.photo && <span className="mt-1 block text-xs text-rose-600">{errors.photo}</span>}
              </div>

              {/* Disabled Documents Section per Requirement 1 */}
              <div className="opacity-75">
                <div className="flex items-center justify-between mb-1.5">
                  <p className="text-sm font-semibold text-slate-700">Compliance documents</p>
                  <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-800">
                    <Lock size={11} /> Coming soon
                  </span>
                </div>
                <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 p-4 text-center">
                  <FileCheck2 size={24} className="mx-auto text-slate-400" />
                  <p className="mt-2 text-xs font-medium text-slate-600">Document uploads are paused in Phase 1</p>
                  <p className="mt-1 text-[11px] text-slate-400">RC, Insurance, and PUC files will be available when private secured storage is connected.</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-5">
            <div className="mb-1">
              <h2 className="text-lg font-semibold text-slate-900">Review your vehicle</h2>
              <p className="mt-1 text-sm text-slate-500">Review all details before publishing this vehicle to your fleet.</p>
            </div>
            <div className="flex items-center gap-4 rounded-2xl border border-emerald-100 bg-gradient-to-r from-emerald-50 to-white p-4 sm:p-5">
              <span className="grid size-14 place-items-center overflow-hidden rounded-2xl bg-white text-3xl shadow-sm">
                {photo?.preview ? (
                  <img src={photo.preview} alt="" className="h-full w-full object-cover" />
                ) : data.type === 'Electric' ? (
                  '⚡'
                ) : data.type === 'Scooter' ? (
                  '🛵'
                ) : (
                  '🏍️'
                )}
              </span>
              <div className="min-w-0">
                <h3 className="truncate text-base font-semibold text-slate-900">{data.makeModel || 'Vehicle name'}</h3>
                <p className="mt-1 text-sm text-slate-500">
                  {data.registration.toUpperCase() || 'Registration number'} · {data.year}
                </p>
              </div>
              <span className="ml-auto shrink-0 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700">
                Offline
              </span>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              {[
                ['Variant / trim', data.trim],
                ['Registration / RC', data.registration.toUpperCase()],
                ['Model year', data.year],
                ['Vehicle type', data.type],
                ['Fuel & transmission', `${data.fuel || '—'} · ${data.transmission || '—'}`],
                ['Color', data.color],
                ['Engine capacity', data.engineCapacity ? `${data.engineCapacity} cc` : data.fuel === 'Electric' ? 'Electric' : 'Not specified'],
                ['RC status', data.rcStatus],
                ['Seating', `${data.seats} ${Number(data.seats) === 1 ? 'seat' : 'seats'}`],
                ['Daily rate', `₹${Number(data.rate || 0).toLocaleString('en-IN')} / day`],
                ['Minimum rental', `${data.minimumDays} ${Number(data.minimumDays) === 1 ? 'day' : 'days'}`],
                ['Pickup location', data.location],
                ['Pickup instructions', data.pickupNotes],
              ].map(([label, value]) => (
                <div key={label} className="rounded-xl border border-slate-100 bg-slate-50/60 p-3.5">
                  <p className="text-xs font-medium text-slate-400">{label}</p>
                  <p className="mt-1.5 text-sm font-semibold text-slate-800">{value || '—'}</p>
                </div>
              ))}
            </div>

            <div className="rounded-xl border border-slate-100 bg-slate-50/60 p-4">
              <p className="text-sm font-semibold text-slate-800">Vehicle photo</p>
              <p className="mt-1 text-xs text-slate-600">
                {photo?.name ? `Selected: ${photo.name}` : 'No photo uploaded.'}
              </p>
            </div>
          </div>
        )}

        <div className="mt-7 flex flex-col-reverse gap-2 border-t border-slate-100 pt-5 sm:flex-row sm:items-center sm:justify-between">
          <button
            type="button"
            disabled={step === 0 || createMutation.isPending}
            onClick={() => {
              setStep((current) => Math.max(0, current - 1))
              setErrors({})
            }}
            className="inline-flex h-11 items-center justify-center gap-2 rounded-xl border border-slate-200 px-4 text-sm font-semibold text-slate-600 transition hover:bg-slate-50 disabled:invisible"
          >
            <ArrowLeft size={15} /> Back
          </button>

          <div className="flex items-center justify-end gap-3">
            <span className="hidden text-xs text-slate-400 sm:block">
              Step {step + 1} of {steps.length}
            </span>
            {step < 3 ? (
              <button
                type="button"
                onClick={() => {
                  if (validateCurrentStep()) {
                    setErrors({})
                    setSubmitError('')
                    setStep((current) => current + 1)
                  }
                }}
                className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-emerald-800 px-5 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-900"
              >
                Continue <ArrowRight size={16} />
              </button>
            ) : (
              <button
                type="button"
                onClick={handleSubmit}
                disabled={createMutation.isPending}
                className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-emerald-800 px-5 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-900 disabled:opacity-50"
              >
                <Check size={16} />
                {createMutation.isPending ? 'Submitting…' : 'Add vehicle'}
              </button>
            )}
          </div>
        </div>

        {submitError && (
          <div className="mt-4 flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
            <AlertCircle size={16} className="shrink-0 text-rose-600" />
            <p>{submitError}</p>
          </div>
        )}
      </div>
    </section>
  )
}

export default AddVehicle
