import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  ArrowRight,
  BadgeCheck,
  CalendarDays,
  Check,
  CircleHelp,
  FileCheck2,
  ImagePlus,
  IndianRupee,
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
  const [step, setStep] = useState(0)
  const [data, setData] = useState(initialData)
  const [errors, setErrors] = useState({})
  const [photo, setPhoto] = useState(null)
  const [documents, setDocuments] = useState([])
  const [documentType, setDocumentType] = useState('RC')
  const [submitError, setSubmitError] = useState('')

  // Clear only the edited field's validation message while preserving other step errors.
  function update(field, value) {
    setData((current) => ({ ...current, [field]: value }))
    setErrors((current) => ({ ...current, [field]: '' }))
  }

  function validateStep() {
    const nextErrors = {}
    // Validate the current wizard step only, so users can advance without filling later sections.
    if (step === 0) {
      if (!data.makeModel.trim()) nextErrors.makeModel = 'Enter the vehicle make and model.'
      if (!data.registration.trim()) nextErrors.registration = 'Enter the registration number.'
      if (!data.year || Number(data.year) < 1900 || Number(data.year) > new Date().getFullYear() + 1) nextErrors.year = 'Enter a valid model year.'
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
    // Object URLs serve local previews only and are revoked when the selection is replaced or removed.
    if (kind === 'photo') {
      if (photo?.preview) URL.revokeObjectURL(photo.preview)
      setPhoto({ name: file.name, preview: file.type.startsWith('image/') ? URL.createObjectURL(file) : '', file })
    } else {
      setDocuments((current) => [...current, { id: `${Date.now()}-${file.name}`, name: file.name, size: file.size, type: documentType, url: URL.createObjectURL(file) }])
    }
    event.target.value = ''
  }

  function createVehicle() {
    setSubmitError('Vehicle creation is unavailable because no vehicle API is configured. Your entries and selected files have not been submitted.')
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

  return (
    <section className="mx-auto max-w-4xl space-y-5 pb-8 text-slate-800">
      <button type="button" onClick={() => navigate('/app/vehicles')} className="inline-flex items-center gap-2 text-sm font-medium text-slate-500 transition hover:text-emerald-800"><ArrowLeft size={16} /> Back to vehicles</button>
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
        <div><p className="mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-emerald-700">Fleet setup</p><h1 className="text-3xl font-semibold tracking-tight text-slate-900">Add a vehicle</h1><p className="mt-1.5 text-sm text-slate-500">A few details and you’ll be ready to list it in your fleet.</p></div>
        <span className="inline-flex w-fit items-center gap-1.5 rounded-full border border-amber-100 bg-amber-50 px-3 py-1.5 text-xs font-semibold text-amber-800"><ShieldCheck size={14} /> API not configured</span>
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
          <div className="flex gap-3 rounded-xl border border-emerald-100 bg-emerald-50/60 p-4"><IndianRupee size={18} className="mt-0.5 shrink-0 text-emerald-700" /><p className="text-xs leading-5 text-emerald-900/75"><span className="font-semibold">Manual pickup location.</span> Map selection is unavailable because no map configuration is present. Location details are not saved until a vehicle API is connected.</p></div>
        </div>}

        {step === 2 && <div className="space-y-5">
          <div className="mb-1"><h2 className="text-lg font-semibold text-slate-900">Documents & photos</h2><p className="mt-1 text-sm text-slate-500">Select RC, Insurance, PUC or other files for local preview. No upload service is configured.</p></div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div><p className="mb-1.5 text-sm font-semibold text-slate-700">Vehicle photo</p>{photo?.preview ? <div className="relative h-48 overflow-hidden rounded-2xl border border-slate-200 bg-slate-50"><img src={photo.preview} alt="Local vehicle preview" className="h-full w-full object-cover" /><button type="button" aria-label="Remove vehicle photo" onClick={() => { URL.revokeObjectURL(photo.preview); setPhoto(null) }} className="absolute right-2 top-2 grid size-8 place-items-center rounded-full bg-white/90 text-slate-700 shadow"><X size={15} /></button><p className="absolute inset-x-0 bottom-0 truncate bg-slate-950/50 px-3 py-2 text-xs text-white">{photo.name}</p></div> : <label className="flex h-48 cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-slate-50/70 text-center transition hover:border-emerald-400 hover:bg-emerald-50/40"><ImagePlus size={24} className="text-emerald-700" /><span className="mt-2 text-sm font-semibold text-slate-700">Choose a vehicle image</span><span className="mt-1 text-xs text-slate-400">Preview stays on this device</span><input type="file" accept="image/*" onChange={(event) => handleFile(event, 'photo')} className="sr-only" /></label>}</div>
            <div><p className="mb-1.5 text-sm font-semibold text-slate-700">Supporting documents <span className="font-normal text-slate-400">(optional)</span></p><select aria-label="Document type" value={documentType} onChange={(event) => setDocumentType(event.target.value)} className="mb-2 h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700"><option>RC</option><option>Insurance</option><option>PUC</option><option>Other</option></select><label className="flex h-32 cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-slate-50/70 text-center transition hover:border-emerald-400 hover:bg-emerald-50/40"><Upload size={22} className="text-emerald-700" /><span className="mt-2 text-sm font-semibold text-slate-700">Select a local file</span><span className="mt-1 text-xs text-slate-400">Preview only · not uploaded</span><input type="file" accept="image/*,.pdf" onChange={(event) => handleFile(event, 'document')} className="sr-only" /></label><div className="mt-3 space-y-2">{documents.map((document) => <div key={document.id} className="flex items-center gap-2 rounded-xl border border-slate-100 bg-white p-2.5"><FileCheck2 size={16} className="shrink-0 text-emerald-700" /><span className="min-w-0 flex-1 truncate text-xs font-medium text-slate-700">{document.type}: {document.name}</span><a href={document.url} target="_blank" rel="noreferrer" className="text-xs font-semibold text-emerald-800">View</a><button type="button" aria-label={`Remove ${document.name}`} onClick={() => { URL.revokeObjectURL(document.url); setDocuments((current) => current.filter((item) => item.id !== document.id)) }} className="grid size-7 place-items-center rounded-md text-slate-400 hover:bg-slate-100"><X size={14} /></button></div>)}</div></div>
          </div>
          <div className="flex gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3"><CircleHelp size={16} className="mt-0.5 shrink-0 text-slate-500" /><p className="text-xs leading-5 text-slate-500">Selected files stay in this browser tab as local previews. They are not uploaded, persisted, or included in a vehicle record.</p></div>
        </div>}

        {step === 3 && <div className="space-y-5">
          <div className="mb-1"><h2 className="text-lg font-semibold text-slate-900">Review your vehicle</h2><p className="mt-1 text-sm text-slate-500">Everything look right? You can go back to make changes.</p></div>
          <div className="flex items-center gap-4 rounded-2xl border border-emerald-100 bg-gradient-to-r from-emerald-50 to-white p-4 sm:p-5"><span className="grid size-14 place-items-center overflow-hidden rounded-2xl bg-white text-3xl shadow-sm">{photo?.preview ? <img src={photo.preview} alt="" className="h-full w-full object-cover" /> : data.type === 'Electric' ? '⚡' : data.type === 'Scooter' ? '🛵' : '🏍️'}</span><div className="min-w-0"><h3 className="truncate text-base font-semibold text-slate-900">{data.makeModel || 'Vehicle name'}</h3><p className="mt-1 text-sm text-slate-500">{data.registration.toUpperCase() || 'Registration number'} · {data.year}</p></div><span className="ml-auto shrink-0 rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-semibold text-emerald-800">Online</span></div>
          <div className="grid gap-3 sm:grid-cols-2">{[['Variant / trim', data.trim], ['Registration / RC', data.registration.toUpperCase()], ['Model year', data.year], ['Vehicle type', data.type], ['Fuel & transmission', `${data.fuel} · ${data.transmission}`], ['Color', data.color], ['Engine capacity', data.engineCapacity ? `${data.engineCapacity} cc` : data.fuel === 'Electric' ? 'Electric' : 'Not specified'], ['RC status', data.rcStatus], ['Seating', `${data.seats} ${Number(data.seats) === 1 ? 'seat' : 'seats'}`], ['Daily rate', `₹${Number(data.rate || 0).toLocaleString('en-IN')} / day`], ['Minimum rental', `${data.minimumDays} ${Number(data.minimumDays) === 1 ? 'day' : 'days'}`], ['Pickup location', data.location], ['Pickup instructions', data.pickupNotes]].map(([label, value]) => <div key={label} className="rounded-xl border border-slate-100 bg-slate-50/60 p-3.5"><p className="text-xs font-medium text-slate-400">{label}</p><p className="mt-1.5 text-sm font-semibold text-slate-800">{value || '—'}</p></div>)}</div>
          <div className="rounded-xl border border-slate-100 bg-slate-50/60 p-4"><p className="text-sm font-semibold text-slate-800">Selected documents ({documents.length})</p>{documents.length ? documents.map((document) => <p key={document.id} className="mt-1 text-xs text-slate-600">{document.type}: {document.name}</p>) : <p className="mt-1 text-xs text-slate-500">No documents selected.</p>}</div>
          <div className="flex items-start gap-3 rounded-xl bg-amber-50 p-4"><BadgeCheck size={17} className="mt-0.5 shrink-0 text-amber-700" /><p className="text-xs leading-5 text-amber-900">Review is available, but submitting is blocked because this project has no vehicle creation API or upload service.</p></div>
        </div>}

        <div className="mt-7 flex flex-col-reverse gap-2 border-t border-slate-100 pt-5 sm:flex-row sm:items-center sm:justify-between">
          <button type="button" disabled={step === 0} onClick={() => { setStep((current) => current - 1); setErrors({}) }} className="inline-flex h-11 items-center justify-center gap-2 rounded-xl border border-slate-200 px-4 text-sm font-semibold text-slate-600 transition hover:bg-slate-50 disabled:invisible"><ArrowLeft size={15} /> Back</button>
          <div className="flex items-center justify-end gap-3"><span className="hidden text-xs text-slate-400 sm:block">Step {step + 1} of {steps.length}</span>{step < 3 ? <button type="button" onClick={() => { if (step >= 2 || validateStep()) { setErrors({}); setSubmitError(''); setStep((current) => current + 1) } }} className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-emerald-800 px-5 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-900">Continue <ArrowRight size={16} /></button> : <button type="button" onClick={createVehicle} className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-slate-400 px-5 text-sm font-semibold text-white shadow-sm" aria-describedby="vehicle-submit-unavailable"><Check size={16} /> Submit unavailable</button>}</div>
        </div>
        {submitError && <p id="vehicle-submit-unavailable" role="alert" className="mt-4 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{submitError}</p>}
      </div>
      <p className="flex items-center justify-center gap-2 text-center text-xs text-slate-400"><CalendarDays size={14} /> No vehicle API or file upload service is currently configured.</p>
    </section>
  )
}

export default AddVehicle
