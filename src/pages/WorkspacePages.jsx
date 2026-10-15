import { useState } from 'react'
import {
  ArrowDownToLine,
  ArrowUpRight,
  BadgeIndianRupee,
  CalendarDays,
  Check,
  CircleDollarSign,
  ClipboardList,
  Download,
  Eye,
  FileText,
  Plus,
  Settings2,
  ShieldCheck,
  Upload,
  Users,
  Wallet,
  Wrench,
} from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import { useDemoData } from '../data/DemoDataContext.jsx'
import {
  BarChart,
  Button,
  Card,
  ComparisonChart,
  DataTable,
  Field,
  FilterSelect,
  MetricCard,
  Modal,
  PageHeader,
  SearchField,
  StatusBadge,
  Tabs,
} from '../components/ui/Workspace.jsx'

const currency = (amount) =>
  `₹${Number(amount || 0).toLocaleString('en-IN')}`

function nextId(prefix, records) {
  const max = records.reduce((largest, record) => {
    const number = Number(record.id?.match(/\d+$/)?.[0] || 0)
    return Math.max(largest, number)
  }, 0)
  return `${prefix}-${max + 1}`
}

function RecordForm({ title, fields, onClose, onSave, saveLabel = 'Save to demo' }) {
  const initialValues = Object.fromEntries(fields.map((field) => [field.name, field.initial || '']))
  const [values, setValues] = useState(initialValues)
  const [error, setError] = useState('')

  function submit(event) {
    event.preventDefault()
    const missing = fields.find(
      (field) => field.required && !String(values[field.name] || '').trim(),
    )
    if (missing) {
      setError(`${missing.label} is required.`)
      return
    }
    setError('')
    onSave(values)
  }

  return (
    <Modal
      title={title}
      onClose={onClose}
      footer={
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" form="record-form"><Check size={15} />{saveLabel}</Button>
        </div>
      }
    >
      <form id="record-form" onSubmit={submit} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          {fields.map((field) => (
            <label key={field.name} className={`block ${field.wide ? 'sm:col-span-2' : ''}`}>
              <span className="mb-1.5 block text-xs font-medium text-slate-600">
                {field.label}{field.required && <span className="ml-0.5 text-rose-500">*</span>}
              </span>
              {field.type === 'select' ? (
                <select
                  required={field.required}
                  value={values[field.name]}
                  onChange={(event) =>
                    setValues((current) => ({ ...current, [field.name]: event.target.value }))
                  }
                  className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
                >
                  <option value="">Select {field.label.toLowerCase()}</option>
                  {field.options.map((option) => (
                    <option value={option.value || option} key={option.value || option}>
                      {option.label || option}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  required={field.required}
                  type={field.type || 'text'}
                  min={field.min}
                  step={field.step}
                  value={field.type === 'file' ? undefined : values[field.name]}
                  placeholder={field.placeholder}
                  onChange={(event) => setValues((current) => ({
                    ...current,
                    [field.name]: field.type === 'file'
                      ? event.target.files?.[0]?.name || ''
                      : event.target.value,
                  }))}
                  className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100 placeholder:text-slate-400"
                />
              )}
            </label>
          ))}
        </div>
        {error && <p role="alert" className="text-xs text-rose-600">{error}</p>}
        <p className="rounded-xl bg-amber-50 px-3 py-2 text-[11px] leading-5 text-amber-800">
          Demo only. This record is held in page state and is not sent to a server.
        </p>
      </form>
    </Modal>
  )
}

function DetailDialog({ title, rows, onClose }) {
  return (
    <Modal title={title} onClose={onClose}>
      <div className="space-y-3">
        {rows.map(([label, value]) => (
          <div key={label} className="flex items-start justify-between gap-4 border-b border-slate-100 pb-2.5 last:border-0">
            <span className="text-xs text-slate-500">{label}</span>
            <span className="text-right text-xs font-medium text-slate-800">{value || '—'}</span>
          </div>
        ))}
        <p className="pt-1 text-[11px] text-slate-400">Sample workspace details · Demo data only</p>
      </div>
    </Modal>
  )
}

function Customers() {
  const { customers, addRecord } = useDemoData()
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('All')
  const [searchParams] = useSearchParams()
  const [showForm, setShowForm] = useState(() => searchParams.get('new') === '1')
  const [selected, setSelected] = useState(null)

  const filtered = customers.filter((customer) =>
    `${customer.name} ${customer.phone} ${customer.email} ${customer.id}`.toLowerCase().includes(query.toLowerCase())
    && (status === 'All' || customer.status === status),
  )
  const totalPaid = customers.reduce((total, item) => total + item.paid, 0)
  const pending = customers.reduce((total, item) => total + item.pending, 0)

  return (
    <div>
      <PageHeader
        title="Customers"
        description="Get to know your customers and keep their rental history in one place."
        action={<Button onClick={() => setShowForm(true)}><Plus size={16} />Add customer</Button>}
      />
      <div className="mb-5 grid grid-cols-2 gap-3 xl:grid-cols-4">
        <MetricCard label="Total customers" value={customers.length} caption="In this demo workspace" icon={Users} />
        <MetricCard label="Verified profiles" value={customers.filter((item) => item.status === 'Verified').length} icon={ShieldCheck} tone="blue" />
        <MetricCard label="Total collected" value={currency(totalPaid)} icon={BadgeIndianRupee} tone="violet" />
        <MetricCard label="Pending customer dues" value={currency(pending)} icon={Wallet} tone="amber" />
      </div>
      <Card className="overflow-hidden">
        <div className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5">
          <SearchField value={query} onChange={setQuery} placeholder="Search customers…" />
          <FilterSelect label="Status" value={status} onChange={setStatus} options={['All', 'Verified', 'Review']} />
        </div>
        <DataTable
          rows={filtered}
          columns={[
            { key: 'customer', label: 'Customer', render: (row) => <button type="button" onClick={() => setSelected(row)} className="text-left font-medium text-slate-800 hover:text-emerald-800">{row.name}<span className="mt-1 block text-[11px] font-normal text-slate-400">{row.id} · {row.email}</span></button> },
            { key: 'phone', label: 'Phone' },
            { key: 'bookings', label: 'Bookings', render: (row) => <span>{row.bookings} <span className="text-[11px] text-slate-400">· {row.active} active</span></span> },
            { key: 'paid', label: 'Total paid', render: (row) => currency(row.paid) },
            { key: 'pending', label: 'Pending', render: (row) => currency(row.pending) },
            { key: 'status', label: 'Status', render: (row) => <StatusBadge status={row.status} /> },
            { key: 'view', label: '', render: (row) => <Button variant="quiet" className="min-h-8 px-2.5" onClick={() => setSelected(row)}><Eye size={15} />View</Button> },
          ]}
        />
        <p className="border-t border-slate-100 px-5 py-3 text-[11px] text-slate-400">{filtered.length} demo customers</p>
      </Card>
      {showForm && (
        <RecordForm
          title="Add a customer"
          onClose={() => setShowForm(false)}
          fields={[
            { name: 'name', label: 'Full name', required: true },
            { name: 'phone', label: 'Phone number', required: true, type: 'tel' },
            { name: 'email', label: 'Email address', type: 'email' },
            { name: 'status', label: 'Profile status', type: 'select', options: ['Review', 'Verified'], required: true },
          ]}
          onSave={(values) => {
            addRecord('customers', { ...values, id: nextId('CU', customers), bookings: 0, active: 0, paid: 0, pending: 0 })
            setShowForm(false)
          }}
        />
      )}
      {selected && (
        <DetailDialog
          title={selected.name}
          record={selected}
          onClose={() => setSelected(null)}
          rows={[
            ['Customer ID', selected.id], ['Phone', selected.phone], ['Email', selected.email],
            ['Profile status', selected.status], ['Total bookings', selected.bookings],
            ['Active bookings', selected.active], ['Total paid', currency(selected.paid)],
            ['Pending amount', currency(selected.pending)],
          ]}
        />
      )}
    </div>
  )
}

function Bookings() {
  const { bookings, updateRecord } = useDemoData()
  const [query, setQuery] = useState('')
  const [tab, setTab] = useState('All')
  const [selected, setSelected] = useState(null)
  const [paymentForm, setPaymentForm] = useState(null)
  const online = bookings.filter((item) => item.type === 'Online').length
  const offline = bookings.filter((item) => item.type === 'Offline').length
  const revenue = bookings.reduce((sum, item) => sum + item.paid, 0)
  const pending = bookings.reduce((sum, item) => sum + item.pending, 0)
  const tabs = ['All', 'Online', 'Offline', 'Active', 'Completed', 'Cancelled']
  const filtered = bookings.filter((booking) => {
    const termMatch = `${booking.id} ${booking.customer} ${booking.vehicle}`.toLowerCase().includes(query.toLowerCase())
    const tabMatch = tab === 'All' || booking.type === tab || booking.status === tab
    return termMatch && tabMatch
  })

  return (
    <div>
      <PageHeader
        title="Bookings"
        description="Track online and in-store rentals, upcoming handovers and payments."
        action={<Link to="/app/bookings/new"><Button><Plus size={16} />Offline booking</Button></Link>}
      />
      <div className="mb-5 grid grid-cols-2 gap-3 xl:grid-cols-4">
        <MetricCard label="Total bookings" value={bookings.length} caption="Sample records" icon={ClipboardList} />
        <MetricCard label="Online bookings" value={online} icon={ArrowUpRight} tone="blue" />
        <MetricCard label="Offline bookings" value={offline} icon={CalendarDays} tone="violet" />
        <MetricCard label="Revenue · pending" value={`${currency(revenue)} · ${currency(pending)}`} icon={CircleDollarSign} tone="amber" />
      </div>
      <Card className="overflow-hidden">
        <Tabs items={tabs.map((label) => ({ label, value: label, count: label === 'All' ? bookings.length : undefined }))} value={tab} onChange={setTab} />
        <div className="p-4 sm:p-5"><SearchField value={query} onChange={setQuery} placeholder="Search ID, customer or vehicle…" /></div>
        <DataTable
          rows={filtered}
          columns={[
            { key: 'id', label: 'Booking ID', render: (row) => <button type="button" onClick={() => setSelected(row)} className="font-semibold text-emerald-800 hover:underline">{row.id}</button> },
            { key: 'customer', label: 'Customer', render: (row) => <><span className="font-medium text-slate-800">{row.customer}</span><span className="mt-1 block text-[11px] text-slate-400">{row.vehicle}</span></> },
            { key: 'dates', label: 'Rental dates' },
            { key: 'type', label: 'Type', render: (row) => <span className="text-xs">{row.type}</span> },
            { key: 'status', label: 'Status', render: (row) => <StatusBadge status={row.status} /> },
            { key: 'paid', label: 'Paid', render: (row) => currency(row.paid) },
            { key: 'pending', label: 'Pending', render: (row) => currency(row.pending) },
            { key: 'actions', label: '', render: (row) => <div className="flex gap-1"><Button variant="quiet" className="min-h-8 px-2" aria-label={`View ${row.id}`} onClick={() => setSelected(row)}><Eye size={15} /></Button>{row.pending > 0 && <Button variant="quiet" className="min-h-8 px-2" onClick={() => setPaymentForm(row)}>Update payment</Button>}</div> },
          ]}
        />
        <p className="border-t border-slate-100 px-5 py-3 text-[11px] text-slate-400">Demo booking records · {filtered.length} shown</p>
      </Card>
      {selected && <DetailDialog title={`Booking ${selected.id}`} onClose={() => setSelected(null)} record={selected} rows={Object.entries(selected).map(([key, value]) => [key.replace(/([A-Z])/g, ' $1').replace(/^./, (char) => char.toUpperCase()), ['paid', 'pending'].includes(key) ? currency(value) : value])} />}
      {paymentForm && (
        <RecordForm
          title={`Record payment · ${paymentForm.id}`}
          onClose={() => setPaymentForm(null)}
          fields={[{ name: 'amount', label: 'Payment amount (₹)', type: 'number', min: 1, required: true }]}
          onSave={(values) => {
            const amount = Math.min(Number(values.amount), paymentForm.pending)
            updateRecord('bookings', paymentForm.id, { paid: paymentForm.paid + amount, pending: paymentForm.pending - amount })
            setPaymentForm(null)
          }}
          saveLabel="Record in demo"
        />
      )}
    </div>
  )
}

function Payments() {
  const { payments } = useDemoData()
  const [query, setQuery] = useState('')
  const [tab, setTab] = useState('All')
  const [dateRange, setDateRange] = useState('This month')
  const [selected, setSelected] = useState(null)
  const revenue = payments.reduce((sum, payment) => sum + payment.amount, 0)
  const filtered = payments.filter((payment) =>
    `${payment.id} ${payment.booking} ${payment.customer} ${payment.method}`.toLowerCase().includes(query.toLowerCase())
    && (tab === 'All' || payment.status === tab),
  ).filter((payment) => dateRange === 'All time' || payment.date.includes('Oct 2026'))

  return (
    <div>
      <PageHeader title="Payments & finance" description="A clear picture of collections and outstanding payments. This demo does not process real transactions." action={<div className="flex flex-wrap gap-2"><FilterSelect label="Status" value={tab} onChange={setTab} options={['All', 'Paid', 'Partial']} /><FilterSelect value={dateRange} onChange={setDateRange} options={['This month', 'Last month', 'All time']} /></div>} />
      <div className="mb-5 grid grid-cols-2 gap-3 xl:grid-cols-4">
        <MetricCard label="Collected · demo" value={currency(revenue)} caption="From sample transactions" icon={BadgeIndianRupee} />
        <MetricCard label="Online bookings" value={currency(248900)} caption="Illustrative month total" icon={ArrowUpRight} tone="blue" />
        <MetricCard label="Offline revenue" value={currency(105900)} caption="Illustrative month total" icon={Wallet} tone="violet" />
        <MetricCard label="Pending payments" value={currency(18450)} caption="Sample outstanding balance" icon={CircleDollarSign} tone="amber" />
      </div>
      <div className="mb-4 grid gap-4 xl:grid-cols-[minmax(0,1.5fr)_minmax(280px,0.8fr)]">
        <Card className="p-5 sm:p-6">
          <div className="flex flex-wrap justify-between gap-3">
            <div><h2 className="text-sm font-semibold text-slate-900">Revenue vs. expenses</h2><p className="mt-1 text-xs text-slate-500">Illustrative monthly summary · ₹</p></div>
            <FilterSelect value={dateRange} onChange={setDateRange} options={['This month', 'Last month', 'All time']} />
          </div>
          <div className="mt-4"><ComparisonChart data={[{ label: 'May', revenue: 18, expenses: 9 }, { label: 'Jun', revenue: 22, expenses: 12 }, { label: 'Jul', revenue: 19, expenses: 11 }, { label: 'Aug', revenue: 26, expenses: 14 }, { label: 'Sep', revenue: 31, expenses: 16 }, { label: 'Oct', revenue: 35, expenses: 18 }]} /></div>
        </Card>
        <Card className="p-5 sm:p-6">
          <h2 className="text-sm font-semibold text-slate-900">Finance snapshot</h2>
          <p className="mt-1 text-xs text-slate-500">Illustrative totals for October</p>
          <div className="mt-4 space-y-3">
            {[
              ['Current balance', '₹2,84,450', 'text-emerald-700'],
              ['Operating expenses', '₹72,800', 'text-slate-800'],
              ['Maintenance costs', '₹18,450', 'text-slate-800'],
              ['Estimated net', '₹2,11,650', 'text-emerald-700'],
            ].map(([label, amount, tone]) => <div key={label} className="flex justify-between border-b border-slate-100 pb-2.5 text-xs last:border-0"><span className="text-slate-500">{label}</span><span className={`font-semibold ${tone}`}>{amount}</span></div>)}
          </div>
        </Card>
      </div>
      <Card className="overflow-hidden">
        <div className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5"><div><h2 className="text-sm font-semibold text-slate-900">Recent transactions</h2><p className="mt-1 text-xs text-slate-500">Sample records only · no payment gateway connected</p></div><SearchField value={query} onChange={setQuery} placeholder="Search transactions…" /></div>
        <DataTable rows={filtered} columns={[
          { key: 'id', label: 'Transaction', render: (row) => <span className="font-semibold text-slate-800">{row.id}<span className="mt-1 block text-[11px] font-normal text-slate-400">{row.booking}</span></span> },
          { key: 'customer', label: 'Customer' }, { key: 'method', label: 'Method' }, { key: 'date', label: 'Date' },
          { key: 'amount', label: 'Amount', render: (row) => currency(row.amount) },
          { key: 'status', label: 'Status', render: (row) => <StatusBadge status={row.status} /> },
          { key: 'view', label: '', render: (row) => <Button variant="quiet" className="min-h-8 px-2.5" onClick={() => setSelected(row)}><Eye size={15} />Details</Button> },
        ]} />
      </Card>
      {selected && <DetailDialog title={`Transaction ${selected.id}`} record={selected} onClose={() => setSelected(null)} rows={Object.entries(selected).map(([key, value]) => [key, key === 'amount' ? currency(value) : value])} />}
    </div>
  )
}

function Documents() {
  const { documents, addRecord } = useDemoData()
  const [tab, setTab] = useState('Business')
  const [selected, setSelected] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [fileName, setFileName] = useState('')
  const filtered = documents.filter((document) => document.scope === tab)

  return (
    <div>
      <PageHeader title="Documents" description="Keep business and vehicle paperwork organized in one place." action={<Button onClick={() => setShowForm(true)}><Upload size={16} />Upload document</Button>} />
      <div className="mb-5 grid grid-cols-2 gap-3 xl:grid-cols-3">
        <MetricCard label="All documents" value={documents.length} icon={FileText} />
        <MetricCard label="Verified" value={documents.filter((item) => item.status === 'Verified').length} icon={ShieldCheck} tone="green" />
        <MetricCard label="Needs attention" value={documents.filter((item) => item.status !== 'Verified').length} icon={CalendarDays} tone="amber" />
      </div>
      <Card className="overflow-hidden">
        <Tabs items={['Business', 'Vehicle']} value={tab} onChange={setTab} />
        <div className="px-4 py-4 sm:px-5"><div className="rounded-xl border border-amber-200/80 bg-amber-50 px-3.5 py-2.5 text-xs leading-5 text-amber-800">Simulated document records. Files are not uploaded or stored on a server in this demo.</div></div>
        <DataTable rows={filtered} columns={[
          { key: 'name', label: 'Document', render: (row) => <span className="flex items-center gap-3"><span className="grid size-9 place-items-center rounded-lg bg-emerald-50 text-emerald-700"><FileText size={16} /></span><span className="font-medium text-slate-800">{row.name}<span className="mt-1 block text-[11px] font-normal text-slate-400">{row.id}</span></span></span> },
          { key: 'category', label: 'Category' }, { key: 'date', label: 'Uploaded' },
          { key: 'status', label: 'Status', render: (row) => <StatusBadge status={row.status} /> },
          { key: 'actions', label: '', render: (row) => <div className="flex gap-1"><Button variant="quiet" className="min-h-8 px-2" onClick={() => setSelected(row)} aria-label={`Preview ${row.name}`}><Eye size={15} />Preview</Button><Button variant="quiet" className="min-h-8 px-2" onClick={() => setSelected(row)} aria-label={`Download ${row.name}`}><Download size={15} /></Button></div> },
        ]} />
        <p className="border-t border-slate-100 px-5 py-3 text-[11px] text-slate-400">{filtered.length} simulated {tab.toLowerCase()} documents</p>
      </Card>
      {showForm && <RecordForm title="Add a demo document" onClose={() => { setShowForm(false); setFileName('') }} fields={[
        { name: 'name', label: 'Document name', required: true },
        { name: 'category', label: 'Category', type: 'select', options: ['Shop License', 'GST Certificate', 'Insurance', 'PAN Card', 'RC Book', 'PUC', 'Permit'], required: true },
        { name: 'scope', label: 'Document type', type: 'select', options: [{ label: 'Business document', value: 'Business' }, { label: 'Vehicle document', value: 'Vehicle' }], required: true },
        { name: 'file', label: 'Choose a local file', type: 'file', wide: true },
      ]} onSave={(values) => { addRecord('documents', { ...values, file: values.file, id: nextId('DC', documents), date: new Date().toLocaleDateString('en-US', { month: 'short', day: '2-digit', year: 'numeric' }), status: 'In review' }); setShowForm(false); setFileName('') }} saveLabel="Add to demo" />}
      {selected && <DetailDialog title={selected.name} record={selected} onClose={() => setSelected(null)} rows={Object.entries(selected)} />}
    </div>
  )
}

function Maintenance() {
  const { maintenance, addRecord, updateRecord } = useDemoData()
  const [tab, setTab] = useState('All')
  const [showForm, setShowForm] = useState(false)
  const [selected, setSelected] = useState(null)
  const [query, setQuery] = useState('')
  const filtered = maintenance.filter((record) =>
    (tab === 'All' || record.status === tab)
    && `${record.vehicle} ${record.type} ${record.id}`.toLowerCase().includes(query.toLowerCase()),
  )

  return (
    <div>
      <PageHeader title="Maintenance" description="Schedule service and keep track of fleet health and costs." action={<Button onClick={() => setShowForm(true)}><Plus size={16} />Add maintenance</Button>} />
      <div className="mb-5 grid grid-cols-2 gap-3 xl:grid-cols-3">
        <MetricCard label="Open jobs" value={maintenance.filter((item) => item.status === 'Ongoing').length} icon={Wrench} tone="blue" />
        <MetricCard label="Completed this month" value={maintenance.filter((item) => item.status === 'Completed').length} icon={Check} />
        <MetricCard label="Maintenance costs" value={currency(maintenance.reduce((sum, item) => sum + Number(item.cost), 0))} icon={BadgeIndianRupee} tone="amber" />
      </div>
      <Card className="overflow-hidden">
        <Tabs items={['All', 'Ongoing', 'Completed']} value={tab} onChange={setTab} />
        <div className="p-4 sm:p-5"><SearchField value={query} onChange={setQuery} placeholder="Search vehicle or maintenance…" /></div>
        <DataTable rows={filtered} columns={[
          { key: 'vehicle', label: 'Vehicle', render: (row) => <button type="button" onClick={() => setSelected(row)} className="text-left font-medium text-slate-800 hover:text-emerald-800">{row.vehicle}<span className="mt-1 block text-[11px] font-normal text-slate-400">{row.id} · {row.type}</span></button> },
          { key: 'start', label: 'Started' }, { key: 'expected', label: 'Expected completion' },
          { key: 'cost', label: 'Cost', render: (row) => currency(row.cost) },
          { key: 'payment', label: 'Payment', render: (row) => <StatusBadge status={row.payment} /> },
          { key: 'status', label: 'Work status', render: (row) => <StatusBadge status={row.status} /> },
          { key: 'action', label: '', render: (row) => <div className="flex gap-1"><Button variant="quiet" className="min-h-8 px-2.5" onClick={() => setSelected(row)}>History</Button>{row.status === 'Ongoing' && <Button variant="quiet" className="min-h-8 px-2.5" onClick={() => updateRecord('maintenance', row.id, { status: 'Completed' })}>Complete</Button>}</div> },
        ]} />
      </Card>
      {showForm && <RecordForm title="Add maintenance" onClose={() => setShowForm(false)} fields={[
        { name: 'vehicle', label: 'Vehicle', type: 'select', options: ['Honda Activa 6G', 'Royal Enfield Classic 350', 'Ather 450X', 'TVS Jupiter', 'Yamaha FZ-S FI'], required: true },
        { name: 'type', label: 'Maintenance type', required: true },
        { name: 'start', label: 'Start date', type: 'date', required: true },
        { name: 'expected', label: 'Expected completion', type: 'date', required: true },
        { name: 'cost', label: 'Estimated cost (₹)', type: 'number', min: 0, required: true },
        { name: 'payment', label: 'Payment status', type: 'select', options: ['Pending', 'Paid'], required: true },
      ]} onSave={(values) => { addRecord('maintenance', { ...values, id: nextId('MT', maintenance), cost: Number(values.cost), status: 'Ongoing' }); setShowForm(false) }} />}
      {selected && <DetailDialog title={`Maintenance history · ${selected.vehicle}`} record={selected} onClose={() => setSelected(null)} rows={Object.entries(selected).map(([key, value]) => [key, key === 'cost' ? currency(value) : value])} />}
    </div>
  )
}

function Staff() {
  const { staff, addRecord, updateRecord } = useDemoData()
  const [tab, setTab] = useState('All')
  const [query, setQuery] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [selected, setSelected] = useState(null)
  const filtered = staff.filter((person) =>
    (tab === 'All' || person.status === tab)
    && `${person.name} ${person.role} ${person.phone}`.toLowerCase().includes(query.toLowerCase()),
  )

  return (
    <div>
      <PageHeader title="Staff" description="Manage your team, roles, attendance and payroll overview." action={<Button onClick={() => setShowForm(true)}><Plus size={16} />Add staff</Button>} />
      <div className="mb-5 grid grid-cols-2 gap-3 xl:grid-cols-3">
        <MetricCard label="Team members" value={staff.length} caption="Sample profiles" icon={Users} />
        <MetricCard label="Active team" value={staff.filter((person) => person.status === 'Active').length} icon={ShieldCheck} tone="green" />
        <MetricCard label="Monthly payroll" value={currency(staff.filter((person) => person.status === 'Active').reduce((sum, person) => sum + Number(person.salary), 0))} icon={BadgeIndianRupee} tone="violet" />
      </div>
      <Card className="overflow-hidden">
        <Tabs items={['All', 'Active', 'Inactive']} value={tab} onChange={setTab} />
        <div className="p-4 sm:p-5"><SearchField value={query} onChange={setQuery} placeholder="Search team members…" /></div>
        <DataTable rows={filtered} columns={[
          { key: 'name', label: 'Team member', render: (row) => <button type="button" onClick={() => setSelected(row)} className="text-left font-medium text-slate-800 hover:text-emerald-800">{row.name}<span className="mt-1 block text-[11px] font-normal text-slate-400">{row.id}</span></button> },
          { key: 'role', label: 'Role' }, { key: 'phone', label: 'Phone' },
          { key: 'salary', label: 'Monthly salary', render: (row) => currency(row.salary) },
          { key: 'attendance', label: 'Attendance' }, { key: 'nextSalary', label: 'Next salary' },
          { key: 'status', label: 'Status', render: (row) => <StatusBadge status={row.status} /> },
          { key: 'action', label: '', render: (row) => <Button variant="quiet" className="min-h-8 px-2.5" onClick={() => updateRecord('staff', row.id, { status: row.status === 'Active' ? 'Inactive' : 'Active' })}>{row.status === 'Active' ? 'Deactivate' : 'Activate'}</Button> },
        ]} />
      </Card>
      {showForm && <RecordForm title="Add team member" onClose={() => setShowForm(false)} fields={[
        { name: 'name', label: 'Full name', required: true },
        { name: 'role', label: 'Role', type: 'select', options: ['Fleet manager', 'Operations associate', 'Customer support', 'Delivery associate', 'Administrator'], required: true },
        { name: 'phone', label: 'Phone number', type: 'tel', required: true },
        { name: 'salary', label: 'Monthly salary (₹)', type: 'number', min: 0, required: true },
        { name: 'nextSalary', label: 'Next salary date', type: 'date' },
      ]} onSave={(values) => { addRecord('staff', { ...values, salary: Number(values.salary), id: nextId('ST', staff), attendance: 'Not recorded', status: 'Active' }); setShowForm(false) }} />}
      {selected && <DetailDialog title={selected.name} record={selected} onClose={() => setSelected(null)} rows={Object.entries(selected).map(([key, value]) => [key, key === 'salary' ? currency(value) : value])} />}
    </div>
  )
}

const reportSeries = {
  Overview: [18, 22, 19, 26, 31, 35],
  Revenue: [14, 19, 16, 25, 29, 37],
  Bookings: [12, 16, 15, 21, 25, 30],
  Vehicles: [18, 22, 19, 26, 27, 31],
  Customers: [9, 13, 15, 20, 21, 28],
  Expenses: [8, 10, 12, 14, 13, 17],
  Staff: [12, 13, 13, 14, 15, 15],
}

function Reports() {
  const { vehicles, bookings, customers, payments } = useDemoData()
  const [tab, setTab] = useState('Overview')
  const sections = Object.keys(reportSeries)
  const data = reportSeries[tab].map((value, index) => ({ label: ['May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct'][index], value }))

  function exportCsv() {
    const csvRows = [['Booking ID', 'Customer', 'Vehicle', 'Rental dates', 'Type', 'Status', 'Paid', 'Pending']]
    bookings.forEach((row) => csvRows.push([row.id, row.customer, row.vehicle, row.dates, row.type, row.status, row.paid, row.pending]))
    const content = csvRows.map((row) => row.map((value) => `"${String(value ?? '').replaceAll('"', '""')}"`).join(',')).join('\r\n')
    const url = URL.createObjectURL(new Blob([content], { type: 'text/csv;charset=utf-8' }))
    const link = document.createElement('a')
    link.href = url
    link.download = 'wavygo-demo-bookings.csv'
    document.body.append(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  }

  return (
    <div>
      <PageHeader title="Reports" description="Explore sample trends across your rental business." action={<div className="flex gap-2"><FilterSelect value="Last 6 months" onChange={() => {}} options={['Last 6 months', 'This month', 'Last 30 days']} /><Button variant="secondary" onClick={exportCsv}><ArrowDownToLine size={16} />Export bookings CSV</Button></div>} />
      <div className="mb-5 flex flex-wrap gap-2">
        {[['Revenue', '₹3,54,800'], ['Bookings', bookings.length], ['Vehicle utilization', '74%'], ['Customers', customers.length]].map(([label, value]) => <Card key={label} className="min-w-36 flex-1 p-4"><p className="text-xs text-slate-500">{label}</p><p className="mt-2 text-xl font-semibold text-slate-900">{value}</p></Card>)}
      </div>
      <Card className="overflow-hidden">
        <Tabs items={sections} value={tab} onChange={setTab} />
        <div className="grid gap-4 p-4 sm:p-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(270px,0.8fr)]">
          <section className="min-w-0"><div><h2 className="text-sm font-semibold text-slate-900">{tab} trends</h2><p className="mt-1 text-xs text-slate-500">Illustrative demo figures · May–October 2026</p></div><div className="mt-4"><BarChart data={data} label={`${tab} report trend`} /></div></section>
          <section className="rounded-xl bg-slate-50 p-4"><h2 className="text-sm font-semibold text-slate-900">Fleet utilization</h2><p className="mt-1 text-xs text-slate-500">Illustrative utilization by vehicle type</p><div className="mt-4 space-y-4">{[['Motorcycles', 78], ['Scooters', 71], ['Electric', 63]].map(([label, value]) => <div key={label}><div className="mb-1.5 flex justify-between text-xs"><span className="text-slate-600">{label}</span><span className="font-medium text-slate-800">{value}%</span></div><div className="h-2 rounded-full bg-slate-200"><div className="h-2 rounded-full bg-emerald-600" style={{ width: `${value}%` }} /></div></div>)}</div><div className="mt-5 rounded-xl border border-slate-200 bg-white p-3 text-[11px] leading-5 text-slate-500">Utilization and financial figures are illustrative. This workspace is not connected to business APIs.</div></section>
        </div>
      </Card>
      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <Card className="overflow-hidden"><div className="p-5"><h2 className="text-sm font-semibold text-slate-900">Top vehicles by bookings</h2><p className="mt-1 text-xs text-slate-500">Based on these illustrative sample records</p></div><DataTable rows={vehicles.slice(0, 4).map((vehicle, index) => ({ ...vehicle, reportBookings: [28, 23, 19, 15][index] }))} columns={[{ key: 'name', label: 'Vehicle' }, { key: 'registration', label: 'Registration' }, { key: 'type', label: 'Type' }, { key: 'reportBookings', label: 'Bookings', render: (row) => <span className="font-semibold text-slate-800">{row.reportBookings}</span> }]} /></Card>
        <Card className="p-5"><h2 className="text-sm font-semibold text-slate-900">Recent report notes</h2><div className="mt-4 space-y-3 text-xs"><p className="rounded-xl bg-emerald-50 px-3.5 py-3 leading-5 text-emerald-900">Sample payments currently total {currency(payments.reduce((sum, item) => sum + item.amount, 0))}.</p><p className="rounded-xl bg-slate-50 px-3.5 py-3 leading-5 text-slate-600">The current demo dataset contains {bookings.length} booking records and {customers.length} customer profiles.</p></div></Card>
      </div>
    </div>
  )
}

const settingSections = [
  { label: 'Business profile', fields: [{ name: 'businessName', label: 'Business name', required: true }, { name: 'owner', label: 'Owner name', required: true }, { name: 'phone', label: 'Business phone', type: 'tel', required: true }, { name: 'email', label: 'Business email', type: 'email' }, { name: 'address', label: 'Business address', wide: true }, { name: 'businessLogo', label: 'Business logo · local file', type: 'file', wide: true }] },
  { label: 'Booking rules', fields: [{ name: 'minimum', label: 'Minimum rental duration (hours)', type: 'number', min: 1 }, { name: 'advance', label: 'Maximum advance booking (days)', type: 'number', min: 1 }, { name: 'deposit', label: 'Default deposit (₹)', type: 'number', min: 0 }, { name: 'cancellation', label: 'Cancellation window (hours)', type: 'number', min: 0 }] },
  { label: 'Payment settings', fields: [{ name: 'currency', label: 'Display currency' }, { name: 'taxId', label: 'GST registration number' }, { name: 'paymentNote', label: 'Payment note for customers', wide: true }] },
  { label: 'Notification settings', fields: [{ name: 'bookingNotifications', label: 'Booking updates enabled', type: 'select', options: ['Enabled', 'Disabled'] }, { name: 'paymentNotifications', label: 'Payment reminders enabled', type: 'select', options: ['Enabled', 'Disabled'] }, { name: 'maintenanceNotifications', label: 'Maintenance reminders enabled', type: 'select', options: ['Enabled', 'Disabled'] }] },
  { label: 'Profile settings', fields: [{ name: 'profileName', label: 'Profile name' }, { name: 'profileEmail', label: 'Profile email', type: 'email' }, { name: 'profilePhone', label: 'Profile phone', type: 'tel' }] },
  { label: 'User permissions', fields: [{ name: 'staffAccess', label: 'Staff access level', type: 'select', options: ['Read only', 'Bookings and customers', 'Manager access'] }, { name: 'invitePolicy', label: 'Team invitation policy', type: 'select', options: ['Owner approval', 'Manager approval'] }] },
  { label: 'Document categories', fields: [{ name: 'businessCategories', label: 'Business document categories', wide: true }, { name: 'vehicleCategories', label: 'Vehicle document categories', wide: true }] },
  { label: 'Staff permissions', fields: [{ name: 'bookingPermission', label: 'Manage bookings', type: 'select', options: ['Allowed', 'Restricted'] }, { name: 'paymentPermission', label: 'View payment totals', type: 'select', options: ['Allowed', 'Restricted'] }, { name: 'settingsPermission', label: 'Manage workspace settings', type: 'select', options: ['Allowed', 'Restricted'] }] },
]

const defaultSettings = {
  businessName: 'WavyGo Mobility',
  owner: 'WavyGo Vendor',
  phone: '+91 98765 43210',
  email: 'hello@wavygo.example',
  address: 'Ahmedabad, Gujarat',
  minimum: '24',
  advance: '90',
  deposit: '2000',
  cancellation: '24',
  currency: 'INR · Indian Rupee',
  paymentNote: 'Payment is collected directly by the rental partner.',
  bookingNotifications: 'Enabled',
  paymentNotifications: 'Enabled',
  maintenanceNotifications: 'Enabled',
  profileName: 'WavyGo Vendor',
  profileEmail: 'vendor@wavygo.example',
  profilePhone: '+91 98765 43210',
  staffAccess: 'Bookings and customers',
  invitePolicy: 'Owner approval',
  businessCategories: 'Shop License, GST Certificate, PAN Card',
  vehicleCategories: 'Insurance, RC Book, PUC, Permit',
  bookingPermission: 'Allowed',
  paymentPermission: 'Restricted',
  settingsPermission: 'Restricted',
}

function Settings() {
  const [section, setSection] = useState(settingSections[0].label)
  const [settings, setSettings] = useState(() => {
    const stored = window.localStorage.getItem('wavygo-demo-settings')
    return stored ? { ...defaultSettings, ...JSON.parse(stored) } : defaultSettings
  })
  const [draft, setDraft] = useState(settings)
  const [notice, setNotice] = useState('')
  const current = settingSections.find((item) => item.label === section)

  function saveSettings(event) {
    event.preventDefault()
    const missing = current.fields.find((field) => field.required && !String(draft[field.name] || '').trim())
    if (missing) {
      setNotice(`${missing.label} is required.`)
      return
    }
    try {
      window.localStorage.setItem('wavygo-demo-settings', JSON.stringify(draft))
      setSettings(draft)
      setNotice(`${section} saved in this browser for the demo. No server was contacted.`)
    } catch (error) {
      setNotice(`Browser storage was unavailable: ${error.message}`)
    }
  }

  return (
    <div>
      <PageHeader title="Settings" description="Manage your business preferences and team access." />
      <div className="mb-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs leading-5 text-amber-800">Settings are saved locally in this browser for this demo only. They are not synced to a server.</div>
      <div className="grid gap-4 lg:grid-cols-[225px_minmax(0,1fr)]">
        <Card className="h-fit p-2">
          <nav aria-label="Settings sections" className="flex gap-1 overflow-x-auto lg:flex-col">
            {settingSections.map((item) => <button key={item.label} type="button" onClick={() => { setSection(item.label); setNotice('') }} className={`shrink-0 rounded-xl px-3 py-2.5 text-left text-xs font-medium transition lg:w-full ${section === item.label ? 'bg-emerald-50 text-emerald-800' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-800'}`}>{item.label}</button>)}
          </nav>
        </Card>
        <Card className="p-5 sm:p-7">
          <div className="mb-5 border-b border-slate-100 pb-4"><h2 className="text-base font-semibold text-slate-900">{section}</h2><p className="mt-1 text-xs text-slate-500">Changes are kept in this browser for the demo.</p></div>
          <form onSubmit={saveSettings}>
            <div className="grid gap-4 sm:grid-cols-2">{current.fields.map((field) => <label key={field.name} className={`block ${field.wide ? 'sm:col-span-2' : ''}`}><span className="mb-1.5 block text-xs font-medium text-slate-600">{field.label}{field.required && <span className="ml-0.5 text-rose-500">*</span>}</span>{field.type === 'select' ? <select value={draft[field.name] || ''} onChange={(event) => setDraft((state) => ({ ...state, [field.name]: event.target.value }))} className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100">{field.options.map((option) => <option key={option}>{option}</option>)}</select> : field.type === 'file' ? <><input type="file" accept="image/*" onChange={(event) => setDraft((state) => ({ ...state, [field.name]: event.target.files?.[0]?.name || '' }))} className="block w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-emerald-50 file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-emerald-800" /><span className="mt-1 block text-[11px] text-slate-400">{draft[field.name] ? `Selected locally: ${draft[field.name]}` : 'File name only; no upload is performed.'}</span></> : <input required={field.required} min={field.min} type={field.type || 'text'} value={draft[field.name] || ''} onChange={(event) => setDraft((state) => ({ ...state, [field.name]: event.target.value }))} className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100" />}</label>)}</div>
            <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-5"><p role="status" aria-live="polite" className="max-w-lg text-xs text-emerald-800">{notice}</p><Button type="submit"><Check size={15} />Save in this browser</Button></div>
          </form>
          <p className="mt-5 text-[11px] text-slate-400">Business logo and file uploads are not sent or stored remotely.</p>
        </Card>
      </div>
    </div>
  )
}

export { Customers, Bookings, Payments, Documents, Maintenance, Staff, Reports, Settings }
