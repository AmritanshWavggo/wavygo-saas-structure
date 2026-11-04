import { useState, useEffect } from 'react'
import {
  AlertCircle,
  BadgeIndianRupee,
  Check,
  ChevronLeft,
  ChevronRight,
  Eye,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  Trash2,
  Users,
  Wallet,
} from 'lucide-react'
import {
  useCustomers,
  useCustomerMetrics,
  useCreateCustomer,
  useUpdateCustomer,
  useDeleteCustomer,
} from '../../hooks/useCustomers.js'
import { useAuth } from '../../providers/AuthProvider.jsx'
import {
  Button,
  Card,
  FilterSelect,
  MetricCard,
  Modal,
  PageHeader,
  SearchField,
  StatusBadge,
} from '../../components/ui/Workspace.jsx'

export function CustomerFormModal({
  isOpen,
  onClose,
  initialData = null,
  isStaff = false,
}) {
  const isEditing = Boolean(initialData?.id)
  const createMutation = useCreateCustomer()
  const updateMutation = useUpdateCustomer()

  const [formData, setFormData] = useState({
    name: initialData?.name || '',
    phone: initialData?.phone || '',
    email: initialData?.email || '',
    status: initialData?.status || 'Review',
    notes: initialData?.notes || '',
  })
  const [fieldErrors, setFieldErrors] = useState({})
  const [formError, setFormError] = useState('')

  useEffect(() => {
    if (initialData) {
      setFormData({
        name: initialData.name || '',
        phone: initialData.phone || '',
        email: initialData.email || '',
        status: initialData.status || 'Review',
        notes: initialData.notes || '',
      })
    } else {
      setFormData({
        name: '',
        phone: '',
        email: '',
        status: 'Review',
        notes: '',
      })
    }
    setFieldErrors({})
    setFormError('')
  }, [initialData, isOpen])

  if (!isOpen) return null

  const isPending = createMutation.isPending || updateMutation.isPending

  function handleChange(field, value) {
    setFormData((prev) => ({ ...prev, [field]: value }))
    setFieldErrors((prev) => ({ ...prev, [field]: '' }))
    setFormError('')
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setFieldErrors({})
    setFormError('')

    // Client-side quick checks
    const errors = {}
    if (!formData.name.trim()) errors.name = 'Full name is required.'
    if (!formData.phone.trim()) errors.phone = 'Phone number is required.'
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors)
      return
    }

    const payload = {
      name: formData.name.trim(),
      phone: formData.phone.trim(),
      email: formData.email.trim() ? formData.email.trim().toLowerCase() : null,
      notes: formData.notes.trim() || null,
    }

    if (!isStaff) {
      payload.status = formData.status
    }

    try {
      if (isEditing) {
        await updateMutation.mutateAsync({ id: initialData.id, customerData: payload })
      } else {
        await createMutation.mutateAsync(payload)
      }
      onClose()
    } catch (err) {
      if (err.status === 409 || err.code === 'CONFLICT') {
        setFieldErrors((prev) => ({
          ...prev,
          phone: err.message || 'A customer with this phone number already exists in your fleet.',
        }))
      } else if (err.status === 422 && Array.isArray(err.details)) {
        const nextErrors = {}
        err.details.forEach(({ field, message }) => {
          if (field) nextErrors[field] = message
        })
        setFieldErrors(nextErrors)
        if (Object.keys(nextErrors).length === 0) {
          setFormError(err.message || 'Validation failed. Check your inputs.')
        }
      } else {
        setFormError(err.message || 'An error occurred while saving the customer.')
      }
    }
  }

  return (
    <Modal
      title={isEditing ? 'Edit customer' : 'Add a customer'}
      onClose={onClose}
      footer={
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose} disabled={isPending}>
            Cancel
          </Button>
          <Button type="submit" form="customer-form" disabled={isPending}>
            {isPending ? (
              <span className="flex items-center gap-1.5">Saving…</span>
            ) : (
              <span className="flex items-center gap-1.5"><Check size={15} />{isEditing ? 'Update customer' : 'Save customer'}</span>
            )}
          </Button>
        </div>
      }
    >
      <form id="customer-form" noValidate onSubmit={handleSubmit} className="space-y-4">
        {formError && (
          <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800">
            {formError}
          </div>
        )}

        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block sm:col-span-2">
            <span className="mb-1.5 block text-xs font-medium text-slate-700">
              Full name <span className="text-rose-500">*</span>
            </span>
            <input
              type="text"
              required
              value={formData.name}
              onChange={(e) => handleChange('name', e.target.value)}
              placeholder="e.g. Aarav Mehta"
              className={`h-10 w-full rounded-xl border bg-white px-3 text-sm text-slate-800 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100 ${
                fieldErrors.name ? 'border-rose-300' : 'border-slate-200'
              }`}
            />
            {fieldErrors.name && <p className="mt-1 text-xs text-rose-600">{fieldErrors.name}</p>}
          </label>

          <label className="block">
            <span className="mb-1.5 block text-xs font-medium text-slate-700">
              Phone number <span className="text-rose-500">*</span>
            </span>
            <input
              type="tel"
              required
              value={formData.phone}
              onChange={(e) => handleChange('phone', e.target.value)}
              placeholder="e.g. 9876543210 or +919876543210"
              className={`h-10 w-full rounded-xl border bg-white px-3 text-sm text-slate-800 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100 ${
                fieldErrors.phone ? 'border-rose-300' : 'border-slate-200'
              }`}
            />
            {fieldErrors.phone && <p className="mt-1 text-xs text-rose-600">{fieldErrors.phone}</p>}
          </label>

          <label className="block">
            <span className="mb-1.5 block text-xs font-medium text-slate-700">
              Email address <span className="text-slate-400 font-normal">(optional)</span>
            </span>
            <input
              type="email"
              value={formData.email}
              onChange={(e) => handleChange('email', e.target.value)}
              placeholder="e.g. aarav@example.com"
              className={`h-10 w-full rounded-xl border bg-white px-3 text-sm text-slate-800 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100 ${
                fieldErrors.email ? 'border-rose-300' : 'border-slate-200'
              }`}
            />
            {fieldErrors.email && <p className="mt-1 text-xs text-rose-600">{fieldErrors.email}</p>}
          </label>

          <label className="block sm:col-span-2">
            <span className="mb-1.5 block text-xs font-medium text-slate-700">
              Profile status <span className="text-rose-500">*</span>
            </span>
            {isStaff ? (
              <div className="h-10 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 flex items-center text-sm text-slate-500">
                Review <span className="ml-2 text-xs text-slate-400">(Staff-created customers are automatically set to Review)</span>
              </div>
            ) : (
              <select
                value={formData.status}
                onChange={(e) => handleChange('status', e.target.value)}
                className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
              >
                <option value="Review">Review</option>
                <option value="Verified">Verified</option>
              </select>
            )}
            {fieldErrors.status && <p className="mt-1 text-xs text-rose-600">{fieldErrors.status}</p>}
          </label>

          <label className="block sm:col-span-2">
            <span className="mb-1.5 block text-xs font-medium text-slate-700">
              Notes <span className="text-slate-400 font-normal">(optional internal remarks)</span>
            </span>
            <textarea
              rows="3"
              value={formData.notes}
              onChange={(e) => handleChange('notes', e.target.value)}
              placeholder="Add any helpful customer details…"
              className="w-full rounded-xl border border-slate-200 bg-white p-3 text-sm text-slate-800 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
            />
            {fieldErrors.notes && <p className="mt-1 text-xs text-rose-600">{fieldErrors.notes}</p>}
          </label>
        </div>
      </form>
    </Modal>
  )
}

export function CustomerDetailModal({ customer, onClose }) {
  if (!customer) return null

  return (
    <Modal title={customer.name} onClose={onClose}>
      <div className="space-y-3">
        {[
          ['Customer ID', customer.id],
          ['Phone', customer.phone],
          ['Email', customer.email || '—'],
          ['Profile status', customer.status],
          ['Notes', customer.notes || '—'],
          ['Total bookings', '—'],
          ['Active bookings', '—'],
          ['Total paid', '—'],
          ['Pending amount', '—'],
          ['Created date', customer.createdAt ? new Date(customer.createdAt).toLocaleDateString('en-IN') : '—'],
        ].map(([label, value]) => (
          <div key={label} className="flex items-start justify-between gap-4 border-b border-slate-100 pb-2.5 last:border-0">
            <span className="text-xs text-slate-500">{label}</span>
            <span className="text-right text-xs font-medium text-slate-800">{value}</span>
          </div>
        ))}
      </div>
    </Modal>
  )
}

export default function Customers() {
  const { user } = useAuth()
  const isOwnerOrManager = user?.role === 'owner' || user?.role === 'manager'
  const isStaff = user?.role === 'staff'

  const [searchInput, setSearchInput] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('All')
  const [page, setPage] = useState(1)
  const pageSize = 10

  // Modals state
  const [showFormModal, setShowFormModal] = useState(false)
  const [editingCustomer, setEditingCustomer] = useState(null)
  const [viewingCustomer, setViewingCustomer] = useState(null)
  const [deletingCustomer, setDeletingCustomer] = useState(null)
  const [deleteError, setDeleteError] = useState('')

  const deleteMutation = useDeleteCustomer()

  // Debounce search query
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchInput.trim())
      setPage(1)
    }, 300)
    return () => clearTimeout(timer)
  }, [searchInput])

  const {
    data: customerData,
    isLoading,
    isError,
    error,
    refetch,
    isPlaceholderData,
  } = useCustomers({
    page,
    limit: pageSize,
    search: debouncedSearch || undefined,
    status: statusFilter === 'All' ? undefined : statusFilter,
  })

  const { data: metrics } = useCustomerMetrics()

  const customers = customerData?.items || []
  const meta = customerData?.meta || { total: 0, page: 1, limit: pageSize }
  const totalPages = Math.max(1, Math.ceil(meta.total / pageSize))

  async function handleDeleteConfirm() {
    if (!deletingCustomer) return
    setDeleteError('')
    try {
      await deleteMutation.mutateAsync(deletingCustomer.id)
      setDeletingCustomer(null)
    } catch (err) {
      setDeleteError(err.message || 'Failed to delete customer.')
    }
  }

  return (
    <div>
      <PageHeader
        title="Customers"
        description="Get to know your customers and keep their rental history in one place."
        action={
          <Button onClick={() => { setEditingCustomer(null); setShowFormModal(true) }}>
            <Plus size={16} /> Add customer
          </Button>
        }
      />

      {/* Metrics Row */}
      <div className="mb-5 grid grid-cols-2 gap-3 xl:grid-cols-4">
        <MetricCard
          label="Total customers"
          value={metrics?.totalCustomers ?? meta.total ?? '—'}
          caption="In your fleet"
          icon={Users}
        />
        <MetricCard
          label="Verified profiles"
          value={metrics?.verifiedProfiles ?? '—'}
          icon={ShieldCheck}
          tone="blue"
        />
        <MetricCard
          label="Total collected"
          value="—"
          caption="Available in Phase 4"
          icon={BadgeIndianRupee}
          tone="violet"
        />
        <MetricCard
          label="Pending customer dues"
          value="—"
          caption="Available in Phase 4"
          icon={Wallet}
          tone="amber"
        />
      </div>

      {/* Main Table Card */}
      <Card className="overflow-hidden">
        <div className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5">
          <SearchField
            value={searchInput}
            onChange={setSearchInput}
            placeholder="Search customers…"
          />
          <FilterSelect
            label="Status"
            value={statusFilter}
            onChange={(val) => { setStatusFilter(val); setPage(1) }}
            options={['All', 'Verified', 'Review']}
          />
        </div>

        {/* Content States */}
        {isLoading && !isPlaceholderData ? (
          <div className="divide-y divide-slate-100 p-6 space-y-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="animate-pulse flex items-center justify-between py-3">
                <div className="space-y-2">
                  <div className="h-4 w-40 rounded bg-slate-200" />
                  <div className="h-3 w-28 rounded bg-slate-100" />
                </div>
                <div className="h-4 w-24 rounded bg-slate-200" />
                <div className="h-6 w-16 rounded-full bg-slate-200" />
                <div className="h-8 w-20 rounded bg-slate-200" />
              </div>
            ))}
          </div>
        ) : isError ? (
          <div className="px-5 py-16 text-center sm:py-20">
            <span className="mx-auto grid size-14 place-items-center rounded-2xl bg-rose-50 text-rose-700">
              <AlertCircle size={24} />
            </span>
            <h3 className="mt-4 text-base font-semibold text-slate-900">Failed to load customers</h3>
            <p className="mx-auto mt-1.5 max-w-sm text-sm leading-6 text-slate-500">
              {error?.message || 'An error occurred while fetching your customer list.'}
            </p>
            <button
              type="button"
              onClick={() => refetch()}
              className="mt-4 inline-flex items-center gap-2 rounded-xl bg-emerald-800 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-900"
            >
              <RefreshCw size={15} /> Retry
            </button>
          </div>
        ) : customers.length === 0 ? (
          <div className="px-5 py-16 text-center sm:py-20">
            <span className="mx-auto grid size-14 place-items-center rounded-2xl bg-emerald-50 text-emerald-800">
              <Search size={22} />
            </span>
            <h3 className="mt-4 text-base font-semibold text-slate-900">No customers match your filters</h3>
            <p className="mx-auto mt-1 max-w-sm text-sm text-slate-500">
              Try adjusting your search terms or filter selections.
            </p>
            {(debouncedSearch || statusFilter !== 'All') && (
              <button
                type="button"
                onClick={() => { setSearchInput(''); setStatusFilter('All'); setPage(1) }}
                className="mt-4 inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-700 hover:text-emerald-800"
              >
                Reset filters
              </button>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[700px] border-collapse text-left">
              <thead>
                <tr className="bg-slate-50/80 text-[11px] font-semibold uppercase tracking-[0.11em] text-slate-400">
                  <th className="px-5 py-3.5">Customer</th>
                  <th className="px-4 py-3.5">Phone</th>
                  <th className="px-4 py-3.5">Bookings</th>
                  <th className="px-4 py-3.5">Total paid</th>
                  <th className="px-4 py-3.5">Pending</th>
                  <th className="px-4 py-3.5">Status</th>
                  <th className="px-5 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {customers.map((customer) => (
                  <tr key={customer.id} className="group transition hover:bg-emerald-50/25">
                    <td className="px-5 py-3.5">
                      <button
                        type="button"
                        onClick={() => setViewingCustomer(customer)}
                        className="text-left font-medium text-slate-800 hover:text-emerald-800"
                      >
                        {customer.name}
                        <span className="mt-0.5 block text-[11px] font-normal text-slate-400">
                          {customer.id} · {customer.email || 'No email'}
                        </span>
                      </button>
                    </td>
                    <td className="px-4 py-3.5 text-sm text-slate-700">{customer.phone}</td>
                    <td className="px-4 py-3.5 text-sm text-slate-500">—</td>
                    <td className="px-4 py-3.5 text-sm text-slate-500">—</td>
                    <td className="px-4 py-3.5 text-sm text-slate-500">—</td>
                    <td className="px-4 py-3.5">
                      <StatusBadge status={customer.status} />
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      <div className="flex justify-end gap-1">
                        <button
                          type="button"
                          onClick={() => setViewingCustomer(customer)}
                          className="inline-flex h-8 items-center gap-1 rounded-lg px-2 text-xs font-semibold text-slate-600 hover:bg-slate-100"
                          aria-label={`View ${customer.name}`}
                        >
                          <Eye size={14} /> View
                        </button>
                        <button
                          type="button"
                          onClick={() => { setEditingCustomer(customer); setShowFormModal(true) }}
                          className="inline-flex h-8 items-center gap-1 rounded-lg px-2 text-xs font-semibold text-slate-600 hover:bg-slate-100"
                          aria-label={`Edit ${customer.name}`}
                        >
                          <Pencil size={14} /> Edit
                        </button>
                        {isOwnerOrManager && (
                          <button
                            type="button"
                            onClick={() => { setDeleteError(''); setDeletingCustomer(customer) }}
                            className="inline-flex h-8 items-center gap-1 rounded-lg px-2 text-xs font-semibold text-rose-600 hover:bg-rose-50"
                            aria-label={`Delete ${customer.name}`}
                          >
                            <Trash2 size={14} /> Delete
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Footer */}
        {meta.total > 0 && (
          <div className="flex items-center justify-between border-t border-slate-100 px-5 py-3 text-xs text-slate-500">
            <span>
              Showing {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, meta.total)} of {meta.total} customers
            </span>
            <div className="flex items-center gap-1">
              <button
                type="button"
                disabled={page <= 1 || isPlaceholderData}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="grid size-8 place-items-center rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-40"
                aria-label="Previous page"
              >
                <ChevronLeft size={15} />
              </button>
              <span className="px-2 font-medium text-slate-700">
                Page {page} of {totalPages}
              </span>
              <button
                type="button"
                disabled={page >= totalPages || isPlaceholderData}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                className="grid size-8 place-items-center rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-40"
                aria-label="Next page"
              >
                <ChevronRight size={15} />
              </button>
            </div>
          </div>
        )}
      </Card>

      {/* Form Modal (Add / Edit) */}
      <CustomerFormModal
        isOpen={showFormModal}
        onClose={() => { setShowFormModal(false); setEditingCustomer(null) }}
        initialData={editingCustomer}
        isStaff={isStaff}
      />

      {/* Detail Modal */}
      <CustomerDetailModal
        customer={viewingCustomer}
        onClose={() => setViewingCustomer(null)}
      />

      {/* Delete Confirmation Modal */}
      {deletingCustomer && (
        <Modal
          title="Delete customer"
          onClose={() => setDeletingCustomer(null)}
          footer={
            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="secondary"
                onClick={() => setDeletingCustomer(null)}
                disabled={deleteMutation.isPending}
              >
                Cancel
              </Button>
              <button
                type="button"
                disabled={deleteMutation.isPending}
                onClick={handleDeleteConfirm}
                className="inline-flex h-9 items-center gap-1.5 rounded-xl bg-rose-600 px-4 text-xs font-semibold text-white transition hover:bg-rose-700 disabled:opacity-50"
              >
                <Trash2 size={14} />
                {deleteMutation.isPending ? 'Deleting…' : 'Delete customer'}
              </button>
            </div>
          }
        >
          <div className="space-y-3">
            {deleteError && (
              <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800">
                {deleteError}
              </div>
            )}
            <p className="text-sm text-slate-600">
              Are you sure you want to remove <span className="font-semibold text-slate-900">{deletingCustomer.name}</span> ({deletingCustomer.phone})?
            </p>
            <p className="text-xs text-slate-400">
              This will remove the customer from your active fleet profile. Their past records remain archived.
            </p>
          </div>
        </Modal>
      )}
    </div>
  )
}
