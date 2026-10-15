import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDemoData } from '../../data/DemoDataContext.jsx'
import {
  ArrowLeft,
  ArrowRight,
  BadgeCheck,
  CalendarDays,
  CarFront,
  Check,
  CheckCircle2,
  CircleHelp,
  FileCheck2,
  ImagePlus,
  IndianRupee,
  MapPin,
  ShieldCheck,
  Upload,
  X,
} from 'lucide-react'

const steps = ['Basic details', 'Pricing & availability', 'Documents', 'Review']
const initialData = {
  makeModel: '',
  trim: '',
  registration: '',
  year: '2024',
  type: '',
  fuel: '',
  color: '',
  engineCapacity: '',
  rcStatus: 'Pending review',
  seats: '5',
  transmission: '',
  rate: '',
  location: '',
  minimumDays: '1',
  pickupNotes: '',
}

function AddVehicle() {
  const navigate = useNavigate()
  const { addRecord } = useDemoData()
  const [step, setStep] = useState(0)
  const [data, setData] = useState(initialData)
  const [errors, setErrors] = useState({})
  const [photo, setPhoto] = useState(null)
  const [documents, setDocuments] = useState([])
  const [isComplete, setIsComplete] = useState(false)
  const [createdName, setCreatedName] = useState('')

  function update(field, value) {
    setData((current) => ({ ...current, [field]: value }))
    setErrors((current) => ({ ...current, [field]: '' }))
  }

  function validateStep() {
    const nextErrors = {}
    if (step === 0) {
      if (!data.makeModel.trim()) nextErrors.makeModel = 'Enter the vehicle make and model.'
      if (!data.registration.trim()) nextErrors.registration = 'Enter the registration number.'
      if (!data.type) nextErrors.type = 'Choose a vehicle type.'
      if (!data.fuel) nextErrors.fuel = 'Choose a fuel type.'
      if (!data.transmission) nextErrors.transmission = 'Choose a transmission.'
    }
    if (step === 1) {
      if (!data.rate || Number(data.rate) <= 0) nextErrors.rate = 'Enter a daily rate greater than ₹0.'
      if (!data.location.trim()) nextErrors.location = 'Add a pickup location.'
      if (!data.minimumDays || Number(data.minimumDays) < 1) nextErrors.minimumDays = 'Minimum rental must be at least one day.'
    }
    setErrors(nextErrors)
    return Object.keys(nextErrors).length === 0
  }

  function handleFile(event, kind) {
    const file = event.target.files?.[0]
    if (!file) return
    if (kind === 'photo') {
      setPhoto({ name: file.name, preview: file.type.startsWith('image/') ? URL.createObjectURL(file) : '' })
    } else {
      setDocuments((current) => [...current, { id: `${Date.now()}-${file.name}`, name: file.name, size: file.size }])
    }
    event.target.value = ''
  }

  function createVehicle() {
    const vehicleImage = data.type === 'Electric' ? '⚡' : data.type === 'Scooter' ? '🛵' : '🏍️'
    const vehicle = {
      id: `VH-${String(Date.now()).slice(-5)}`,
      name: data.makeModel.trim(),
      registration: data.registration.trim().toUpperCase(),
      type: data.type,
      fuel: data.fuel,
      color: data.color.trim(),
      engineCapacity: data.engineCapacity ? Number(data.engineCapacity) : null,
      rcStatus: data.rcStatus,
      year: Number(data.year),
      seats: Number(data.seats) || 1,
      status: 'Online',
      availability: 'Available',
      price: Number(data.rate),
      image: photo?.preview || vehicleImage,
    }
    addRecord('vehicles', vehicle)
    setCreatedName(vehicle.name)
    setIsComplete(true)
  }

  const Input = ({ label, name, placeholder, type = 'text', required = false, help, ...props }) => (
    <label className="block">
      <span className="mb-1.5 block text-sm font-semibold text-slate-700">{label}{required && <span className="ml-1 text-rose-500">*</span>}</span>
      <input type={type} value={data[name]} onChange={(event) => update(name, event.target.value)} placeholder={placeholder} {...props} className={`h-11 w-full rounded-xl border bg-white px-3.5 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-emerald-500 focus:ring-3 focus:ring-emerald-100 ${errors[name] ? 'border-rose-300' : 'border-slate-200'}`} />
      {errors[name] ? <span className="mt-1 block text-xs text-rose-600">{errors[name]}</span> : help ? <span className="mt-1 block text-xs text-slate-400">{help}</span> : null}
    </label>
  )

  const Select = ({ label, name, options, required = false }) => (
    <label className="block">
      <span className="mb-1.5 block text-sm font-semibold text-slate-700">{label}{required && <span className="ml-1 text-rose-500">*</span>}</span>
      <select value={data[name]} onChange={(event) => update(name, event.target.value)} className={`h-11 w-full rounded-xl border bg-white px-3.5 text-sm text-slate-700 outline-none transition focus:border-emerald-500 focus:ring-3 focus:ring-emerald-100 ${errors[name] ? 'border-rose-300' : 'border-slate-200'}`}>
        <option value="">Select {label.toLowerCase()}</option>{options.map((option) => <option key={option}>{option}</option>)}
      </select>
      {errors[name] && <span className="mt-1 block text-xs text-rose-600">{errors[name]}</span>}
    </label>
  )

  if (isComplete) {
    return (
      <section className="mx-auto max-w-2xl pb-10 text-slate-800">
        <div className="overflow-hidden rounded-3xl border border-slate-200/80 bg-white shadow-[0_12px_45px_rgba(15,23,42,0.06)]">
          <div className="bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-emerald-100 via-emerald-50 to-white px-6 pb-8 pt-10 text-center sm:px-10">
            <span className="mx-auto grid size-16 place-items-center rounded-full bg-white text-emerald-700 shadow-sm"><CheckCircle2 size={34} /></span>
            <p className="mt-5 text-xs font-semibold uppercase tracking-[0.16em] text-emerald-700">Saved in this browser</p>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">Your vehicle is ready</h1>
            <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500"><span className="font-semibold text-slate-700">{createdName}</span> has been added to your shared demo fleet for this workspace session. No vehicle data was sent to a server.</p>
          </div>
          <div className="mx-5 mb-5 rounded-2xl border border-slate-100 bg-slate-50/70 p-4 sm:mx-8 sm:p-5">
            <div className="flex items-center gap-3"><span className="grid size-11 place-items-center rounded-xl bg-emerald-100 text-emerald-800"><CarFront size={21} /></span><div><p className="text-sm font-semibold text-slate-800">{createdName}</p><p className="mt-1 text-xs text-slate-500">{data.registration.toUpperCase()} · ₹{Number(data.rate).toLocaleString('en-IN')} / day</p></div><span className="ml-auto rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-semibold text-emerald-800">Online</span></div>
          </div>
          <div className="flex flex-col gap-2 border-t border-slate-100 p-5 sm:flex-row sm:justify-end sm:px-8"><button type="button" onClick={() => { setData(initialData); setPhoto(null); setDocuments([]); setStep(0); setIsComplete(false) }} className="h-11 rounded-xl border border-slate-200 px-4 text-sm font-semibold text-slate-700 hover:bg-slate-50">Add another vehicle</button><button type="button" onClick={() => navigate('/app/vehicles')} className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-emerald-800 px-5 text-sm font-semibold text-white hover:bg-emerald-900">View fleet <ArrowRight size={16} /></button></div>
        </div>
      </section>
    )
  }

  return (
    <section className="mx-auto max-w-4xl space-y-5 pb-8 text-slate-800">
      <button type="button" onClick={() => navigate('/app/vehicles')} className="inline-flex items-center gap-2 text-sm font-medium text-slate-500 transition hover:text-emerald-800"><ArrowLeft size={16} /> Back to vehicles</button>
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
        <div><p className="mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-emerald-700">Fleet setup</p><h1 className="text-3xl font-semibold tracking-tight text-slate-900">Add a vehicle</h1><p className="mt-1.5 text-sm text-slate-500">A few details and you’ll be ready to list it in your fleet.</p></div>
        <span className="inline-flex w-fit items-center gap-1.5 rounded-full border border-emerald-100 bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-800"><ShieldCheck size={14} /> Private demo setup</span>
      </div>

      <div className="rounded-2xl border border-slate-200/80 bg-white px-4 py-5 shadow-[0_4px_22px_rgba(15,23,42,0.035)] sm:px-7">
        <div className="mb-6 grid grid-cols-4 gap-2 sm:gap-4">
          {steps.map((label, index) => <div key={label} className="min-w-0"><div className="flex items-center gap-2">{index < step ? <span className="grid size-7 shrink-0 place-items-center rounded-full bg-emerald-700 text-white"><Check size={14} /></span> : <span className={`grid size-7 shrink-0 place-items-center rounded-full text-xs font-semibold ${index === step ? 'bg-emerald-700 text-white' : 'bg-slate-100 text-slate-500'}`}>{index + 1}</span>}<span className={`hidden truncate text-xs font-semibold sm:block ${index === step ? 'text-slate-900' : 'text-slate-400'}`}>{label}</span></div><div className={`mt-2 h-1 rounded-full ${index <= step ? 'bg-emerald-600' : 'bg-slate-100'}`} /><span className={`mt-1.5 block truncate text-[10px] font-medium sm:hidden ${index === step ? 'text-slate-700' : 'text-slate-400'}`}>{label}</span></div>)}
        </div>

        {step === 0 && <div className="animate-in space-y-5">
          <div className="mb-1"><h2 className="text-lg font-semibold text-slate-900">Basic details</h2><p className="mt-1 text-sm text-slate-500">Tell us about the vehicle you’re adding to your fleet.</p></div>
          <div className="grid gap-4 sm:grid-cols-2"><Input label="Make & model" name="makeModel" placeholder="e.g. Royal Enfield Classic 350" required /><Input label="Variant / trim" name="trim" placeholder="e.g. Classic Chrome" /><Input label="Registration number" name="registration" placeholder="e.g. GJ 05 AB 4821" required /><Input label="Model year" name="year" type="number" min="2000" max="2030" required /><Select label="Vehicle type" name="type" options={['Motorcycle', 'Scooter', 'Electric']} required /><Select label="Fuel type" name="fuel" options={['Petrol', 'Diesel', 'Electric']} required /><Input label="Color" name="color" placeholder="e.g. Forest green" /><Input label="Engine capacity (cc)" name="engineCapacity" type="number" min="0" placeholder="e.g. 350" /><Select label="Transmission" name="transmission" options={['Automatic', 'Manual']} required /><Select label="RC status" name="rcStatus" options={['Pending review', 'Verified']} required /><Select label="Seating capacity" name="seats" options={['1', '2']} /></div>
        </div>}

        {step === 1 && <div className="space-y-5">
          <div className="mb-1"><h2 className="text-lg font-semibold text-slate-900">Pricing & availability</h2><p className="mt-1 text-sm text-slate-500">Set the daily rate and where guests can collect this vehicle.</p></div>
          <div className="grid gap-4 sm:grid-cols-2"><Input label="Daily rental rate" name="rate" type="number" min="1" placeholder="e.g. 2,500" required help="Your demo rate is shown in Indian rupees per day." /><Input label="Minimum rental period" name="minimumDays" type="number" min="1" required help="How many days a booking must be for." /><Input label="Pickup location" name="location" placeholder="e.g. Indiranagar, Bengaluru" required /><label className="block sm:col-span-2"><span className="mb-1.5 block text-sm font-semibold text-slate-700">Pickup instructions <span className="font-normal text-slate-400">(optional)</span></span><textarea value={data.pickupNotes} onChange={(event) => update('pickupNotes', event.target.value)} rows="3" placeholder="Share a helpful note for your renter…" className="w-full resize-y rounded-xl border border-slate-200 bg-white px-3.5 py-3 text-sm text-slate-800 outline-none placeholder:text-slate-400 focus:border-emerald-500 focus:ring-3 focus:ring-emerald-100" /></label></div>
          <div className="flex gap-3 rounded-xl border border-emerald-100 bg-emerald-50/60 p-4"><IndianRupee size={18} className="mt-0.5 shrink-0 text-emerald-700" /><p className="text-xs leading-5 text-emerald-900/75"><span className="font-semibold">Your pricing is yours to manage.</span> This preview does not calculate fees, take payments or publish a live listing.</p></div>
        </div>}

        {step === 2 && <div className="space-y-5">
          <div className="mb-1"><h2 className="text-lg font-semibold text-slate-900">Documents & photos</h2><p className="mt-1 text-sm text-slate-500">Add local previews to help identify the vehicle. Files are not uploaded.</p></div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div><p className="mb-1.5 text-sm font-semibold text-slate-700">Vehicle photo</p>{photo?.preview ? <div className="relative h-48 overflow-hidden rounded-2xl border border-slate-200 bg-slate-50"><img src={photo.preview} alt="Local vehicle preview" className="h-full w-full object-cover" /><button type="button" aria-label="Remove vehicle photo" onClick={() => setPhoto(null)} className="absolute right-2 top-2 grid size-8 place-items-center rounded-full bg-white/90 text-slate-700 shadow"><X size={15} /></button><p className="absolute inset-x-0 bottom-0 truncate bg-slate-950/50 px-3 py-2 text-xs text-white">{photo.name}</p></div> : <label className="flex h-48 cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-slate-50/70 text-center transition hover:border-emerald-400 hover:bg-emerald-50/40"><ImagePlus size={24} className="text-emerald-700" /><span className="mt-2 text-sm font-semibold text-slate-700">Choose a vehicle image</span><span className="mt-1 text-xs text-slate-400">Preview stays on this device</span><input type="file" accept="image/*" onChange={(event) => handleFile(event, 'photo')} className="sr-only" /></label>}</div>
            <div><p className="mb-1.5 text-sm font-semibold text-slate-700">Supporting documents <span className="font-normal text-slate-400">(optional)</span></p><label className="flex h-32 cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-slate-50/70 text-center transition hover:border-emerald-400 hover:bg-emerald-50/40"><Upload size={22} className="text-emerald-700" /><span className="mt-2 text-sm font-semibold text-slate-700">Select a local file</span><span className="mt-1 text-xs text-slate-400">Registration, insurance, or permit</span><input type="file" accept="image/*,.pdf" onChange={(event) => handleFile(event, 'document')} className="sr-only" /></label><div className="mt-3 space-y-2">{documents.map((document) => <div key={document.id} className="flex items-center gap-2 rounded-xl border border-slate-100 bg-white p-2.5"><FileCheck2 size={16} className="shrink-0 text-emerald-700" /><span className="min-w-0 flex-1 truncate text-xs font-medium text-slate-700">{document.name}</span><span className="text-[10px] text-slate-400">{document.size < 1024 * 1024 ? `${Math.max(1, Math.round(document.size / 1024))} KB` : `${(document.size / (1024 * 1024)).toFixed(1)} MB`}</span><button type="button" aria-label={`Remove ${document.name}`} onClick={() => setDocuments((current) => current.filter((item) => item.id !== document.id))} className="grid size-7 place-items-center rounded-md text-slate-400 hover:bg-slate-100"><X size={14} /></button></div>)}</div></div>
          </div>
          <div className="flex gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3"><CircleHelp size={16} className="mt-0.5 shrink-0 text-slate-500" /><p className="text-xs leading-5 text-slate-500">Selected images are previewed locally and document names are shown for review. Files are not uploaded or included in the shared vehicle record.</p></div>
        </div>}

        {step === 3 && <div className="space-y-5">
          <div className="mb-1"><h2 className="text-lg font-semibold text-slate-900">Review your vehicle</h2><p className="mt-1 text-sm text-slate-500">Everything look right? You can go back to make changes.</p></div>
          <div className="flex items-center gap-4 rounded-2xl border border-emerald-100 bg-gradient-to-r from-emerald-50 to-white p-4 sm:p-5"><span className="grid size-14 place-items-center overflow-hidden rounded-2xl bg-white text-3xl shadow-sm">{photo?.preview ? <img src={photo.preview} alt="" className="h-full w-full object-cover" /> : data.type === 'Electric' ? '⚡' : data.type === 'Scooter' ? '🛵' : '🏍️'}</span><div className="min-w-0"><h3 className="truncate text-base font-semibold text-slate-900">{data.makeModel || 'Vehicle name'}</h3><p className="mt-1 text-sm text-slate-500">{data.registration.toUpperCase() || 'Registration number'} · {data.year}</p></div><span className="ml-auto shrink-0 rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-semibold text-emerald-800">Online</span></div>
          <div className="grid gap-3 sm:grid-cols-2">{[['Vehicle type', data.type], ['Fuel & transmission', `${data.fuel} · ${data.transmission}`], ['Color', data.color], ['Engine capacity', data.engineCapacity ? `${data.engineCapacity} cc` : data.fuel === 'Electric' ? 'Electric' : 'Not specified'], ['RC status', data.rcStatus], ['Seating', `${data.seats} ${Number(data.seats) === 1 ? 'seat' : 'seats'}`], ['Daily rate', `₹${Number(data.rate || 0).toLocaleString('en-IN')} / day`], ['Minimum rental', `${data.minimumDays} ${Number(data.minimumDays) === 1 ? 'day' : 'days'}`], ['Pickup location', data.location]].map(([label, value]) => <div key={label} className="rounded-xl border border-slate-100 bg-slate-50/60 p-3.5"><p className="text-xs font-medium text-slate-400">{label}</p><p className="mt-1.5 text-sm font-semibold text-slate-800">{value || '—'}</p></div>)}</div>
          <div className="flex items-start gap-3 rounded-xl bg-slate-50 p-4"><BadgeCheck size={17} className="mt-0.5 shrink-0 text-emerald-700" /><p className="text-xs leading-5 text-slate-500">You’re saving a demo vehicle to this browser only. Nothing will be published or transmitted.</p></div>
        </div>}

        <div className="mt-7 flex flex-col-reverse gap-2 border-t border-slate-100 pt-5 sm:flex-row sm:items-center sm:justify-between">
          <button type="button" disabled={step === 0} onClick={() => { setStep((current) => current - 1); setErrors({}) }} className="inline-flex h-11 items-center justify-center gap-2 rounded-xl border border-slate-200 px-4 text-sm font-semibold text-slate-600 transition hover:bg-slate-50 disabled:invisible"><ArrowLeft size={15} /> Back</button>
          <div className="flex items-center justify-end gap-3"><span className="hidden text-xs text-slate-400 sm:block">Step {step + 1} of {steps.length}</span>{step < 3 ? <button type="button" onClick={() => { if (step >= 2 || validateStep()) { setErrors({}); setStep((current) => current + 1) } }} className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-emerald-800 px-5 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-900">Continue <ArrowRight size={16} /></button> : <button type="button" onClick={createVehicle} className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-emerald-800 px-5 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-900"><Check size={16} /> Add demo vehicle</button>}</div>
        </div>
      </div>
      <p className="flex items-center justify-center gap-2 text-center text-xs text-slate-400"><CalendarDays size={14} /> Your progress is held in this screen and will not be submitted to a service.</p>
    </section>
  )
}

export default AddVehicle
