import { useState } from 'react'
import {
  CalendarDays,
  Check,
  ClipboardList,
  Eye,
  Plus,
  RefreshCw,
  Trash2,
  X,
  AlertTriangle,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../providers/AuthProvider.jsx'
import {
  useBookings,
  useTransitionBookingStatus,
  useDeleteBooking,
} from '../../hooks/useBookings.js'
import {
  Button,
  Card,
  DataTable,
  Modal,
  PageHeader,
  SearchField,
  StatusBadge,
  Tabs,
} from '../../components/ui/Workspace.jsx'

const currency = (amount) =>
  `₹${Number(amount || 0).toLocaleString('en-IN')}`

const formatPaise = (paise) =>
  currency((paise || 0) / 100)

const formatDate = (dateStr) => {
  if (!dateStr) return '—'
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export default function Bookings() {
  const { user } = useAuth()
  const userRole = (user?.role || '').toLowerCase()
  const isOwnerOrManager = ['owner', 'manager'].includes(userRole)

  const [query, setQuery] = useState('')
  const [tab, setTab] = useState('All')
  const [page, setPage] = useState(1)
  const limit = 20

  const [selectedBooking, setSelectedBooking] = useState(null)
  const [cancelModalBooking, setCancelModalBooking] = useState(null)
  const [cancelReason, setCancelReason] = useState('')
  const [deleteModalBooking, setDeleteModalBooking] = useState(null)
  const [actionError, setActionError] = useState('')

  const statusParam = tab === 'All' ? undefined : tab
  const {
    data: bookingsData,
    isLoading,
    isError,
    error,
    refetch,
  } = useBookings({
    page,
    limit,
    status: statusParam,
    search: query.trim() || undefined,
  })

  const transitionMutation = useTransitionBookingStatus()
  const deleteMutation = useDeleteBooking()

  const bookings = bookingsData?.items || []
  const meta = bookingsData?.meta || { total: 0, page: 1, limit: 20 }
  const totalPages = Math.ceil((meta.total || 0) / limit) || 1

  const tabs = [
    { label: 'All', value: 'All' },
    { label: 'Pending', value: 'Pending' },
    { label: 'Confirmed', value: 'Confirmed' },
    { label: 'Active', value: 'Active' },
    { label: 'Completed', value: 'Completed' },
    { label: 'Cancelled', value: 'Cancelled' },
  ]

  function handleTabChange(newTab) {
    setTab(newTab)
    setPage(1)
  }

  function handleSearchChange(val) {
    setQuery(val)
    setPage(1)
  }

  async function handleTransition(bookingId, targetStatus, reason) {
    setActionError('')
    try {
      const payload = { status: targetStatus }
      if (reason && reason.trim()) {
        payload.cancelReason = reason.trim()
      }
      await transitionMutation.mutateAsync({
        id: bookingId,
        statusData: payload,
      })
      if (cancelModalBooking) setCancelModalBooking(null)
      if (selectedBooking && selectedBooking.id === bookingId) {
        setSelectedBooking((prev) => ({
          ...prev,
          status: targetStatus,
          cancelReason: reason || prev.cancelReason,
        }))
      }
    } catch (err) {
      setActionError(err.message || 'Status transition failed.')
    }
  }

  async function handleDelete(bookingId) {
    setActionError('')
    try {
      await deleteMutation.mutateAsync(bookingId)
      setDeleteModalBooking(null)
      if (selectedBooking && selectedBooking.id === bookingId) {
        setSelectedBooking(null)
      }
    } catch (err) {
      setActionError(err.message || 'Failed to delete booking.')
    }
  }

  return (
    <div>
      <PageHeader
        title="Bookings"
        description="Track rental lifecycles, active bookings, customer handovers and completions."
        action={
          <Link to="/app/bookings/new">
            <Button>
              <Plus size={16} />
              Add booking
            </Button>
          </Link>
        }
      />

      {actionError && (
        <div
          role="alert"
          className="mb-4 flex items-center justify-between rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800"
        >
          <div className="flex items-center gap-2">
            <AlertTriangle size={18} className="shrink-0 text-rose-600" />
            <span>{actionError}</span>
          </div>
          <button
            type="button"
            onClick={() => setActionError('')}
            className="text-rose-600 hover:text-rose-800"
          >
            <X size={16} />
          </button>
        </div>
      )}

      <Card className="overflow-hidden">
        <Tabs items={tabs} value={tab} onChange={handleTabChange} />

        <div className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5">
          <SearchField
            value={query}
            onChange={handleSearchChange}
            placeholder="Search booking number, customer or vehicle…"
          />
        </div>

        {isLoading ? (
          <div className="flex h-64 flex-col items-center justify-center gap-3 p-8 text-slate-500">
            <RefreshCw className="size-6 animate-spin text-emerald-700" />
            <p className="text-sm">Loading bookings…</p>
          </div>
        ) : isError ? (
          <div className="flex h-64 flex-col items-center justify-center gap-3 p-8 text-center text-slate-600">
            <AlertTriangle className="size-8 text-rose-500" />
            <p className="text-sm font-medium text-slate-800">
              {error?.message || 'Failed to load bookings.'}
            </p>
            <Button variant="secondary" onClick={() => refetch()}>
              <RefreshCw size={14} /> Retry
            </Button>
          </div>
        ) : bookings.length === 0 ? (
          <div className="flex h-64 flex-col items-center justify-center gap-3 p-8 text-center text-slate-500">
            <ClipboardList className="size-10 text-slate-300" />
            <p className="text-sm font-medium text-slate-700">No bookings found</p>
            <p className="text-xs text-slate-400">
              {query || tab !== 'All'
                ? 'Try adjusting your filters or search query.'
                : 'Get started by creating your first booking.'}
            </p>
            {tab !== 'All' && (
              <Button variant="quiet" onClick={() => setTab('All')}>
                View all bookings
              </Button>
            )}
          </div>
        ) : (
          <>
            <DataTable
              rows={bookings}
              columns={[
                {
                  key: 'bookingNumber',
                  label: 'Booking #',
                  render: (row) => (
                    <button
                      type="button"
                      onClick={() => setSelectedBooking(row)}
                      className="font-semibold text-emerald-800 hover:underline"
                    >
                      {row.bookingNumber}
                    </button>
                  ),
                },
                {
                  key: 'customer',
                  label: 'Customer',
                  render: (row) => (
                    <div>
                      <span className="font-medium text-slate-800">
                        {row.customerSnapshot?.name || '—'}
                      </span>
                      <span className="mt-0.5 block text-[11px] text-slate-400">
                        {row.customerSnapshot?.phone || '—'}
                      </span>
                    </div>
                  ),
                },
                {
                  key: 'vehicle',
                  label: 'Vehicle',
                  render: (row) => (
                    <div>
                      <span className="font-medium text-slate-800">
                        {row.vehicleSnapshot?.name || '—'}
                      </span>
                      <span className="mt-0.5 block text-[11px] text-slate-400">
                        {row.vehicleSnapshot?.registration ||
                          row.vehicleSnapshot?.registrationNumber ||
                          '—'}
                      </span>
                    </div>
                  ),
                },
                {
                  key: 'dates',
                  label: 'Rental dates',
                  render: (row) => (
                    <div className="text-xs text-slate-600">
                      <span>{formatDate(row.startDate)}</span>
                      <span className="mx-1 text-slate-400">→</span>
                      <span>{formatDate(row.endDate)}</span>
                    </div>
                  ),
                },
                {
                  key: 'total',
                  label: 'Total',
                  render: (row) => (
                    <span className="font-semibold text-slate-800">
                      {formatPaise(row.totalAmountPaise)}
                    </span>
                  ),
                },
                {
                  key: 'status',
                  label: 'Status',
                  render: (row) => <StatusBadge status={row.status} />,
                },
                {
                  key: 'actions',
                  label: 'Actions',
                  render: (row) => {
                    const status = row.status
                    const canStaffCancelPending =
                      status === 'Pending'
                    const canOwnerManagerCancel =
                      isOwnerOrManager && ['Pending', 'Confirmed'].includes(status)
                    const canCancel = canStaffCancelPending || canOwnerManagerCancel
                    const canDelete =
                      isOwnerOrManager && ['Pending', 'Cancelled'].includes(status)

                    return (
                      <div className="flex items-center gap-1">
                        <Button
                          variant="quiet"
                          className="min-h-8 px-2"
                          aria-label={`View ${row.bookingNumber}`}
                          onClick={() => setSelectedBooking(row)}
                        >
                          <Eye size={15} />
                        </Button>

                        {status === 'Pending' && (
                          <Button
                            variant="quiet"
                            className="min-h-8 px-2 text-emerald-800 hover:bg-emerald-50"
                            onClick={() => handleTransition(row.id, 'Confirmed')}
                            disabled={transitionMutation.isPending}
                          >
                            Confirm
                          </Button>
                        )}

                        {status === 'Confirmed' && (
                          <Button
                            variant="quiet"
                            className="min-h-8 px-2 text-blue-800 hover:bg-blue-50"
                            onClick={() => handleTransition(row.id, 'Active')}
                            disabled={transitionMutation.isPending}
                          >
                            Activate
                          </Button>
                        )}

                        {status === 'Active' && (
                          <Button
                            variant="quiet"
                            className="min-h-8 px-2 text-emerald-800 hover:bg-emerald-50"
                            onClick={() => handleTransition(row.id, 'Completed')}
                            disabled={transitionMutation.isPending}
                          >
                            Complete
                          </Button>
                        )}

                        {canCancel && (
                          <Button
                            variant="quiet"
                            className="min-h-8 px-2 text-rose-700 hover:bg-rose-50"
                            onClick={() => {
                              setCancelModalBooking(row)
                              setCancelReason('')
                            }}
                            disabled={transitionMutation.isPending}
                          >
                            Cancel
                          </Button>
                        )}

                        {canDelete && (
                          <Button
                            variant="quiet"
                            className="min-h-8 px-2 text-rose-700 hover:bg-rose-50"
                            aria-label={`Delete ${row.bookingNumber}`}
                            onClick={() => setDeleteModalBooking(row)}
                            disabled={deleteMutation.isPending}
                          >
                            <Trash2 size={15} />
                          </Button>
                        )}
                      </div>
                    )
                  },
                },
              ]}
            />

            <div className="flex flex-col items-center justify-between gap-3 border-t border-slate-100 px-5 py-4 sm:flex-row">
              <p className="text-xs text-slate-500">
                Showing {bookings.length} of {meta.total} bookings
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="secondary"
                  className="min-h-8 px-3 text-xs"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  Previous
                </Button>
                <span className="text-xs font-medium text-slate-600">
                  Page {meta.page} of {totalPages}
                </span>
                <Button
                  variant="secondary"
                  className="min-h-8 px-3 text-xs"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next
                </Button>
              </div>
            </div>
          </>
        )}
      </Card>

      {/* Booking Details Modal */}
      {selectedBooking && (
        <Modal
          title={`Booking ${selectedBooking.bookingNumber}`}
          onClose={() => setSelectedBooking(null)}
          footer={
            <div className="flex items-center justify-between w-full">
              <div>
                {isOwnerOrManager &&
                  ['Pending', 'Cancelled'].includes(selectedBooking.status) && (
                    <Button
                      variant="quiet"
                      className="text-rose-700 hover:bg-rose-50"
                      onClick={() => {
                        setDeleteModalBooking(selectedBooking)
                      }}
                    >
                      <Trash2 size={15} /> Delete booking
                    </Button>
                  )}
              </div>
              <div className="flex items-center gap-2">
                {selectedBooking.status === 'Pending' && (
                  <>
                    <Button
                      variant="secondary"
                      className="text-rose-700"
                      onClick={() => {
                        setCancelModalBooking(selectedBooking)
                        setCancelReason('')
                      }}
                    >
                      Cancel booking
                    </Button>
                    <Button
                      onClick={() => handleTransition(selectedBooking.id, 'Confirmed')}
                    >
                      <Check size={15} /> Confirm booking
                    </Button>
                  </>
                )}
                {selectedBooking.status === 'Confirmed' && (
                  <>
                    {isOwnerOrManager && (
                      <Button
                        variant="secondary"
                        className="text-rose-700"
                        onClick={() => {
                          setCancelModalBooking(selectedBooking)
                          setCancelReason('')
                        }}
                      >
                        Cancel booking
                      </Button>
                    )}
                    <Button
                      onClick={() => handleTransition(selectedBooking.id, 'Active')}
                    >
                      <Check size={15} /> Handover & Activate
                    </Button>
                  </>
                )}
                {selectedBooking.status === 'Active' && (
                  <Button
                    onClick={() => handleTransition(selectedBooking.id, 'Completed')}
                  >
                    <Check size={15} /> Return & Complete
                  </Button>
                )}
                <Button variant="secondary" onClick={() => setSelectedBooking(null)}>
                  Close
                </Button>
              </div>
            </div>
          }
        >
          <div className="space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <span className="text-xs text-slate-400">Current status</span>
                <div className="mt-1">
                  <StatusBadge status={selectedBooking.status} />
                </div>
              </div>
              <div className="text-right">
                <span className="text-xs text-slate-400">Total amount</span>
                <p className="mt-0.5 text-lg font-bold text-slate-900">
                  {formatPaise(selectedBooking.totalAmountPaise)}
                </p>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-xl border border-slate-100 bg-slate-50/50 p-3">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Customer
                </p>
                <p className="mt-1 font-semibold text-slate-800">
                  {selectedBooking.customerSnapshot?.name || '—'}
                </p>
                <p className="text-xs text-slate-500">
                  {selectedBooking.customerSnapshot?.phone || '—'}
                </p>
                {selectedBooking.customerSnapshot?.email && (
                  <p className="text-xs text-slate-500">
                    {selectedBooking.customerSnapshot.email}
                  </p>
                )}
              </div>

              <div className="rounded-xl border border-slate-100 bg-slate-50/50 p-3">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Vehicle
                </p>
                <p className="mt-1 font-semibold text-slate-800">
                  {selectedBooking.vehicleSnapshot?.name || '—'}
                </p>
                <p className="text-xs text-slate-500">
                  {selectedBooking.vehicleSnapshot?.registration ||
                    selectedBooking.vehicleSnapshot?.registrationNumber ||
                    '—'}
                </p>
                <p className="text-xs text-slate-400">
                  {selectedBooking.vehicleSnapshot?.type || '—'}
                </p>
              </div>
            </div>

            <div className="space-y-2 border-t border-slate-100 pt-3 text-xs">
              <div className="flex justify-between py-1">
                <span className="text-slate-500">Rental start</span>
                <span className="font-medium text-slate-800">
                  {formatDate(selectedBooking.startDate)}
                </span>
              </div>
              <div className="flex justify-between py-1">
                <span className="text-slate-500">Rental end</span>
                <span className="font-medium text-slate-800">
                  {formatDate(selectedBooking.endDate)}
                </span>
              </div>
              <div className="flex justify-between py-1">
                <span className="text-slate-500">Billable days</span>
                <span className="font-medium text-slate-800">
                  {selectedBooking.billableDays} {selectedBooking.billableDays === 1 ? 'day' : 'days'}
                </span>
              </div>
              <div className="flex justify-between py-1">
                <span className="text-slate-500">Daily rate (snapshot)</span>
                <span className="font-medium text-slate-800">
                  {formatPaise(selectedBooking.dailyRatePaise)} / day
                </span>
              </div>
              <div className="flex justify-between py-1">
                <span className="text-slate-500">Base rental amount</span>
                <span className="font-medium text-slate-800">
                  {formatPaise(selectedBooking.baseAmountPaise)}
                </span>
              </div>
              {selectedBooking.discountPaise > 0 && (
                <div className="flex justify-between py-1 text-emerald-700">
                  <span>Applied discount</span>
                  <span>−{formatPaise(selectedBooking.discountPaise)}</span>
                </div>
              )}
              {selectedBooking.securityDepositPaise > 0 && (
                <div className="flex justify-between py-1">
                  <span className="text-slate-500">Security deposit</span>
                  <span className="font-medium text-slate-800">
                    {formatPaise(selectedBooking.securityDepositPaise)}
                  </span>
                </div>
              )}
              {selectedBooking.pickupLocation && (
                <div className="flex justify-between py-1">
                  <span className="text-slate-500">Pickup location</span>
                  <span className="font-medium text-slate-800">
                    {selectedBooking.pickupLocation}
                  </span>
                </div>
              )}
            </div>

            {/* Lifecycle Timestamps */}
            <div className="rounded-xl border border-slate-100 bg-slate-50 p-3 text-[11px] space-y-1 text-slate-500">
              <div className="flex justify-between">
                <span>Created at:</span>
                <span>{formatDate(selectedBooking.createdAt)}</span>
              </div>
              {selectedBooking.confirmedAt && (
                <div className="flex justify-between">
                  <span>Confirmed at:</span>
                  <span>{formatDate(selectedBooking.confirmedAt)}</span>
                </div>
              )}
              {selectedBooking.activatedAt && (
                <div className="flex justify-between">
                  <span>Activated at:</span>
                  <span>{formatDate(selectedBooking.activatedAt)}</span>
                </div>
              )}
              {selectedBooking.completedAt && (
                <div className="flex justify-between">
                  <span>Completed at:</span>
                  <span>{formatDate(selectedBooking.completedAt)}</span>
                </div>
              )}
              {selectedBooking.cancelledAt && (
                <div className="flex justify-between text-rose-700">
                  <span>Cancelled at:</span>
                  <span>{formatDate(selectedBooking.cancelledAt)}</span>
                </div>
              )}
              {selectedBooking.cancelReason && (
                <div className="pt-1 text-rose-700 border-t border-slate-200">
                  <span className="font-medium">Cancel reason:</span> {selectedBooking.cancelReason}
                </div>
              )}
            </div>

            {selectedBooking.notes && (
              <div className="text-xs">
                <span className="font-medium text-slate-600">Notes:</span>
                <p className="mt-0.5 rounded-lg bg-slate-50 p-2 text-slate-700">
                  {selectedBooking.notes}
                </p>
              </div>
            )}
          </div>
        </Modal>
      )}

      {/* Cancel Confirmation Modal */}
      {cancelModalBooking && (
        <Modal
          title={`Cancel Booking ${cancelModalBooking.bookingNumber}`}
          onClose={() => setCancelModalBooking(null)}
          footer={
            <div className="flex justify-end gap-2">
              <Button
                variant="secondary"
                onClick={() => setCancelModalBooking(null)}
              >
                Back
              </Button>
              <Button
                className="bg-rose-700 hover:bg-rose-800 text-white"
                onClick={() =>
                  handleTransition(
                    cancelModalBooking.id,
                    'Cancelled',
                    cancelReason
                  )
                }
                disabled={transitionMutation.isPending}
              >
                Confirm cancellation
              </Button>
            </div>
          }
        >
          <div className="space-y-4">
            <p className="text-sm text-slate-600">
              Are you sure you want to cancel booking{' '}
              <strong className="text-slate-800">
                {cancelModalBooking.bookingNumber}
              </strong>
              ? This frees up the vehicle for future reservations.
            </p>
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-slate-700">
                Cancellation reason (optional, max 200 chars)
              </span>
              <input
                type="text"
                maxLength={200}
                value={cancelReason}
                onChange={(e) => setCancelReason(e.target.value)}
                placeholder="e.g. Customer request, emergency"
                className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none focus:border-rose-500 focus:ring-2 focus:ring-rose-100"
              />
            </label>
          </div>
        </Modal>
      )}

      {/* Delete Confirmation Modal */}
      {deleteModalBooking && (
        <Modal
          title={`Delete Booking ${deleteModalBooking.bookingNumber}`}
          onClose={() => setDeleteModalBooking(null)}
          footer={
            <div className="flex justify-end gap-2">
              <Button
                variant="secondary"
                onClick={() => setDeleteModalBooking(null)}
              >
                Cancel
              </Button>
              <Button
                className="bg-rose-700 hover:bg-rose-800 text-white"
                onClick={() => handleDelete(deleteModalBooking.id)}
                disabled={deleteMutation.isPending}
              >
                Delete permanently
              </Button>
            </div>
          }
        >
          <div className="space-y-3">
            <p className="text-sm text-slate-600">
              Are you sure you want to delete booking{' '}
              <strong className="text-slate-800">
                {deleteModalBooking.bookingNumber}
              </strong>
              ?
            </p>
            <p className="text-xs text-rose-600">
              This action cannot be undone. Only Pending or Cancelled bookings can be
              deleted.
            </p>
          </div>
        </Modal>
      )}
    </div>
  )
}
